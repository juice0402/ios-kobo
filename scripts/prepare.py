#!/usr/bin/env python3
"""アプリ1つ分の Xcode プロジェクトとストアの文を build/<app>/ に作る。

  python3 scripts/prepare.py <app> [--ref コミットやタグ] [--build-number N]

やること
  1. app.json の game.repo から、ゲームの HTML を決まった版（game.ref）で取ってくる
  2. Google Fonts の読み込みを、使っている文字だけのフォントファイルに置きかえる（ネットなしで同じ見た目）
  3. ネットにつなぐ読み込みが残っていないか点検する（残っていたら止める）
  4. shell/ の Swift と、アイコン・色・言語・Info.plist から XcodeGen の設定を作る
  5. fastlane（deliver）用のストアの文を build/<app>/fastlane/metadata に並べる
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_BASE = "https://juice0402.github.io/ios-kobo"
WEIGHT_NAMES = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}
STORE_LIMITS = {"name.txt": 30, "subtitle.txt": 30, "keywords.txt": 100,
                "promotional_text.txt": 170, "description.txt": 4000, "release_notes.txt": 4000}
ALL_ORIENTATIONS = ["UIInterfaceOrientationPortrait", "UIInterfaceOrientationPortraitUpsideDown",
                    "UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"]

notes = []  # Actions の結果のページに出すメモ


def say(msg):
    print(msg, flush=True)
    notes.append(msg)


def fail(msg):
    print(f"::error::{msg}", flush=True)
    sys.exit(1)


def run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


# ---------------------------------------------------------------- 1. ゲームを取ってくる
def fetch_game(app, cfg, ref, game_dir):
    g = cfg["game"]
    src = ROOT / "build" / "_src" / app
    shutil.rmtree(src, ignore_errors=True)
    src.mkdir(parents=True)
    run(["git", "init", "-q"], cwd=src)
    run(["git", "fetch", "-q", "--depth", "1", f"https://github.com/{g['repo']}", ref], cwd=src)
    run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=src)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=src, text=True).strip()
    game_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / g.get("file", "index.html"), game_dir / "index.html")
    for extra in g.get("extra", []):  # 画像や音のフォルダなど、HTML のほかに要るもの
        s = src / extra
        if s.is_dir():
            shutil.copytree(s, game_dir / extra, dirs_exist_ok=True)
        else:
            (game_dir / extra).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, game_dir / extra)
    say(f"ゲーム: {g['repo']} @ {sha[:7]}（ref: {ref}）")
    return sha


# ---------------------------------------------------------------- 2. フォントを同梱
GF_LINK = re.compile(r'<link\b[^>]*href=["\'](https://fonts\.googleapis\.com/css2?\?[^"\']+)["\'][^>]*>\s*', re.I)
GF_PRECONNECT = re.compile(r'<link\b(?=[^>]*preconnect)(?=[^>]*fonts\.g(?:oogleapis|static)\.com)[^>]*>\s*', re.I)


def parse_google_fonts(url):
    """css2?family=Klee+One:wght@400;600 → [("Klee One", [400, 600])]"""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    out = []
    for fam in q.get("family", []):
        name, _, axes = fam.partition(":")
        weights = []
        if "wght@" in axes:
            tags, _, values = axes.partition("@")
            tag_list = tags.split(",")
            wi = tag_list.index("wght")
            for tup in values.split(";"):
                parts = tup.split(",")
                if "ital" in tag_list and parts[tag_list.index("ital")] == "1":
                    continue  # 斜体は使わない
                w = parts[wi]
                weights += [int(x) for x in w.split("..")] if ".." in w else [int(w)]
        elif axes and "," in axes and axes.replace(",", "").isdigit():
            weights = [int(x) for x in axes.split(",")]  # 古い css?family=Name:400,700
        out.append((name.replace("+", " "), sorted(set(weights or [400]))))
    return out


def download_font(family, weight, cache):
    """google/fonts のリポジトリから TTF を取る。(path, 可変フォントか)"""
    cache.mkdir(parents=True, exist_ok=True)
    folder = family.lower().replace(" ", "")
    stem = family.replace(" ", "")
    style = WEIGHT_NAMES.get(weight, "Regular")
    names = [(f"{stem}-{style}.ttf", False), (f"{stem}[wght].ttf", True)]
    for lic in ("ofl", "apache", "ufl"):
        for fname, variable in names:
            dest = cache / f"{lic}-{fname}"
            if dest.exists():
                return dest, variable
            url = f"https://raw.githubusercontent.com/google/fonts/main/{lic}/{folder}/{urllib.parse.quote(fname)}"
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    dest.write_bytes(r.read())
                return dest, variable
            except urllib.error.HTTPError:
                continue
    return None, False


def localize_fonts(html, game_dir):
    links = GF_LINK.findall(html)
    if not links:
        return html
    from fontTools import subset
    from fontTools.ttLib import TTFont

    text_chars = {ord(c) for c in html if ord(c) > 0x7F}
    codepoints = set(range(0x20, 0x7F)) | set(range(0xA0, 0x180)) | set(range(0x2000, 0x2070)) \
        | set(range(0x3000, 0x3100)) | set(range(0xFF01, 0xFF5F)) | text_chars
    faces = []
    cache = ROOT / "build" / "_fonts"
    (game_dir / "fonts").mkdir(exist_ok=True)
    for url in links:
        for family, weights in parse_google_fonts(url):
            for w in weights:
                path, variable = download_font(family, w, cache)
                if not path:
                    fail(f"フォント {family} {w} を google/fonts で見つけられません")
                font = TTFont(path)
                if variable:
                    from fontTools.varLib import instancer
                    font = instancer.instantiateVariableFont(font, {"wght": w})
                opts = subset.Options()
                opts.layout_features = ["*"]
                opts.name_IDs = ["*"]
                opts.name_languages = ["*"]
                opts.notdef_outline = True
                opts.hinting = False
                sub = subset.Subsetter(opts)
                sub.populate(unicodes=codepoints)
                sub.subset(font)
                out_name = f"{family.replace(' ', '')}-{w}.ttf"
                font.save(game_dir / "fonts" / out_name)
                kb = (game_dir / "fonts" / out_name).stat().st_size // 1024
                # フォントのライセンスの文もいっしょに入れる（OFL は配るときに文を添える決まり）
                lic = path.name.split("-", 1)[0]
                lic_file = {"ofl": "OFL.txt", "apache": "LICENSE.txt", "ufl": "UFL.txt"}[lic]
                lic_dest = game_dir / "fonts" / f"{family.replace(' ', '')}-{lic_file}"
                if not lic_dest.exists():
                    folder = family.lower().replace(" ", "")
                    with urllib.request.urlopen(f"https://raw.githubusercontent.com/google/fonts/main/{lic}/{folder}/{lic_file}", timeout=60) as r:
                        lic_dest.write_bytes(r.read())
                faces.append(f'@font-face{{font-family:"{family}";font-style:normal;font-weight:{w};'
                             f'font-display:swap;src:url("fonts/{out_name}") format("truetype")}}')
                say(f"フォント同梱: {family} {w}（{kb} KB）")
    html = GF_PRECONNECT.sub("", html)
    html = GF_LINK.sub(lambda m: "<style>" + "".join(faces) + "</style>\n" if faces else "", html, count=1)
    html = GF_LINK.sub("", html)
    return html


def inject_skin(html, cfg, game_dir):
    """app.json の skin があれば、skins/<名前>/skin.json の中身を window.APP_SKIN でゲームに渡す
    （アプリの中のページはファイルなので、ゲームが skin.json を fetch で読めないため）"""
    name = cfg.get("skin")
    if not name:
        return html
    if not re.fullmatch(r"[a-z0-9-]{1,24}", name):
        fail(f"skin の名前に使えない文字があります: {name}")
    skin_json = game_dir / "skins" / name / "skin.json"
    if not skin_json.exists():
        fail(f"skins/{name}/skin.json がありません（app.json の game.extra に skins/{name} を入れる）")
    data = json.dumps({"name": name, "cfg": json.loads(skin_json.read_text(encoding="utf-8"))}, ensure_ascii=False)
    if "<head>" not in html:
        fail("ゲームの HTML に <head> がありません")
    say(f"スキン: {name}")
    return html.replace("<head>", f"<head>\n<script>window.APP_SKIN={data};</script>", 1)


# ---------------------------------------------------------------- 3. オフラインの点検
ONLINE_PATTERNS = [
    (r'<(?:script|img|audio|video|source|iframe|embed|track|object)\b[^>]*\b(?:src|data)\s*=\s*["\']?(?:https?:)?//', "src"),
    (r'<link\b[^>]*\bhref\s*=\s*["\']?(?:https?:)?//', "link"),
    (r'url\(\s*["\']?(?:https?:)?//', "CSS url()"),
    (r'@import\s+(?:url\()?\s*["\']?(?:https?:)?//', "@import"),
    (r'\bfetch\(\s*["\'`](?:https?:)?//', "fetch"),
    (r'\.open\(\s*["\'][A-Za-z]+["\']\s*,\s*["\'`](?:https?:)?//', "XMLHttpRequest"),
    (r'\bimport\(\s*["\'`](?:https?:)?//', "import()"),
]


def offline_check(game_dir, allowed):
    problems = []
    for f in game_dir.rglob("*"):
        if f.suffix.lower() not in (".html", ".htm", ".js", ".css", ".json"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for pat, kind in ONLINE_PATTERNS:
            for m in re.finditer(pat, text, re.I):
                snippet = text[m.start():m.end() + 60].split("\n")[0]
                if not any(a in snippet for a in allowed):
                    problems.append(f"{f.name}: {kind}: {snippet[:120]}")
    links = len(re.findall(r'<a\b[^>]*href=["\']https?://', (game_dir / "index.html").read_text(encoding="utf-8")))
    if problems:
        for p in problems:
            print(f"::error::ネットにつなぐ読み込み {p}")
        fail("オフラインで動かない読み込みがあります（app.json の allowOnline で許可もできます）")
    say(f"オフラインの点検: OK（外へのリンク {links} 個は Safari で開く）")


# ---------------------------------------------------------------- 4. Xcode プロジェクト
def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def localized_name(cfg, lang):
    names = cfg["name"]
    return names.get(lang) or names.get(lang.split("-")[0]) or names["en"]


def make_project(app, cfg, proj, build_number):
    shutil.copytree(ROOT / "shell" / "Sources", proj / "Sources")
    shutil.copy2(ROOT / "shell" / "PrivacyInfo.xcprivacy", proj / "PrivacyInfo.xcprivacy")

    # アイコン（透明なしの 1024px が必須）と色
    from PIL import Image
    assets = proj / "Assets.xcassets"
    write_json(assets / "Contents.json", {"info": {"author": "xcode", "version": 1}})
    icon = Image.open(ROOT / "apps" / app / cfg.get("icon", "icon.png"))
    bg = hex_to_rgb(cfg.get("background", "#FFFFFF"))
    if icon.mode in ("RGBA", "LA", "P"):
        icon = icon.convert("RGBA")
        flat = Image.new("RGB", icon.size, bg)
        flat.paste(icon, mask=icon.getchannel("A"))
        icon = flat
    icon = icon.convert("RGB").resize((1024, 1024), Image.LANCZOS)
    (assets / "AppIcon.appiconset").mkdir(parents=True)
    icon.save(assets / "AppIcon.appiconset" / "icon-1024.png")
    write_json(assets / "AppIcon.appiconset" / "Contents.json", {
        "images": [{"filename": "icon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}],
        "info": {"author": "xcode", "version": 1}})
    r, g, b = bg
    write_json(assets / "GameBackground.colorset" / "Contents.json", {
        "colors": [{"idiom": "universal", "color": {"color-space": "srgb", "components": {
            "red": f"0x{r:02X}", "green": f"0x{g:02X}", "blue": f"0x{b:02X}", "alpha": "1.000"}}}],
        "info": {"author": "xcode", "version": 1}})

    # ホーム画面の名前を言語ごとに（App Store の「言語」の欄にも出る）
    langs = cfg.get("languages", ["en"])
    for lang in langs:
        name = localized_name(cfg, lang).replace('"', '\\"')
        f = proj / "Resources" / f"{lang}.lproj" / "InfoPlist.strings"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f'"CFBundleDisplayName" = "{name}";\n"CFBundleName" = "{name}";\n', encoding="utf-8")

    devices = cfg.get("devices", ["iphone", "ipad"])
    family = ",".join(x for x, d in (("1", "iphone"), ("2", "ipad")) if d in devices)
    iphone_orient = {"portrait": ["UIInterfaceOrientationPortrait"],
                     "landscape": ["UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"],
                     "all": ALL_ORIENTATIONS[:1] + ALL_ORIENTATIONS[2:]}[cfg.get("iphoneOrientation", "portrait")]
    min_ios = cfg.get("minIOS", "16.0")
    product = re.sub(r"[^A-Za-z0-9]", "", cfg["name"]["en"]) or "Game"
    bundle_id = cfg["bundleId"]

    info = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": cfg["name"]["en"],
        "CFBundleExecutable": "$(EXECUTABLE_NAME)",
        "CFBundleIdentifier": "$(PRODUCT_BUNDLE_IDENTIFIER)",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "$(PRODUCT_NAME)",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "$(MARKETING_VERSION)",
        "CFBundleVersion": "$(CURRENT_PROJECT_VERSION)",
        "CFBundleLocalizations": langs,
        "LSRequiresIPhoneOS": True,
        "LSApplicationCategoryType": cfg.get("category", "public.app-category.games"),
        "ITSAppUsesNonExemptEncryption": False,
        "UILaunchScreen": {"UIColorName": "GameBackground"},
        "UIStatusBarHidden": True,
        "UIViewControllerBasedStatusBarAppearance": False,
        "UIApplicationSceneManifest": {"UIApplicationSupportsMultipleScenes": False},
        "UISupportedInterfaceOrientations": iphone_orient,
        "UISupportedInterfaceOrientations~ipad": ALL_ORIENTATIONS,
        "GameEntry": "Game/index.html",
        "GameLangGlobals": cfg.get("langGlobals", []),
        "GameSafeArea": cfg.get("safeArea", "respect"),
    }
    # zoom "game"：ゲームが自分で大きさを合わせる（APP_PLATFORM='ios' を見る）。アプリはページを拡大しない
    if cfg.get("fitSize") and cfg.get("zoom", "page") != "game":
        info["GameFitSize"] = cfg["fitSize"]

    spec = {
        "name": "App",
        "options": {"deploymentTarget": {"iOS": min_ios}, "developmentLanguage": "en",
                    "createIntermediateGroups": True},
        "settings": {"base": {"MARKETING_VERSION": cfg["version"], "CURRENT_PROJECT_VERSION": str(build_number),
                              "SWIFT_VERSION": "5.0", "LOCALIZATION_PREFERS_STRING_CATALOGS": "NO"}},
        "targets": {
            "App": {
                "type": "application", "platform": "iOS", "deploymentTarget": min_ios,
                "sources": [{"path": "Sources"},
                            {"path": "Game", "type": "folder", "buildPhase": "resources"},
                            {"path": "Resources"},
                            {"path": "Assets.xcassets"},
                            {"path": "PrivacyInfo.xcprivacy", "buildPhase": "resources"}],
                "info": {"path": "Info.plist", "properties": info},
                "settings": {"base": {
                    "PRODUCT_BUNDLE_IDENTIFIER": bundle_id, "PRODUCT_NAME": product,
                    "TARGETED_DEVICE_FAMILY": family, "ASSETCATALOG_COMPILER_APPICON_NAME": "AppIcon",
                    "CODE_SIGN_STYLE": "Automatic", "ENABLE_PREVIEWS": "NO",
                    "SUPPORTS_MACCATALYST": "NO", "SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD": "NO",
                    "SUPPORTS_XR_DESIGNED_FOR_IPHONE_IPAD": "NO"}},
            },
        },
        "schemes": {"App": {"build": {"targets": {"App": "all"}}, "archive": {"config": "Release"}}},
    }
    write_json(proj / "project.json", spec)
    return product


# ---------------------------------------------------------------- 5. ストアの文
def make_metadata(app, cfg, out):
    meta = out / "fastlane" / "metadata"
    store = ROOT / "apps" / app / "store"
    pages_file = ROOT / "apps" / app / "pages.json"
    pages = json.loads(pages_file.read_text(encoding="utf-8")) if pages_file.exists() else {}
    for loc_dir in sorted(p for p in store.iterdir() if p.is_dir()):
        dest = meta / loc_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        for f in loc_dir.glob("*.txt"):
            text = f.read_text(encoding="utf-8").strip()
            limit = STORE_LIMITS.get(f.name)
            if limit and len(text) > limit:
                fail(f"{loc_dir.name}/{f.name} が {len(text)} 文字です（上限 {limit}）")
            if f.name == "keywords.txt" and (" ," in text or ", " in text):
                fail(f"{loc_dir.name}/keywords.txt はカンマのまわりに空白を入れない")
            (dest / f.name).write_text(text + "\n", encoding="utf-8")
        page_lang = "ja" if loc_dir.name.startswith("ja") else "en"
        (dest / "privacy_url.txt").write_text(f"{PAGES_BASE}/{app}/privacy.html#{page_lang}\n", encoding="utf-8")
        (dest / "support_url.txt").write_text(f"{PAGES_BASE}/{app}/#{page_lang}\n", encoding="utf-8")
        # マーケティング URL＝工房のページ。AdMob はこのドメインの直下の app-ads.txt を見る（asobi-talk.com/app-ads.txt）
        if pages.get("workshopUrl"):
            (dest / "marketing_url.txt").write_text(pages["workshopUrl"] + "\n", encoding="utf-8")
    s = cfg.get("store", {})
    (meta / "copyright.txt").write_text(s.get("copyright", "") + "\n", encoding="utf-8")
    (meta / "primary_category.txt").write_text(s.get("primaryCategory", "GAMES") + "\n", encoding="utf-8")
    subs = s.get("subcategories", [])
    for i, key in enumerate(["primary_first_sub_category.txt", "primary_second_sub_category.txt"]):
        if i < len(subs):
            (meta / key).write_text(subs[i] + "\n", encoding="utf-8")
    say(f"ストアの文: {', '.join(sorted(p.name for p in meta.iterdir() if p.is_dir()))}")


# ----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("--ref", default="")
    ap.add_argument("--build-number", default="1")
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a.app):
        fail("アプリの名前は apps/ の中のフォルダ名（英小文字・数字・-）")
    cfg_path = ROOT / "apps" / a.app / "app.json"
    if not cfg_path.exists():
        fail(f"{cfg_path} がありません")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    ref = a.ref or cfg["game"]["ref"]

    out = ROOT / "build" / a.app
    shutil.rmtree(out, ignore_errors=True)
    proj = out / "project"
    game_dir = proj / "Game"

    sha = fetch_game(a.app, cfg, ref, game_dir)
    index = game_dir / "index.html"
    html = index.read_text(encoding="utf-8")
    html = localize_fonts(html, game_dir)
    html = inject_skin(html, cfg, game_dir)
    index.write_text(html, encoding="utf-8")
    offline_check(game_dir, cfg.get("allowOnline", []))
    product = make_project(a.app, cfg, proj, a.build_number)
    make_metadata(a.app, cfg, out)

    env = {"BUNDLE_ID": cfg["bundleId"], "APP_VERSION": cfg["version"], "PRODUCT_NAME": product,
           "GAME_SHA": sha, "APP_NAME_EN": cfg["name"]["en"]}
    (out / "app.env").write_text("".join(f"{k}={shlex.quote(v)}\n" for k, v in env.items()), encoding="utf-8")
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
            f.write("".join(f"{k}={v}\n" for k, v in env.items()))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"### {cfg['name']['ja'] if 'ja' in cfg['name'] else cfg['name']['en']} {cfg['version']}\n")
            f.write("".join(f"- {n}\n" for n in notes))
    say(f"できあがり: build/{a.app}/project（{cfg['bundleId']} {cfg['version']} ビルド {a.build_number}）")


if __name__ == "__main__":
    main()
