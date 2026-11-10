#!/usr/bin/env python3
"""パチおばの宣伝の絵（App Store のスクショ用）を HTML で組んで headless Chrome で書き出す。
python3 make.py <案 a|b> <場面名> <見出し1> <見出し2> <スクショ> <出力> [幅 高さ]
"""
import asyncio, sys, random, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = Path("/home/claude/ios-kobo/build/pachioba/project/Game/fonts")
ASSETS = HERE / "assets"


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


def html(variant, h1, h2, shot, W, H, ghosts):
    k = W / 1320  # iPad などで大きさをそろえる
    css_fonts = f"""
@font-face{{font-family:R;src:url('{(FONTS/'MPLUSRounded1c-800.ttf').as_uri()}');font-weight:800}}
@font-face{{font-family:R;src:url('{(FONTS/'MPLUSRounded1c-700.ttf').as_uri()}');font-weight:700}}
@font-face{{font-family:K;src:url('{(FONTS/'KiwiMaru-500.ttf').as_uri()}')}}
"""
    shot_uri = Path(shot).resolve().as_uri()
    if variant == "a":
        from PIL import Image as _I
        iw, ih = _I.open(shot).size
        top, pad = int(640 * k), int(10 * k)
        sw = int(min(1000 * k, (H - top - 40 * k) * iw / ih + 2 * pad))
        n2 = max(1, len(h2))
        f2 = int(min(128 * k, (W - 140 * k) / n2))
        return f"""<!doctype html><html><head><meta charset=utf-8><style>{css_fonts}
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
<div class=fr><img src="{shot_uri}"></div></body></html>"""
    # 案 b：台の絵をぼかした背景・ななめのスクショ・飛び出すおばけ
    sw = int(960 * k)
    bg = (ASSETS / "133_src.webp").as_uri()
    gh = ""
    for g in ghosts:
        gh += f'<img class=g src="{(ASSETS/g["f"]).as_uri()}" style="left:{int(g["x"]*k)}px;top:{int(g["y"]*k)}px;width:{int(g["w"]*k)}px;transform:rotate({g["r"]}deg);filter:drop-shadow(0 0 {int(26*k)}px {g["c"]})">'
    return f"""<!doctype html><html><head><meta charset=utf-8><style>{css_fonts}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}
body{{position:relative;font-family:R;background:#0b0620}}
.bg{{position:absolute;inset:-60px;background:url('{bg}') center/cover;filter:blur({int(22*k)}px) saturate(1.3);opacity:.9}}
.dim{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(12,5,35,.82) 0%,rgba(12,5,35,.45) 30%,rgba(12,5,35,.35) 70%,rgba(12,5,35,.75) 100%)}}
.st i{{position:absolute;border-radius:50%}}
.sign{{position:absolute;top:{int(140*k)}px;left:50%;transform:translateX(-50%);padding:{int(36*k)}px {int(60*k)}px {int(44*k)}px;border-radius:{int(56*k)}px;background:rgba(20,8,50,.72);border:{int(7*k)}px solid #ffe873;box-shadow:0 0 {int(30*k)}px #ffb800,inset 0 0 {int(26*k)}px rgba(255,184,0,.5);text-align:center;white-space:nowrap}}
.l1{{font-size:{int(88*k)}px;font-weight:800;color:#5ce1ff;text-shadow:0 0 {int(10*k)}px #5ce1ff,0 0 {int(36*k)}px #1aa7ff}}
.l2{{font-size:{int(118*k)}px;font-weight:800;color:#fff;margin-top:{int(10*k)}px;text-shadow:0 0 {int(8*k)}px #fff,0 0 {int(28*k)}px #ff4fd8,0 0 {int(70*k)}px #ff4fd8}}
.fr{{position:absolute;left:50%;top:{int(700*k)}px;width:{sw}px;transform:translateX(-50%) rotate(-3.5deg);padding:{int(9*k)}px;border-radius:{int(74*k)}px;background:linear-gradient(160deg,#fff 0%,#ffd6fa 40%,#bff0ff 100%);box-shadow:0 {int(30*k)}px {int(90*k)}px rgba(0,0,0,.6),0 0 {int(60*k)}px rgba(255,95,216,.55)}}
.fr img{{display:block;width:100%;border-radius:{int(66*k)}px}}
.g{{position:absolute}}
</style></head><body><div class=bg></div><div class=dim></div><div class=st>{stars(W,H,90,11)}</div>
<div class=fr><img src="{shot_uri}"></div>{gh}
<div class=sign><div class=l1>{h1}</div><div class=l2>{h2}</div></div></body></html>"""


async def main():
    variant, name, h1, h2, shot, out = sys.argv[1:7]
    W, H = (int(sys.argv[7]), int(sys.argv[8])) if len(sys.argv) > 8 else (1320, 2868)
    ghosts = json.loads(Path(HERE / "ghosts.json").read_text()) if (HERE / "ghosts.json").exists() else []
    page_html = html(variant, h1, h2, shot, W, H, ghosts.get(name, []) if isinstance(ghosts, dict) else ghosts)
    tmp = HERE / f"_{variant}_{name}.html"
    tmp.write_text(page_html, encoding="utf-8")
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        await pg.goto(tmp.as_uri())
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=out)
        await b.close()
    print(out)

if __name__ == "__main__":
    asyncio.run(main())
