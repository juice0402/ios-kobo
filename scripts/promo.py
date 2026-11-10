#!/usr/bin/env python3
"""宣伝の絵（案A「ネオンの看板」）と、縦の宣伝動画（動く文字）を作る。app.json に promo があるアプリだけ。

  python3 scripts/promo.py shots <app>   → shots.py のスクショを案Aの絵に包む（fastlane/screenshots を入れかえる）
                                           元のスクショは build/<app>/promo/raw/ に残す（動画で使う）
  python3 scripts/promo.py video <app>   → build/<app>/promo/<app>-promo.mp4（1080×1920・30fps・無音のステレオ AAC。App Store には送らない）

見た目は 11/10【ios】の試作（ブランチ claude/promo-a の promo-draft/make.py の案 a・motion.py）と同じ。
絵はゲームの画面とコードの飾りだけ（Canva のライブラリの素材は使わない）。文字は app.json の promo から入れる（手で打たない）。
フォントはゲームに入っている OFL のもの（M PLUS Rounded 1c 800）。App Store のスクショには文字や飾りを足してよい。
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
    jobs = []
    for png in sorted(raw.glob("*/*.png")):
        lang, (scene, kind) = png.parent.name, png.stem.rsplit("-", 1)
        h = heads(promo, lang, scene)
        if not h:
            sys.exit(f"promo.headlines に {scene} の見出しがありません")
        W, H = Image.open(png).size
        jobs.append((card_html(font, h[0], h[1], png, W, H), W, H, src / lang / png.name))
    asyncio.run(snap_pages(jobs))
    for _, W, H, out in jobs:
        im = Image.open(out)
        if im.size != (W, H):
            sys.exit(f"::error::{out.name} の大きさが {im.size}（{W}×{H} のはず）")
        im.convert("RGB").save(out)   # App Store のスクショは透明なし
        print(f"{out.relative_to(ROOT)} {W}x{H}（案A）")
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


def video(app):
    cfg, promo = load(app)
    if not promo or not promo.get("motion"):
        print(f"{app}: app.json に promo.motion がないので、宣伝動画は作りません")
        return
    out_dir = ROOT / "build" / app / "promo"
    if not (out_dir / "raw").exists():
        sys.exit("先に scripts/promo.py shots を動かしてください（元のスクショを使う）")
    font = font_data_url(app, promo.get("font", "MPLUSRounded1c-ExtraBold"), [all_text(cfg, promo)], out_dir / "_font.ttf")
    total, html = motion_page(app, cfg, promo, font)
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
    dest = out_dir / f"{app}-promo.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", str(frames / "f%04d.jpg"),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(dest)], check=True)
    shutil.rmtree(frames, ignore_errors=True)
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


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "shots":
        shots(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "video":
        video(sys.argv[2])
    else:
        sys.exit(__doc__)
