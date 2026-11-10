import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import make
HERE=Path(__file__).resolve().parent
W,H=1080,1920
F=make.FONTS
html=f"""<!doctype html><html><head><meta charset=utf-8><style>
@font-face{{font-family:R;src:url('{(F/'MPLUSRounded1c-800.ttf').as_uri()}');font-weight:800}}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}
body{{background:radial-gradient(ellipse at 50% 40%,#4a1a9a 0%,#1d0c4a 40%,#0a0520 75%,#05030f 100%);position:relative;font-family:R}}
.st i{{position:absolute;border-radius:50%}}
.arch{{position:absolute;left:60px;right:60px;top:300px;bottom:-200px;border:8px solid #ff5fd8;border-bottom:none;border-radius:520px 520px 0 0;box-shadow:0 0 34px #ff5fd8,inset 0 0 34px #ff5fd8;opacity:.5}}
.arch2{{position:absolute;left:25px;right:25px;top:260px;bottom:-200px;border:5px solid #5ce1ff;border-bottom:none;border-radius:560px 560px 0 0;box-shadow:0 0 26px #5ce1ff;opacity:.4}}
.logo{{position:absolute;top:250px;left:50%;transform:translateX(-50%);width:1080px}}
.gh{{position:absolute;top:600px;left:50%;transform:translateX(-50%);width:1080px}}
.t1{{position:absolute;top:1520px;left:0;right:0;text-align:center;font-size:76px;font-weight:800;color:#ffe873;text-shadow:0 0 12px #ffb800,0 0 40px #ff8a00}}
.t2{{position:absolute;top:1640px;left:0;right:0;text-align:center;font-size:50px;font-weight:800;color:#fff;letter-spacing:.06em;text-shadow:0 0 10px #ff4fd8,0 0 30px #8a5cff}}
</style></head><body><div class=st>{make.stars(W,H,120,3)}</div><div class=arch2></div><div class=arch></div>
<img class=logo src="{(HERE/'vid/logo.png').as_uri()}"><img class=gh src="{(HERE/'vid/ghosts.png').as_uri()}">
<div class=t1>App Storeで配信予定</div><div class=t2>iPhone・iPad</div></body></html>"""
async def main():
    t=HERE/'_end.html'; t.write_text(html,encoding='utf-8')
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--allow-file-access-from-files"])
        pg=await b.new_page(viewport={"width":W,"height":H})
        await pg.goto(t.as_uri()); await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(HERE/'vid/s7.png')); await b.close()
asyncio.run(main())
