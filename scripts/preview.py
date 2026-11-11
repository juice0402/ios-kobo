#!/usr/bin/env python3
"""App Store のプレビュー動画（App プレビュー）を、アプリの本物の画面の録画で作る。

  python3 scripts/preview.py render <app> [--device iphone|ipad] [--lang ja] [--fast]
      → build/<app>/previews/<言語>/<機種>.mp4 と build/<app>/previews/preview.json
  python3 scripts/preview.py probe <動画>   → 大きさ・コマ数・長さ・コーデックを点検する

アプリの中と同じ HTML（build/<app>/project/Game。先に scripts/prepare.py）を headless Chrome で開き、
ページの時計を止めて（Playwright の clock）1コマずつ進めながら撮る。重いコマでも動きがなめらかで、毎回同じ動画になる。
CSS や Web Animations の動き（ボタンの光・シートの出入り）も、同じ時計にそろえる（__pv.vsync）。

場面と台本は app.json の preview（README の「プレビュー動画」）。ゲームはボタンの click と、
キャンバスへの PointerEvent で動かす（ゲームの中の変数は見えない前提。スクショの台本と同じ）。
テロップとカットインは、ページのいちばん上に重ねる別の層（shadow DOM）に描く。ゲームの部品や見た目は変えない。

Apple の決まり：App プレビューはアプリの画面の録画だけ（2.3.4。説明の文字は重ねてよい）・15〜30秒・30fps まで・
H.264・ステレオ AAC。音は入れない（無音の AAC）。大きさは iPhone 886×1920・iPad 1200×1600（縦）。
"""
import argparse
import asyncio
import base64
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shots import app_zoom  # noqa: E402  スクショと同じ iPad の拡大の計算

FPS = 30
# 動画の大きさ（px）と、そのときの画面の大きさ（CSS の px）。iPhone 6.9 インチ・iPad 13 インチの縦
DEVICES = {
    "iphone": {"size": (886, 1920), "css": (443, 960)},
    "ipad": {"size": (1200, 1600), "css": (1032, 1376)},
}
LIMITS = {"min": 15.0, "max": 30.0, "fps": 30}
T0 = 1794000000000  # ページの時計のはじめ（2026-11-10 ごろ。毎回同じ）

# ページに入れる道具（ゲームより先に読む）。時計をそろえる vsync・指の動き・テロップの層
HELPERS = r"""
(()=>{
const pv=window.__pv={};
// ---- CSS・Web Animations の時計を、止めたページの時計（performance.now）にそろえる
const seen=new WeakMap();
pv.vsync=()=>{
  const now=performance.now(), tl=document.timeline.currentTime;
  for(const a of document.getAnimations()){
    if(a.playState!=='running'||a.startTime==null||!a.playbackRate) continue;
    let s=seen.get(a); if(!s){s={c0:a.currentTime||0,v0:now};seen.set(a,s)}
    const want=s.c0+(now-s.v0)*a.playbackRate;
    a.startTime=tl-want/a.playbackRate;
  }
};
// ---- 指（ボタンの click と PointerEvent）
pv.el=s=>typeof s==='string'?document.querySelector(s):s;
pv.box=s=>{const e=pv.el(s);return e?e.getBoundingClientRect():null};
pv.touch=null;  // 指の場所（テロップの層に、うすい丸で見せる）
pv.fire=(t,type,x,y)=>{
  const now=performance.now();
  if(type==='pointerdown')pv.touch={x,y,t0:now,up:null};else if(pv.touch){pv.touch.x=x;pv.touch.y=y;if(type==='pointerup')pv.touch.up=now}
  t.dispatchEvent(new PointerEvent(type,{clientX:x,clientY:y,bubbles:true,cancelable:true,composed:true,
  pointerId:7,isPrimary:true,pointerType:'touch',button:0,buttons:type==='pointerup'?0:1}))};
pv.click=s=>{const e=pv.el(s);if(!e)return false;const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,now=performance.now();
  pv.touch={x,y,t0:now,up:now+150};e.click();return true};
pv.tap=(x,y)=>{const t=document.elementFromPoint(x,y);if(!t)return false;
  pv.fire(t,'pointerdown',x,y);pv.fire(t,'pointerup',x,y);pv.touch.up+=150;
  t.dispatchEvent(new MouseEvent('click',{clientX:x,clientY:y,bubbles:true,cancelable:true}));return true};
// ボタンをしばらくおしたままにする（回すボタンなど）
pv.hold=(sel,ms)=>{const e=pv.el(sel);if(!e)return false;const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
  pv.fire(e,'pointerdown',x,y);setTimeout(()=>pv.fire(e,'pointerup',x,y),ms);return true};
// pts の順に ms かけてなぞる（ページの時計の setTimeout で動く＝撮るコマにそろう）
pv.drag=(pts,ms,sel)=>{
  const t=(sel&&pv.el(sel))||document.elementFromPoint(pts[0][0],pts[0][1]);if(!t)return false;
  const L=[0];for(let i=1;i<pts.length;i++)L.push(L[i-1]+Math.hypot(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]));
  const at=k=>{const d=k*L[L.length-1];let i=1;while(i<L.length-1&&L[i]<d)i++;const s=L[i]-L[i-1]||1,u=Math.min(1,(d-L[i-1])/s);
    return [pts[i-1][0]+(pts[i][0]-pts[i-1][0])*u,pts[i-1][1]+(pts[i][1]-pts[i-1][1])*u]};
  pv.fire(t,'pointerdown',pts[0][0],pts[0][1]);
  const n=Math.max(2,Math.round(ms/16));let i=0;
  const step=()=>{i++;const [x,y]=at(i/n);pv.fire(t,'pointermove',x,y);if(i<n)setTimeout(step,ms/n);else pv.fire(t,'pointerup',x,y)};
  setTimeout(step,ms/n);return true;
};
// 要素のまわりを右回りに turns 回なぞる（ダイヤル・ハンドル）
pv.turn=(sel,turns,ms,a0)=>{const b=pv.box(sel);if(!b)return false;const cx=b.left+b.width/2,cy=b.top+b.height/2,r=Math.min(b.width,b.height)*.42;
  const n=Math.max(8,Math.round(24*turns)),pts=[];a0=a0??-Math.PI/2;
  for(let i=0;i<=n;i++){const a=a0+i/n*turns*Math.PI*2;pts.push([cx+Math.cos(a)*r,cy+Math.sin(a)*r])}
  return pv.drag(pts,ms,sel)};
// ---- テロップとカットインの層（ゲームの CSS がとどかない shadow DOM）
pv.setup=async(fontUrl,style)=>{
  const f=new FontFace('PVCaption',`url(${fontUrl})`);await f.load();document.fonts.add(f);
  const host=document.createElement('div');host.id='__pv';
  host.style.cssText='position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483647;contain:strict';
  document.documentElement.appendChild(host);
  const sh=host.attachShadow({mode:'open'});
  sh.innerHTML=`<style>
  :host{all:initial}
  .cap{position:absolute;left:50%;top:0;white-space:nowrap;font-family:PVCaption;line-height:1.15;opacity:0;will-change:transform,opacity}
  .cut{position:absolute;left:50%;top:0;white-space:nowrap;font-family:PVCaption;line-height:1;opacity:0;will-change:transform,opacity}
  .neon.cap{color:#fff;background:rgba(14,7,36,.80);border:2px solid rgba(255,95,216,.9);border-radius:999px;padding:.42em 1.05em .5em;
    box-shadow:0 0 18px rgba(255,79,216,.55),inset 0 0 12px rgba(92,225,255,.25);text-shadow:0 0 8px rgba(255,79,216,.9),0 0 2px #fff}
  .neon.cut{color:#ffe873;text-shadow:0 0 6px #fff,0 0 22px #ffb800,0 0 50px #ff4fd8,0 0 90px #8a5cff;-webkit-text-stroke:2px rgba(120,30,0,.35)}
  .paper.cap{color:#3a332c;background:#fffdf6;border-radius:6px;padding:.42em .95em .5em;
    box-shadow:0 3px 0 rgba(58,51,44,.18),0 6px 16px rgba(58,51,44,.22)}
  .paper.cut{color:#c0392b;text-shadow:0 3px 0 #fffdf6,0 0 18px #fffdf6}
  .touch{position:absolute;left:0;top:0;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;opacity:0;
    background:radial-gradient(circle,rgba(255,255,255,.55) 0 38%,rgba(255,255,255,.18) 39% 62%,transparent 63%);border:2px solid rgba(255,255,255,.85);
    box-shadow:0 0 10px rgba(0,0,0,.35)}
  </style><div class="touch"></div><div class="cap ${style}"></div><div class="cut ${style}"></div>`;
  pv.cap=sh.querySelector('.cap');pv.cut=sh.querySelector('.cut');pv.tch=sh.querySelector('.touch');pv.capText=null;pv.cutText=null;
};
// 1行に入る大きさ（入らなければ小さく。2行にはしない）
const fit=(e,text,size,maxW)=>{e.textContent=text;e.style.fontSize=size+'px';let s=size;
  while(e.offsetWidth>maxW&&s>8){s-=1;e.style.fontSize=s+'px'}return s};
pv.show=o=>{
  const W=innerWidth,H=innerHeight,k=Math.min(W/443,H/960);
  const c=pv.cap;
  if(o.cap){if(pv.capText!==o.cap||pv.capW!==W){fit(c,o.cap,Math.round(25*k),W*.9);pv.capText=o.cap;pv.capW=W}
    c.style.opacity=o.capOp;c.style.transform=`translate(-50%,-50%) translate(0,${o.capY*H+o.capDy*k}px)`}
  else c.style.opacity=0;
  const u=pv.cut;
  if(o.cut){if(pv.cutText!==o.cut||pv.cutW!==W){fit(u,o.cut,Math.round(96*k),W*.92);pv.cutText=o.cut;pv.cutW=W}
    u.style.opacity=o.cutOp;u.style.transform=`translate(-50%,-50%) translate(${o.cutX*W}px,${o.cutY*H}px) scale(${o.cutS}) skewX(${o.cutK}deg)`}
  else u.style.opacity=0;
  // 指の丸：おしているあいだは見せ、はなしたら 0.25 秒で消える
  const T=pv.touch,g=pv.tch;
  if(T){const now=performance.now(),a=Math.min(1,(now-T.t0)/60),f=T.up==null?1:Math.max(0,1-(now-T.up)/250);
    g.style.opacity=(Math.min(a,f)*.9).toFixed(3);g.style.transform=`translate(${T.x}px,${T.y}px) scale(${(k*(1-.12*a)).toFixed(3)})`;if(f<=0)pv.touch=null}
  else g.style.opacity=0;
};
})();
"""


# ページのフォント（@font-face）と絵を、ゲームが使う前に読みきる。文字の形から当たりの形を作るゲームでも、毎回同じ動きになる
PRELOAD = ("Promise.all([...document.fonts].map(f=>f.load().catch(()=>0)).concat([...document.images].map(i=>i.decode().catch(()=>0))))"
           ".then(()=>document.fonts.ready).then(()=>document.fonts.size)")


def for_device(d, kind):
    """devices.<機種> に書いた分で上書きした設定（機種で画面の作りがちがい、出来事の時刻がずれるとき）"""
    return {**{k: v for k, v in d.items() if k != "devices"}, **d.get("devices", {}).get(kind, {})}


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = max(0.0, min(1.0, x))
    return x ** 3


def lang_text(v, lang):
    if isinstance(v, dict):
        return v.get(lang) or v.get(lang.split("-")[0]) or next(iter(v.values()))
    return v


def overlay_at(scene, t, lang, default_y):
    """場面の中の t 秒のテロップ・カットインの状態"""
    o = {"cap": None, "capOp": 0, "capDy": 0, "capY": default_y, "cut": None, "cutOp": 0, "cutX": 0, "cutY": .42, "cutS": 1, "cutK": 0}
    for c in scene.get("captions", []):
        a, b, text = c["at"], c["to"], lang_text(c["text"], lang)
        if a <= t < b:
            fin, fout = ease_out((t - a) / .28), 1 - ease_in((t - (b - .22)) / .22)
            o.update(cap=text, capOp=round(min(fin, fout), 3), capDy=round((1 - fin) * 14, 2), capY=c.get("y", scene.get("capY", default_y)))
    for c in scene.get("cutins", []):
        a, b = c["at"], c["to"]
        if a <= t < b:
            pin, pout = ease_out((t - a) / .3), ease_in((t - (b - .3)) / .3)
            o.update(cut=lang_text(c["text"], lang), cutY=c.get("y", .42),
                     cutX=round(.6 * (1 - pin) - .5 * pout, 4),          # 右からすっと入って、左へぬける
                     cutOp=round(min(pin, 1 - pout), 3), cutS=round(1.18 - .18 * pin + .06 * pout, 4),
                     cutK=round(-14 * (1 - pin) - 14 * pout, 2))
    return o


def font_data_url(app, name, texts, out):
    """ゲームと同じフォント（OFL）を、使う文字だけにして data URL にする。
    ゲームに入れたフォントはゲームの文字だけなので、prepare.py が取ってきた元のフォント（build/_fonts）を先に使う"""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    cands = sorted((ROOT / "build" / "_fonts").glob(f"*-{name}.ttf")) + [ROOT / "build" / app / "project" / "Game" / "fonts" / f"{name}.ttf"]
    src = next((p for p in cands if p.exists()), None)
    if not src:
        sys.exit(f"フォント {name} が見つかりません（先に prepare.py）")
    font = TTFont(src)
    cmap = font.getBestCmap()
    chars = set("".join(texts))
    missing = sorted(c for c in chars if not c.isspace() and ord(c) not in cmap)
    if missing:
        sys.exit(f"フォント {src.name} に入っていない文字: {''.join(missing)}")
    opts = subset.Options()
    opts.layout_features = ["*"]
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(chars))
    sub.subset(font)
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(out)
    return "data:font/ttf;base64," + base64.b64encode(out.read_bytes()).decode()


def caption_font(cfg, app, texts):
    """テロップのフォント"""
    return font_data_url(app, cfg["preview"]["font"], texts, ROOT / "build" / app / "previews" / "_caption.ttf")


def all_texts(pv):
    out = []
    scenes = list(pv["scenes"]) + [d for s in pv["scenes"] for d in s.get("devices", {}).values()]
    for s in scenes:
        for c in s.get("captions", []) + s.get("cutins", []):
            out += list(c["text"].values()) if isinstance(c["text"], dict) else [c["text"]]
    return out


def timecode(sec):
    f = int(round(sec * FPS))
    return f"{f // (FPS * 3600):02d}:{f // (FPS * 60) % 60:02d}:{f // FPS % 60:02d}:{f % FPS:02d}"


async def record(app, cfg, lang, kind, frames, fast=False):
    from playwright.async_api import async_playwright

    pv = for_device(cfg["preview"], kind)
    game = (ROOT / "build" / app / "project" / "Game" / "index.html").resolve()
    dev = DEVICES[kind]
    px_w, px_h = dev["size"]
    css_w, css_h = dev["css"]
    fit = cfg.get("fitSize") if cfg.get("zoom", "page") != "game" else None
    zoom = app_zoom(css_w, css_h, fit)
    vw, vh = round(css_w / zoom), round(css_h / zoom)
    dsf = px_w / vw
    zoom = css_w / vw
    globals_ = [g for g in cfg.get("langGlobals", []) if re.fullmatch(r"[A-Za-z_$][\w$]*", g)]
    font_url = caption_font(cfg, app, all_texts(pv))
    style = pv.get("style", "neon")
    default_y = pv.get("capY", .86)
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    n_all = 0
    async with async_playwright() as p:
        import os
        browser = await p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None,
                                          args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        for si, scene in enumerate(pv["scenes"]):
            scene = for_device(scene, kind)
            ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1 if fast else dsf,
                                            is_mobile=True, has_touch=True, locale=lang)
            init = f"window.APP_LANGS={json.dumps([lang])};window.APP_PLATFORM='ios';window.APP_ZOOM={zoom};"
            init += "".join(f"window.{g}=window.APP_LANGS;" for g in globals_)
            init += pv.get("init", "")
            seed = int(scene.get("seed", pv.get("seed", 7)))  # Math.random をゲームより先に決まった並びにする（毎回同じ動き）
            init += f"(function(){{var s={seed};Math.random=function(){{s=s*16807%2147483647;return(s-1)/2147483646}}}})();"
            await ctx.add_init_script(HELPERS + init)
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.clock.install(time=T0)  # 毎回同じ日時（日付で変わる絵があっても同じ動画に）
            await page.clock.pause_at(T0 + 1000)  # 止める（ここから先は run_for で進めた分だけ進む）
            await page.goto(game.as_uri() + (("#" + scene["hash"]) if scene.get("hash") else ""))
            await page.wait_for_timeout(400)
            await page.evaluate(PRELOAD)  # フォントと絵を先に読みきる（読みこみの速さで動きが変わらないように）
            await page.evaluate(f"__pv.setup({json.dumps(font_url)},{json.dumps(style)})")
            if scene.get("js"):
                await page.evaluate(scene["js"])
            warm = float(scene.get("warm", 0))
            while warm > 0:  # 撮る前に進めておく時間（場面が落ち着くまで）
                await page.clock.run_for(int(min(warm, 1) * 1000))
                warm -= 1
            steps = sorted(scene.get("steps", []), key=lambda s: s[0])
            n = int(round(float(scene["len"]) * FPS))
            for i in range(n):
                t = i / FPS
                while steps and steps[0][0] <= t + 1e-6:
                    await page.evaluate(steps.pop(0)[1])
                await page.evaluate(f"__pv.show({json.dumps(overlay_at(scene, t, lang, default_y), ensure_ascii=False)});__pv.vsync()")
                await page.screenshot(path=str(frames / f"f{n_all:05d}.jpg"), type="jpeg", quality=92)
                n_all += 1
                await page.clock.run_for(round((i + 1) * 1000 / FPS) - round(i * 1000 / FPS))
            print(f"  {lang} {kind} 場面{si + 1} {scene.get('name', '')}: {n}コマ" + (f"  エラー: {errors[0][:120]}" if errors else ""), flush=True)
            if errors:
                print(f"::warning::preview {lang} {kind} {scene.get('name', si + 1)}: {errors[0][:200]}")
            await ctx.close()
        await browser.close()
    return (px_w, px_h), n_all


def encode(frames, size, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-framerate", str(FPS), "-i", str(frames / "f%05d.jpg"),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    # コマは JPEG（色の幅が full の yuvj420p）なので、ふつうの幅（tv）の yuv420p に直す。ffmpeg の版によっては直さないと yuvj420p のまま出る
                    "-vf", f"scale={w}:{h}:flags=lanczos:in_range=full:out_range=tv,setsar=1,format=yuv420p",
                    "-pix_fmt", "yuv420p", "-color_range", "tv",
                    "-c:v", "libx264", "-preset", "medium", "-profile:v", "high", "-level", "4.0",
                    "-crf", "18", "-maxrate", "12M", "-bufsize", "24M", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)


def probe(path, want=None):
    """App プレビューの決まりに合うかを見る。合わなければ理由のリスト"""
    d = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    dur = float(d["format"]["duration"])
    bad = []
    if not v or v["codec_name"] != "h264":
        bad.append("映像が H.264 ではない")
    if not a or a["codec_name"] != "aac" or int(a.get("channels", 0)) != 2:
        bad.append("音がステレオの AAC ではない")
    if v:
        num, den = map(int, v["r_frame_rate"].split("/"))
        if num / den > LIMITS["fps"] + .01:
            bad.append(f"コマ数 {num / den:.2f}fps（30 まで）")
        if want and (v["width"], v["height"]) != tuple(want):
            bad.append(f"大きさ {v['width']}×{v['height']}（{want[0]}×{want[1]}）")
        if v.get("pix_fmt") != "yuv420p":
            bad.append(f"色の形 {v.get('pix_fmt')}")
    if not LIMITS["min"] <= dur <= LIMITS["max"]:
        bad.append(f"長さ {dur:.2f}秒（15〜30秒）")
    info = f"{v['width']}×{v['height']} {v['r_frame_rate']} {dur:.2f}秒 {v['codec_name']}/{a['codec_name'] if a else '-'}" if v else "?"
    return info, bad


def motion_check(path):
    """止まった動画になっていないか（となりのコマとの差の平均）"""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", "fps=2,scale=160:-2,tblend=all_mode=difference,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    vals = [float(x) for x in re.findall(r"YAVG=([\d.]+)", out)]
    return sum(vals) / len(vals) if vals else 0.0


def render(app, only_dev=None, only_lang=None, fast=False):
    cfg = json.loads((ROOT / "apps" / app / "app.json").read_text(encoding="utf-8"))
    pv = cfg.get("preview")
    if not pv:
        print(f"{app}: app.json に preview がないので作りません")
        return []
    if not pv.get("font"):
        sys.exit("preview.font（テロップのフォント）がありません")
    totals = {}
    for kind in cfg.get("devices", ["iphone"]):
        totals[kind] = total = sum(float(for_device(s, kind)["len"]) for s in pv["scenes"])
        if not LIMITS["min"] <= total <= LIMITS["max"]:
            sys.exit(f"{kind}: 場面の秒の合計が {total:.1f}秒（15〜30秒にする）")
    out_dir = ROOT / "build" / app / "previews"
    made = []
    for lang in pv.get("languages", ["en-US"]):
        if only_lang and lang != only_lang:
            continue
        for kind in cfg.get("devices", ["iphone"]):
            if kind not in DEVICES or (only_dev and kind != only_dev):
                continue
            frames = out_dir / f"_frames-{lang}-{kind}"
            size, n = asyncio.run(record(app, cfg, lang, kind, frames, fast))
            dest = out_dir / lang / f"{kind}.mp4"
            encode(frames, size, dest)
            shutil.rmtree(frames, ignore_errors=True)
            info, bad = probe(dest, size)
            mv = motion_check(dest)
            if mv < 1.0:
                bad.append(f"ほとんど動いていない（{mv:.2f}）")
            print(f"{dest.relative_to(ROOT)} {info} 動き {mv:.1f}" + ("" if not bad else "  ✗ " + "・".join(bad)), flush=True)
            if bad:
                sys.exit(f"::error::{dest.name}: " + "・".join(bad))
            made.append(str(dest.relative_to(out_dir)))
    poster = float(pv.get("poster", min(5.0, min(totals.values()) / 2)))  # 表紙のコマ（全部の機種で同じ秒）
    (out_dir / "preview.json").write_text(json.dumps({"poster": timecode(poster), "videos": made}, ensure_ascii=False, indent=1), encoding="utf-8")
    return made


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["render", "probe"])
    ap.add_argument("target")
    ap.add_argument("--device", choices=list(DEVICES))
    ap.add_argument("--lang")
    ap.add_argument("--fast", action="store_true", help="ためし用（1倍の大きさで撮って広げる）")
    a = ap.parse_args()
    if a.cmd == "render":
        render(a.target, a.device, a.lang, a.fast)
    else:
        info, bad = probe(a.target)
        print(info, "OK" if not bad else "✗ " + "・".join(bad))
        sys.exit(1 if bad else 0)
