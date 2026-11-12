#!/usr/bin/env python3
"""宣伝の絵と、縦の宣伝動画（動く文字）を作る。app.json に promo があるアプリだけ。

  python3 scripts/promo.py shots <app>   → shots.py のスクショを宣伝の絵に包む（fastlane/screenshots を入れかえる）
                                           元のスクショは build/<app>/promo/raw/ に残す（動画で使う）
  python3 scripts/promo.py video <app>   → build/<app>/promo/<app>-promo.mp4（1080×1920・30fps・無音のステレオ AAC。App Store には送らない）

見た目は promo.theme でえらぶ：
  neon（決めなければこれ）＝案A「ネオンの看板」。11/10【ios】の試作（ブランチ claude/promo-a の promo-draft/make.py の案 a・motion.py）と同じ。パチおば
  paper ＝「画用紙と机」。クリーム色の画用紙と方眼・竹のものさし・マスキングテープ・墨の見出し・朱の花丸。ひらがなバランス（11/12）
    promo.art にゲームの中の絵（paper・ruler・title。build/<app>/project/Game からの道）。動画の場面に clip があると、
    プレビュー動画（build/<app>/previews/<lang>/iphone.mp4。先に preview.py render）の一部を切り取って、画面の中で動かす
絵はゲームの画面・ゲームの中の絵・コードの飾りだけ（Canva のライブラリの素材は使わない）。文字は app.json の promo から入れる（手で打たない）。
フォントはゲームに入っている OFL のもの（promo.font）。App Store のスクショには文字や飾りを足してよい。
"""
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preview import font_data_url  # noqa: E402

VW, VH, FPS = 1080, 1920, 30


def load(app):
    cfg = json.loads((ROOT / "apps" / app / "app.json").read_text(encoding="utf-8"))
    return cfg, cfg.get("promo")


def heads(promo, lang, scene):
    """場面の見出し2行。言語ごと（{"ja": [...]}）か、1つの言語だけのアプリは [1行目, 2行目]"""
    h = promo["headlines"].get(scene)
    if isinstance(h, dict):
        h = h.get(lang)
    if not h or len(h) != 2:
        sys.exit(f"promo.headlines に {scene}（{lang}）の見出し2行がありません")
    return h


def all_text(cfg, promo):
    t = "".join("".join(v if isinstance(v, list) else sum(v.values(), [])) for v in promo["headlines"].values())
    return t + "".join(promo["end"]["texts"].values()) + "0123456789"


def stars(w, h, n, seed):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        x, y = r.random() * w, r.random() * h
        s = r.choice([2, 2, 3, 3, 4, 6])
        a = r.uniform(0.35, 0.95)
        c = r.choice(["255,255,255", "255,214,250", "190,240,255", "255,240,170"])
        out.append(f'<i style="left:{x:.0f}px;top:{y:.0f}px;width:{s}px;height:{s}px;background:rgba({c},{a:.2f});box-shadow:0 0 {s*3}px rgba({c},{a:.2f})"></i>')
    return "".join(out)


def card_html(font, h1, h2, shot, W, H):
    """案A：紫のネオンの夜空・星・ピンクと水色のアーチ・見出し2行（1行目は黄色、2行目は白にピンクの光）・角丸の光る枠の中にゲームの画面"""
    from PIL import Image
    k = W / 1320  # iPad などで大きさをそろえる
    iw, ih = Image.open(shot).size
    top, pad = int(640 * k), int(10 * k)
    sw = int(min(1000 * k, (H - top - 40 * k) * iw / ih + 2 * pad))   # 画面に入るように枠を小さく（iPad）
    f2 = int(min(128 * k, (W - 140 * k) / max(1, len(h2))))          # 2行目が長いときは文字を小さく
    return f"""<!doctype html><html><head><meta charset=utf-8><style>
@font-face{{font-family:R;src:url('{font}');font-weight:800}}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}
body{{background:radial-gradient(ellipse at 50% 26%,#4a1a9a 0%,#1d0c4a 38%,#0a0520 72%,#05030f 100%);position:relative;font-family:R}}
.st i{{position:absolute;border-radius:50%}}
.arch{{position:absolute;left:{int(70*k)}px;right:{int(70*k)}px;top:{int(560*k)}px;bottom:{int(-200*k)}px;border:{int(10*k)}px solid #ff5fd8;border-bottom:none;border-radius:{int(620*k)}px {int(620*k)}px 0 0;box-shadow:0 0 {int(40*k)}px #ff5fd8,inset 0 0 {int(40*k)}px #ff5fd8;opacity:.55}}
.arch2{{position:absolute;left:{int(30*k)}px;right:{int(30*k)}px;top:{int(510*k)}px;bottom:{int(-200*k)}px;border:{int(6*k)}px solid #5ce1ff;border-bottom:none;border-radius:{int(660*k)}px {int(660*k)}px 0 0;box-shadow:0 0 {int(30*k)}px #5ce1ff;opacity:.45}}
.hd{{position:absolute;top:{int(150*k)}px;left:0;right:0;text-align:center}}
.l1{{font-size:{int(96*k)}px;font-weight:800;color:#ffe873;letter-spacing:.04em;text-shadow:0 0 {int(12*k)}px #ffb800,0 0 {int(40*k)}px #ff8a00}}
.l2{{font-size:{f2}px;font-weight:800;color:#fff;margin-top:{int(18*k)}px;letter-spacing:.02em;text-shadow:0 0 {int(8*k)}px #fff,0 0 {int(26*k)}px #ff4fd8,0 0 {int(60*k)}px #ff4fd8,0 0 {int(110*k)}px #8a5cff}}
.fr{{position:absolute;left:50%;transform:translateX(-50%);top:{int(640*k)}px;width:{sw}px;padding:{int(10*k)}px;border-radius:{int(78*k)}px;background:linear-gradient(140deg,#ff5fd8,#8a5cff 45%,#5ce1ff 75%,#ffe873);box-shadow:0 0 {int(50*k)}px rgba(255,95,216,.65),0 0 {int(140*k)}px rgba(92,225,255,.35)}}
.fr img{{display:block;width:100%;border-radius:{int(68*k)}px}}
</style></head><body><div class=st>{stars(W,H,150,7)}</div><div class=arch2></div><div class=arch></div>
<div class=hd><div class=l1>{h1}</div><div class=l2>{h2}</div></div>
<div class=fr><img src="{Path(shot).resolve().as_uri()}"></div></body></html>"""


# ---------------------------------------------------------------- 「画用紙と机」（theme paper）
INK, RED = "#2b241f", "#cf3a2c"   # 墨・朱


def hanamaru_d():
    """朱の花丸の線（まん中から外へのうず巻き → まわりの7枚の花びら）。-64〜64 の箱。動画ではこの線を描くように見せる"""
    import math
    T = 5 * math.pi
    pts = []
    for i in range(201):
        a = T * i / 200
        r = 3 + 35 * a / T
        pts.append((r * math.cos(a), r * math.sin(a)))
    for i in range(1, 241):
        u = i / 240
        a = T + (2 * math.pi + .35) * u
        r = 38 + 9 * min(1, u * 6) + 11 * abs(math.sin(3.5 * (a - T)))
        pts.append((r * math.cos(a), r * math.sin(a)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def tape_clip(d, teeth=7):
    """マスキングテープの両はしのギザギザ（clip-path）。d はギザギザの深さ（px）"""
    left = [f"{d if i % 2 else 0}px {i * 100 / teeth:.2f}%" for i in range(teeth + 1)]
    right = [f"calc(100% - {d if i % 2 else 0}px) {100 - i * 100 / teeth:.2f}%" for i in range(teeth + 1)]
    return "polygon(" + ",".join(left + right) + ")"


def paper_css(paper, k):
    """画用紙（ゲームの paper.webp）＋方眼（細い線と5マスごとの太い線）＋ふちのかげ。動画のページにも同じものを入れる"""
    c, m = round(44 * k, 2), round(220 * k, 2)
    t1, t2 = max(1, round(1.4 * k, 2)), max(1.5, round(2.4 * k, 2))
    g1, g2 = "rgba(92,124,158,.13)", "rgba(92,124,158,.23)"
    return (f"radial-gradient(ellipse at 50% 38%,rgba(255,250,236,0) 52%,rgba(122,86,40,.22) 100%),"
            f"linear-gradient({g2} {t2}px,transparent {t2}px) 0 0/{m}px {m}px,"
            f"linear-gradient(90deg,{g2} {t2}px,transparent {t2}px) 0 0/{m}px {m}px,"
            f"linear-gradient({g1} {t1}px,transparent {t1}px) 0 0/{c}px {c}px,"
            f"linear-gradient(90deg,{g1} {t1}px,transparent {t1}px) 0 0/{c}px {c}px,"
            f"url('{paper}') center/cover,#f4ecda")


def tape_css(k):
    return ("background:linear-gradient(180deg,rgba(255,255,255,.30),rgba(255,255,255,0) 46%,rgba(120,90,20,.07)),rgba(241,207,92,.80);"
            f"clip-path:{tape_clip(round(9 * k, 1))}")


def ruler_css(k):
    """竹のものさしの目盛り（ゲームの ruler.webp の上にコードで描く）"""
    mm = round(13.2 * k, 2)
    return (f"background:repeating-linear-gradient(90deg,rgba(74,48,22,.62) 0 {round(2.2*k,2)}px,transparent {round(2.2*k,2)}px {mm*5}px) 0 0/100% 46% no-repeat,"
            f"repeating-linear-gradient(90deg,rgba(74,48,22,.45) 0 {round(1.6*k,2)}px,transparent {round(1.6*k,2)}px {mm}px) 0 0/100% 26% no-repeat")


FIT_JS = ("<script>document.fonts.ready.then(()=>{for(const e of document.querySelectorAll('[data-fit]')){const m=+e.dataset.fit;"
          "if(e.scrollWidth>m)e.style.fontSize=(parseFloat(getComputedStyle(e).fontSize)*m/e.scrollWidth)+'px'}})</script>")


def card_paper(font, h1, h2, shot, W, H, art):
    """「画用紙と机」：方眼の画用紙・テープに書いた1行目・墨の2行目と朱の花丸・竹のものさし・白いふちの画面（角にマスキングテープ）"""
    from PIL import Image
    k = W / 1320
    iw, ih = Image.open(shot).size
    top, pad = int(640 * k), int(14 * k)
    sw = int(min(1010 * k, (H - top - 40 * k) * iw / ih + 2 * pad))
    rw, rh = int(W * 1.08), int(W * 1.08 * 34 / 800)
    u = lambda p: Path(p).resolve().as_uri()
    return f"""<!doctype html><html><head><meta charset=utf-8><style>
@font-face{{font-family:K;src:url('{font}');font-weight:600}}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}
body{{background:{paper_css(u(art['paper']), k)};position:relative;font-family:K;font-weight:600;color:{INK}}}
.hd{{position:absolute;top:{int(150*k)}px;left:0;right:0;text-align:center}}
.l1w{{position:relative;display:inline-block;padding:{int(14*k)}px {int(58*k)}px {int(18*k)}px}}
.tp1{{position:absolute;inset:0;transform:rotate(-2deg);{tape_css(k)}}}
.l1{{position:relative;display:inline-block;white-space:nowrap;font-size:{int(86*k)}px;letter-spacing:.05em;color:#3b3129}}
.l2w{{position:relative;display:inline-block;margin-top:{int(34*k)}px}}
.l2{{display:inline-block;white-space:nowrap;font-size:{int(150*k)}px;line-height:1.1;letter-spacing:.04em;text-shadow:0 {max(1,int(2*k))}px 0 rgba(255,253,246,.75),0 0 {max(1,int(2*k))}px rgba(43,36,31,.35)}}
.hm{{position:absolute;width:{int(176*k)}px;height:{int(176*k)}px;right:{int(-182*k)}px;top:{int(-52*k)}px;transform:rotate(-14deg);mix-blend-mode:multiply;opacity:.93}}
.hm path{{fill:none;stroke:{RED};stroke-width:6.6;stroke-linecap:round;stroke-linejoin:round}}
.rl{{position:absolute;left:{int((W-rw)/2)}px;top:{int(594*k)}px;width:{rw}px;height:{rh}px;transform:rotate(-1.1deg);filter:drop-shadow(0 {int(8*k)}px {int(10*k)}px rgba(70,45,20,.30))}}
.rl img{{position:absolute;inset:0;width:100%;height:100%}}
.rl i{{position:absolute;inset:0;{ruler_css(k)}}}
.fr{{position:absolute;left:50%;transform:translateX(-50%);top:{top}px;width:{sw}px;padding:{pad}px;box-sizing:border-box;border-radius:{int(74*k)}px;background:#fffdf7;
  box-shadow:0 0 0 {max(1,int(1.5*k))}px rgba(120,90,50,.14),0 {int(34*k)}px {int(70*k)}px {int(-12*k)}px rgba(70,45,20,.38),0 {int(6*k)}px {int(16*k)}px rgba(70,45,20,.16)}}
.fr img{{display:block;width:100%;border-radius:{int(60*k)}px}}
.tw{{position:absolute;top:{int(-40*k)}px;width:{int(270*k)}px;height:{int(80*k)}px;filter:drop-shadow(0 {int(3*k)}px {int(4*k)}px rgba(80,55,20,.22))}}
.tw.a{{left:{int(-106*k)}px;transform:rotate(-38deg)}}.tw.b{{right:{int(-106*k)}px;transform:rotate(38deg)}}
.tw b{{position:absolute;inset:0;{tape_css(k)}}}
</style></head><body>
<div class=hd><div class=l1w><span class=tp1></span><span class=l1 data-fit={int(W-300*k)}>{h1}</span></div><br>
<div class=l2w><span class=l2 data-fit={int(W-470*k)}>{h2}</span><svg class=hm viewBox="-64 -64 128 128"><path d="{hanamaru_d()}"/></svg></div></div>
<div class=rl><img src="{u(art['ruler'])}"><i></i></div>
<div class=fr><img src="{u(shot)}"><span class="tw a"><b></b></span><span class="tw b"><b></b></span></div>
{FIT_JS}</body></html>"""


def art_paths(app, promo):
    """promo.art（ゲームの中の絵の道）を、build/<app>/project/Game からの本物の場所に"""
    game = ROOT / "build" / app / "project" / "Game"
    out = {}
    for key in ("paper", "ruler", "title"):
        p = game / promo.get("art", {}).get(key, "")
        if not promo.get("art", {}).get(key) or not p.is_file():
            sys.exit(f"promo.art.{key} の絵がありません（{p.relative_to(ROOT)}。先に prepare.py）")
        out[key] = p
    return out


async def snap_pages(jobs):
    """[(html, W, H, 出力)] を headless Chrome で書き出す"""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
        for html, W, H, out in jobs:
            tmp = Path(out).with_suffix(".html")
            tmp.write_text(html, encoding="utf-8")
            pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            await pg.goto(tmp.as_uri())
            await pg.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>0))).then(()=>document.fonts.ready)")
            await pg.wait_for_timeout(200)
            await pg.screenshot(path=str(out))
            await pg.close()
            tmp.unlink()
        await b.close()


def shots(app):
    """fastlane/screenshots/<言語>/<場面>-<機種>.png を案Aの絵に包む。元は promo/raw に残す"""
    cfg, promo = load(app)
    if not promo:
        print(f"{app}: app.json に promo がないので、スクショはそのまま")
        return
    from PIL import Image
    src = ROOT / "build" / app / "fastlane" / "screenshots"
    raw = ROOT / "build" / app / "promo" / "raw"
    mark = ROOT / "build" / app / "promo" / "wrapped.json"   # 包んだ絵の時刻。shots.py で撮りなおしたら（時刻がちがう）元のスクショとして取りなおす
    if not src.exists():
        sys.exit("先に scripts/shots.py render を動かしてください")
    done = json.loads(mark.read_text()) if mark.exists() else {}
    fresh = any(done.get(str(f.relative_to(src))) != f.stat().st_mtime_ns for f in src.glob("*/*.png"))
    if fresh or not raw.exists():
        shutil.rmtree(raw, ignore_errors=True)
        shutil.copytree(src, raw)
    font = font_data_url(app, promo.get("font", "MPLUSRounded1c-ExtraBold"), [all_text(cfg, promo)], ROOT / "build" / app / "promo" / "_font.ttf")
    theme = promo.get("theme", "neon")
    art = art_paths(app, promo) if theme == "paper" else None
    jobs = []
    for png in sorted(raw.glob("*/*.png")):
        lang, (scene, kind) = png.parent.name, png.stem.rsplit("-", 1)
        h = heads(promo, lang, scene)
        if not h:
            sys.exit(f"promo.headlines に {scene} の見出しがありません")
        W, H = Image.open(png).size
        html = card_paper(font, h[0], h[1], png, W, H, art) if theme == "paper" else card_html(font, h[0], h[1], png, W, H)
        jobs.append((html, W, H, src / lang / png.name))
    asyncio.run(snap_pages(jobs))
    for _, W, H, out in jobs:
        im = Image.open(out)
        if im.size != (W, H):
            sys.exit(f"::error::{out.name} の大きさが {im.size}（{W}×{H} のはず）")
        im.convert("RGB").save(out)   # App Store のスクショは透明なし
        print(f"{out.relative_to(ROOT)} {W}x{H}（{'画用紙と机' if theme == 'paper' else '案A'}）")
    mark.write_text(json.dumps({str(f.relative_to(src)): f.stat().st_mtime_ns for f in src.glob("*/*.png")}))


# ---------------------------------------------------------------- 縦の宣伝動画（動く文字）
def end_parts(app, promo):
    """おわりの1枚のロゴとおばけ：タイトルのスクショから切り出し、ふちをぼかして背景になじませる"""
    from PIL import Image, ImageDraw, ImageFilter
    end = promo["end"]
    title = ROOT / "build" / app / "promo" / "raw" / promo.get("lang", "ja") / f"{end['shot']}-iphone.png"
    im = Image.open(title).convert("RGBA")
    W, H = im.size
    outs = {}
    for key in ("logo", "ghosts"):
        x0, y0, x1, y1 = [int(v * (W if i % 2 == 0 else H)) for i, v in enumerate(end[key])]
        part = im.crop((x0, y0, x1, y1))
        m = Image.new("L", part.size, 0)
        f = int(min(part.size) * .12)
        ImageDraw.Draw(m).rounded_rectangle((f, f, part.width - f, part.height - f), radius=f * 2, fill=255)
        part.putalpha(m.filter(ImageFilter.GaussianBlur(f * .7)))
        out = ROOT / "build" / app / "promo" / "_end" / f"{key}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        part.save(out)
        outs[key] = out.as_uri()
    return outs


def motion_page(app, cfg, promo, font):
    lang = promo.get("lang", "ja")
    raw = ROOT / "build" / app / "promo" / "raw" / lang
    scenes, t = [], 0.0
    for m in promo["motion"]["scenes"]:
        h = heads(promo, lang, m["shot"])
        scenes.append({"h1": h[0], "h2": h[1], "fx": m["fx"], "len": m["len"], "t0": t,
                       "src": (raw / f"{m['shot']}-iphone.png").as_uri()})
        t += m["len"]
    end_len = promo["motion"]["end"]
    parts = end_parts(app, promo)
    r = random.Random(7)
    st = [{"x": r.random() * VW, "y": r.random() * VH, "s": r.choice([2, 2, 3, 3, 4, 5]), "a": round(r.uniform(.35, .95), 2),
           "p": r.random() * 6.28, "c": r.choice(["255,255,255", "255,214,250", "190,240,255", "255,240,170"])} for _ in range(110)]
    sp = [{"x": r.random() * VW, "s": r.random() * .6 + .4, "ph": r.random() * 10, "c": ["#ffe873", "#ff9cf0", "#9cf2ff", "#fff"][i % 4]} for i in range(26)]
    data = {"scenes": scenes, "end_t0": t, "total": t + end_len, "swipe": .36, "stars": st, "sparks": sp,
            "logo": parts["logo"], "ghosts": parts["ghosts"]}
    texts = promo["end"]["texts"]
    t1 = texts["live"] if cfg.get("storeUrl") else texts["soon"]   # App Store に出たら（app.json に storeUrl）「配信中」
    page = (Path(__file__).resolve().parent / "promo_motion.html").read_text(encoding="utf-8")
    page = page.replace("__FONT__", font).replace("__T1__", t1).replace("__T2__", texts["sub"]).replace("__DATA__", json.dumps(data, ensure_ascii=False))
    return data["total"], page


def clip_frames(app, lang, clip, n, dest):
    """プレビュー動画の clip.from 秒から n コマを、clip.crop（[x0,y0,x1,y1] の割合）で切り取って JPEG にする。テロップのない所を切り取る"""
    mp4 = ROOT / "build" / app / "previews" / lang / "iphone.mp4"
    if not mp4.exists():
        sys.exit(f"{mp4.relative_to(ROOT)} がありません（先に scripts/preview.py render {app} --device iphone --lang {lang}）")
    from PIL import Image
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    x0, y0, x1, y1 = clip.get("crop", [0, 0, 1, 1])
    vf = f"crop=trunc(iw*{x1 - x0}/2)*2:trunc(ih*{y1 - y0}/2)*2:trunc(iw*{x0}):trunc(ih*{y0}),fps={FPS}"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(clip["from"]), "-i", str(mp4),
                    "-frames:v", str(n), "-vf", vf, "-q:v", "2", str(dest / "c%04d.jpg")], check=True)
    files = sorted(dest.glob("c*.jpg"))
    if len(files) < n:
        sys.exit(f"::error::clip（{clip['from']}秒から）のコマが足りません（{len(files)}/{n}）。プレビュー動画より長くしないでください")
    w, h = Image.open(files[0]).size
    return [f.as_uri() for f in files], w / h


def motion_page_paper(app, cfg, promo, font):
    """「画用紙と机」の縦の宣伝動画のページ（promo_motion_paper.html）"""
    import random as rnd
    lang = promo.get("lang", "ja")
    out_dir = ROOT / "build" / app / "promo"
    raw = out_dir / "raw" / lang
    art = art_paths(app, promo)
    scenes, t = [], 0.0
    for i, m in enumerate(promo["motion"]["scenes"]):
        h = heads(promo, lang, m["shot"])
        s = {"h1": h[0], "h2": h[1], "fx": m["fx"], "len": m["len"], "t0": t}
        if m.get("clip"):
            s["frames"], s["aspect"] = clip_frames(app, lang, m["clip"], int(round(m["len"] * FPS)) + 2, out_dir / "_clip" / str(i))
        else:
            from PIL import Image
            png = raw / f"{m['shot']}-iphone.png"
            w, hh = Image.open(png).size
            s["src"], s["aspect"] = png.as_uri(), w / hh
        r = rnd.Random(31 + i)
        s["rot"] = [round(r.uniform(-28, 28), 1) for _ in h[1]]      # drop：落ちてくる文字の向き
        s["tilt"] = [round(r.uniform(-4, 4), 1) for _ in h[1]]       # drop：止まったときの少しのかたむき
        scenes.append(s)
        t += m["len"]
    end_len = promo["motion"]["end"]
    data = {"scenes": scenes, "end_t0": t, "total": t + end_len, "swipe": .42, "hm": hanamaru_d(),
            "paper": paper_css(art["paper"].as_uri(), 1080 / 1320), "tape": tape_css(1080 / 1320), "ruler_ticks": ruler_css(1080 / 1320),
            "ruler": art["ruler"].as_uri(), "title": art["title"].as_uri(), "paper_img": art["paper"].as_uri()}
    texts = promo["end"]["texts"]
    t1 = texts["live"] if cfg.get("storeUrl") else texts["soon"]
    page = (Path(__file__).resolve().parent / "promo_motion_paper.html").read_text(encoding="utf-8")
    page = page.replace("__FONT__", font).replace("__T1__", t1).replace("__T2__", texts["sub"]).replace("__DATA__", json.dumps(data, ensure_ascii=False))
    return data["total"], page


def ensure_font(family, weight):
    """google/fonts の OFL のフォントを build/_fonts に取ってきて、font_data_url で使う名前（例 YujiSyuku-Regular）を返す"""
    import prepare
    path, variable = prepare.download_font(family, weight, ROOT / "build" / "_fonts")
    if not path or variable:
        sys.exit(f"フォント {family} {weight} を google/fonts で見つけられません（可変フォントは使わない）")
    return path.stem.split("-", 1)[1]


def motion_page_sumi(app, cfg, promo, ev):
    """「筆と墨」（theme sumi）の縦の宣伝動画のページ（promo_motion_sumi.html）。海外向け（英語の見出し）。
    はじめに筆の文字（縦書き）とローマ字、場面は墨の帯の見出し・朱の判・掛け軸のように開く画面、切りかえは墨のひと筆"""
    from PIL import Image
    lang = ev.get("lang", "en-US")
    out_dir = ROOT / "build" / app / "promo"
    raw = out_dir / "raw" / lang
    art = art_paths(app, promo)
    texts = ev["texts"]
    t1 = texts["live"] if cfg.get("storeUrl") else texts["soon"]
    scenes, t = [], ev["intro"]["len"]
    for i, m in enumerate(ev["scenes"]):
        h = heads(promo, lang, m["shot"])
        if not h:
            sys.exit(f"promo.headlines に {m['shot']} の {lang} の見出しがありません")
        s = {"h1": h[0], "h2": h[1], "len": m["len"], "t0": t}
        if m.get("clip"):
            s["frames"], s["aspect"] = clip_frames(app, lang, m["clip"], int(round(m["len"] * FPS)) + 2, out_dir / "_clip" / f"{ev['name']}{i}")
        else:
            png = raw / f"{m['shot']}-iphone.png"
            w, hh = Image.open(png).size
            s["src"], s["aspect"] = png.as_uri(), w / hh
        scenes.append(s)
        t += m["len"]
    fonts = ev["fonts"]
    text_name = ensure_font(*fonts["text"])
    brush_name = ensure_font(*fonts["brush"])
    words = " ".join([s["h1"] + s["h2"] for s in scenes] + [t1, texts["sub"], ev["intro"].get("caption", "")] + ev["intro"]["romaji"])
    f_text = font_data_url(app, text_name, [words], out_dir / f"_font-{ev['name']}-text.ttf")
    f_brush = font_data_url(app, brush_name, [ev["intro"]["kana"] + ev["seal"]], out_dir / f"_font-{ev['name']}-brush.ttf")
    data = {"intro": ev["intro"], "seal": ev["seal"], "scenes": scenes, "end_t0": t, "total": t + ev["end"], "wipe": .38,
            "paper_img": art["paper"].as_uri(), "title": art["title"].as_uri(), "t1": t1, "t2": texts["sub"]}
    page = (Path(__file__).resolve().parent / "promo_motion_sumi.html").read_text(encoding="utf-8")
    page = page.replace("__FONT_TEXT__", f_text).replace("__FONT_BRUSH__", f_brush).replace("__DATA__", json.dumps(data, ensure_ascii=False))
    return data["total"], page


def render_video(html, total, out_dir, dest):
    """動画のページ（render(t) で1コマを描く）を 30fps で撮って mp4 にする（1080×1920・無音のステレオ AAC・18〜20秒）"""
    tmp = out_dir / "_motion.html"
    tmp.write_text(html, encoding="utf-8")
    frames = out_dir / "_frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir()

    async def shoot():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
            pg = await b.new_page(viewport={"width": VW, "height": VH})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(tmp.as_uri())
            await pg.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>0))).then(()=>document.fonts.ready)")
            n = int(round(total * FPS))
            for i in range(n):
                await pg.evaluate(f"render({i / FPS})")
                await pg.screenshot(path=str(frames / f"f{i:04d}.jpg"), type="jpeg", quality=93)
            await b.close()
            if errs:
                sys.exit(f"::error::宣伝動画のページでエラー: {errs[0][:200]}")
            return n
    n = asyncio.run(shoot())
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", str(frames / "f%04d.jpg"),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-vf", "scale=in_range=full:out_range=tv,format=yuv420p", "-color_range", "tv",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(dest)], check=True)
    shutil.rmtree(frames, ignore_errors=True)
    shutil.rmtree(out_dir / "_clip", ignore_errors=True)
    tmp.unlink()
    from preview import probe
    info, bad = probe(dest, (VW, VH))
    bad = [b for b in bad if not b.startswith("長さ")]
    dur = n / FPS
    if not 18 <= dur <= 20.05:
        bad.append(f"長さ {dur:.1f}秒（18〜20秒）")
    print(f"{dest.relative_to(ROOT)} {info}" + ("" if not bad else "  ✗ " + "・".join(bad)))
    if bad:
        sys.exit("::error::" + "・".join(bad))


def video(app, only=None):
    """only：main（いつもの動画だけ）か promo.extraVideos の name（その動画だけ）。決めなければ全部"""
    cfg, promo = load(app)
    if not promo or not promo.get("motion"):
        print(f"{app}: app.json に promo.motion がないので、宣伝動画は作りません")
        return
    out_dir = ROOT / "build" / app / "promo"
    if not (out_dir / "raw").exists():
        sys.exit("先に scripts/promo.py shots を動かしてください（元のスクショを使う）")
    names = ["main"] + [e["name"] for e in promo.get("extraVideos", [])]
    if only and only not in names:
        sys.exit(f"{only} という動画はありません（{'・'.join(names)}）")
    if only in (None, "main"):
        font = font_data_url(app, promo.get("font", "MPLUSRounded1c-ExtraBold"), [all_text(cfg, promo)], out_dir / "_font.ttf")
        paper = promo.get("theme", "neon") == "paper"
        total, html = motion_page_paper(app, cfg, promo, font) if paper else motion_page(app, cfg, promo, font)
        render_video(html, total, out_dir, out_dir / f"{app}-promo.mp4")
    for ev in promo.get("extraVideos", []):
        if only not in (None, ev["name"]):
            continue
        if ev.get("theme") != "sumi":
            sys.exit(f"extraVideos の {ev['name']}：theme は sumi だけです")
        total, html = motion_page_sumi(app, cfg, promo, ev)
        render_video(html, total, out_dir, out_dir / f"{app}-promo-{ev['name']}.mp4")

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "shots":
        shots(sys.argv[2])
    elif len(sys.argv) in (3, 4) and sys.argv[1] == "video":
        video(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
    else:
        sys.exit(__doc__)
