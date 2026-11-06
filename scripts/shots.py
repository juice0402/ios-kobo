#!/usr/bin/env python3
"""スクショまわりの道具。

  python3 scripts/shots.py render <app>   → App Store 用のスクショを作る（Linux の headless Chrome）
  python3 scripts/shots.py pick iphone    → Mac の Actions で使うシミュレーターの UDID を出す

スクショは、アプリの中と同じ HTML（build/<app>/project/Game）を、iPhone 6.9 インチ・iPad 13 インチと
同じ画面の大きさ・倍率で開いて撮る。アプリは状態バーを隠して全画面にゲームを出すだけなので、見た目は同じ。
（シミュレーターは Actions の Mac では GPU がなく、キャンバスのゲームが重すぎて止まるため使わない）
撮る場面は app.json の screenshots。出力は build/<app>/fastlane/screenshots/<言語>/<場面>-<機種>.png
"""
import asyncio
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 画面の大きさ（CSS の px）と倍率。アプリの GameHostView.zoom と同じ計算で iPad は拡大する
DEVICES = {
    "iphone": {"size": (1320, 2868), "scale": 3},   # iPhone 6.9 インチ
    "ipad": {"size": (2064, 2752), "scale": 2},     # iPad 13 インチ
}


def app_zoom(css_w, css_h, fit):
    if not fit:
        return 1.0
    z = min(css_w / fit[0], css_h / fit[1])
    return 1.0 if z <= 1.15 else int(z * 20) / 20


async def render(app):
    from playwright.async_api import async_playwright

    cfg = json.loads((ROOT / "apps" / app / "app.json").read_text(encoding="utf-8"))
    plan = cfg.get("screenshots", {"languages": ["en-US"], "scenes": [{"name": "1", "wait": 4}]})
    game = (ROOT / "build" / app / "project" / "Game" / "index.html").resolve()
    if not game.exists():
        sys.exit("先に scripts/prepare.py を動かしてください")
    out = ROOT / "build" / app / "fastlane" / "screenshots"
    fit = cfg.get("fitSize")
    globals_ = [g for g in cfg.get("langGlobals", []) if re.fullmatch(r"[A-Za-z_$][\w$]*", g)]

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None, args=["--autoplay-policy=no-user-gesture-required"])
        for kind, dev in DEVICES.items():
            px_w, px_h = dev["size"]
            css_w, css_h = px_w / dev["scale"], px_h / dev["scale"]
            zoom = app_zoom(css_w, css_h, fit)
            # 画像がぴったりその大きさになるよう、縦横の比をそろえた整数の画面幅にする
            g = math.gcd(px_w, px_h)
            k = max(1, round(css_w / zoom / (px_w // g)))
            vw, vh = k * (px_w // g), k * (px_h // g)
            dsf = px_w / vw
            zoom = css_w / vw
            for lang in plan["languages"]:
                for scene in plan["scenes"]:
                    ctx = await browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=dsf,
                                                    is_mobile=True, has_touch=True, locale=lang)
                    init = f"window.APP_LANGS={json.dumps([lang])};window.APP_PLATFORM='ios';window.APP_ZOOM={zoom};"
                    init += "".join(f"window.{g}=window.APP_LANGS;" for g in globals_)
                    await ctx.add_init_script(init)
                    page = await ctx.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    await page.goto(game.as_uri())
                    await page.wait_for_timeout(400)
                    if scene.get("js"):
                        await page.evaluate(scene["js"])
                    await page.wait_for_timeout(int(float(scene["wait"]) * 1000))
                    dest = out / lang / f"{scene['name']}-{kind}.png"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(dest))
                    await ctx.close()
                    from PIL import Image
                    size = "x".join(map(str, Image.open(dest).size))
                    print(f"{dest.relative_to(ROOT)} {size}" + (f"  エラー: {errors[0][:120]}" if errors else ""))
                    if errors:
                        print(f"::warning::{lang} {scene['name']} {kind}: {errors[0][:200]}")
        await browser.close()


def runtime_version(key):
    m = re.search(r"iOS-(\d+)-(\d+)", key)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def pick(kind):
    want = {"iphone": [r"iPhone \d+ Pro Max", r"iPhone .*Pro", r"iPhone"],
            "ipad": [r"iPad Pro 13-inch", r"iPad Air 13-inch", r"iPad"]}[kind]
    data = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
    runtimes = sorted((k for k in data["devices"] if ".iOS-" in k), key=runtime_version, reverse=True)
    for pattern in want:
        for rt in runtimes:
            for d in data["devices"][rt]:
                if re.search(pattern, d["name"]):
                    print(d["udid"])
                    print(f"{kind}: {d['name']} ({rt.split('.')[-1]})", file=sys.stderr)
                    return
    sys.exit(f"{kind} のシミュレーターが見つかりません")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "render":
        asyncio.run(render(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "pick":
        pick(sys.argv[2])
    else:
        sys.exit(__doc__)
