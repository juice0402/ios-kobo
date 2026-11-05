#!/usr/bin/env python3
"""App Store に載せるページ（サポートとプライバシーポリシー）を docs/ に作る。GitHub Pages（main の /docs）で公開。

  python3 scripts/pages.py

apps/<app>/app.json と apps/<app>/pages.json から、アプリごとに
  docs/<app>/index.html    … サポート（App Store の「サポート URL」）
  docs/<app>/privacy.html  … プライバシーポリシー
を日本語と英語で1ページずつ作る。アプリを足したら動かして、docs/ もコミットする。
"""
import html
import json
import shutil
import urllib.parse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FORM = ("https://docs.google.com/forms/d/e/1FAIpQLSdAYN3cjrLkbbFywxHmCS7bqLFtDN0VmlO3NuTVPqKpaFj6Dg/viewform"
        "?usp=pp_url&entry.1872798598=" + urllib.parse.quote("あそびトーク"))
MAKER = {"ja": "はんぺん（あそびトーク ゲーム工房）", "en": "Hanpen (asobi-talk Game Workshop)"}

CSS = """
:root{--ink:#26282b;--sub:#5d6166;--line:#d9dcd6;--paper:#fbfbf8;--link:#1f4e8c}
@media (prefers-color-scheme:dark){:root{--ink:#e8e8e4;--sub:#a9ada8;--line:#3a3d40;--paper:#17191b;--link:#8db4ea}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.75 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP","Segoe UI",sans-serif;-webkit-text-size-adjust:100%}
main{max-width:1040px;margin:0 auto;padding:20px 16px 48px}
a{color:var(--link)}
header{display:flex;align-items:center;gap:14px;padding-bottom:14px;border-bottom:1px solid var(--line)}
header img{width:64px;height:64px;border-radius:14px;flex:none}
header h1{font-size:22px;line-height:1.3;margin:0}
header p{margin:2px 0 0;color:var(--sub);font-size:14px}
nav{font-size:14px;margin:10px 0 0}
nav a{margin-right:14px}
section{padding:18px 0 6px;border-bottom:1px solid var(--line)}
h2{font-size:18px;margin:0 0 6px}
h3{font-size:15px;margin:16px 0 2px}
p,li{margin:0 0 10px}
ul{padding-left:1.2em}
.cols{display:grid;gap:0 40px}
@media (min-width:960px){.cols{grid-template-columns:1fr 1fr}.cols>section{border-bottom:0}}
footer{margin-top:18px;font-size:13px;color:var(--sub)}
"""


def esc(s):
    return html.escape(s, quote=True)


def page(lang_title, body, title, desc):
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="icon" href="icon.png">
<style>{CSS}</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def header(cfg, sub):
    return (f'<header><img src="icon.png" width="64" height="64" alt="">'
            f'<div><h1>{esc(cfg["name"]["ja"])} <span lang="en">/ {esc(cfg["name"]["en"])}</span></h1>'
            f'<p>{esc(sub)}</p></div></header>'
            '<nav><a href="#ja">日本語</a><a href="#en" lang="en">English</a></nav>')


def support(app, cfg, pg):
    parts = [header(cfg, "サポート / Support")]
    for lang in ("ja", "en"):
        faq = "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in pg["faq"][lang])
        if lang == "ja":
            contact = ("<p>不具合やご意見は、お問い合わせフォームから送ってください。アプリの名前と、使っている機種・iOS のバージョンを書いてもらえると、早く直せます。</p>"
                       f'<p><a href="{esc(FORM)}">お問い合わせフォーム</a></p>')
            maker = (f'<p>作った人：{esc(MAKER["ja"])}。ブラウザ版は<a href="{esc(pg["workshopUrl"])}">ゲーム工房</a>で遊べます。</p>'
                     '<p><a href="privacy.html#ja">プライバシーポリシー</a></p>')
            h = ("このアプリについて", "お問い合わせ", "よくある質問")
        else:
            contact = ("<p>To report a problem or send feedback, please use the contact form. The form is in Japanese, but you can write in English. "
                       "Telling us the app name, your device and iOS version helps us fix things faster.</p>"
                       f'<p><a href="{esc(FORM)}">Contact form</a></p>')
            maker = (f'<p>Made by {esc(MAKER["en"])}. You can also play it in a browser at the <a href="{esc(pg["workshopUrl"])}">Game Workshop</a>.</p>'
                     '<p><a href="privacy.html#en">Privacy Policy</a></p>')
            h = ("About this app", "Contact", "FAQ")
        parts.append(
            f'<div class="cols" id="{lang}" lang="{lang}">'
            f'<div><section><h2>{h[0]}</h2><p>{esc(pg["about"][lang])}</p>{maker}</section>'
            f'<section><h2>{h[1]}</h2>{contact}</section></div>'
            f'<section><h2>{h[2]}</h2>{faq}</section></div>')
    desc = f'{cfg["name"]["ja"]}（iPhone・iPad）のサポートとお問い合わせ。'
    return page("", "\n".join(parts), f'{cfg["name"]["ja"]} サポート', desc)


def privacy(app, cfg, pg):
    stored = cfg.get("privacy", {}).get("stored", {})
    date = pg.get("privacyDate", "")
    ja = f"""<section id="ja" lang="ja"><h2>プライバシーポリシー</h2>
<p>{esc(cfg["name"]["ja"])}（以下「このアプリ」）は、遊ぶ人の個人情報を集めません。アカウントの登録、広告、アクセス解析、トラッキングはありません。ゲームは端末の中だけで動き、ネットへの通信はしません。</p>
<h3>端末に保存するもの</h3>
<p>{esc(stored.get("ja", "ゲームの設定と記録"))}を、この端末の中だけに保存します。外へは送りません。アプリを削除すると消えます。</p>
<h3>お問い合わせ</h3>
<p>サポートのページのお問い合わせフォームは Google フォームを使っています。受け取るのは、書いてもらった名前・メールアドレス・内容だけで、どれも書いた分だけです。返事と不具合の直しのためだけに使います。Google フォームでの扱いは Google のプライバシーポリシーに従います。</p>
<h3>子どもの利用</h3>
<p>年齢にかかわらず、このアプリが個人情報を集めることはありません。</p>
<h3>変更</h3>
<p>このポリシーを変えるときは、このページでお知らせします。</p>
<p>運営：{esc(MAKER["ja"])}<br>制定：{esc(date)}</p></section>"""
    en = f"""<section id="en" lang="en"><h2>Privacy Policy</h2>
<p>{esc(cfg["name"]["en"])} ("the app") does not collect any personal information. There are no accounts, ads, analytics or tracking. The game runs entirely on your device and does not connect to the internet.</p>
<h3>Data stored on your device</h3>
<p>The app saves {esc(stored.get("en", "game settings and records"))} on this device only. This data is never sent anywhere and is removed when you delete the app.</p>
<h3>Contact</h3>
<p>The contact form on the support page uses Google Forms. We receive only what you choose to enter (name, email address and message) and use it only to reply and fix problems. Google's privacy policy applies to Google Forms.</p>
<h3>Children</h3>
<p>The app does not collect personal information from anyone, including children.</p>
<h3>Changes</h3>
<p>If this policy changes, we will update this page.</p>
<p>Operator: {esc(MAKER["en"])}<br>Effective: {esc(date)}</p></section>"""
    body = header(cfg, "プライバシーポリシー / Privacy Policy") + ja + en + '<footer><a href="./">サポート / Support</a></footer>'
    return page("", body, f'{cfg["name"]["ja"]} プライバシーポリシー',
                f'{cfg["name"]["ja"]}（iPhone・iPad）のプライバシーポリシー。個人情報は集めません。')


def main():
    shutil.rmtree(DOCS, ignore_errors=True)
    DOCS.mkdir()
    (DOCS / ".nojekyll").write_text("")
    items = []
    for d in sorted(p for p in (ROOT / "apps").iterdir() if (p / "pages.json").exists()):
        cfg = json.loads((d / "app.json").read_text(encoding="utf-8"))
        pg = json.loads((d / "pages.json").read_text(encoding="utf-8"))
        out = DOCS / d.name
        out.mkdir()
        Image.open(d / cfg.get("icon", "icon.png")).convert("RGB").resize((128, 128), Image.LANCZOS).save(out / "icon.png", optimize=True)
        (out / "index.html").write_text(support(d.name, cfg, pg), encoding="utf-8")
        (out / "privacy.html").write_text(privacy(d.name, cfg, pg), encoding="utf-8")
        items.append(f'<li><a href="{d.name}/">{esc(cfg["name"]["ja"])} / {esc(cfg["name"]["en"])}</a></li>')
        print(f"docs/{d.name}/")
    body = ('<header><div><h1>あそびトーク ゲーム工房のアプリ</h1><p>Apps from the asobi-talk Game Workshop</p></div></header>'
            f'<section><ul>{"".join(items)}</ul></section>')
    (DOCS / "index.html").write_text(page("", body, "ゲーム工房のアプリ", "あそびトーク ゲーム工房の iPhone・iPad アプリ。"), encoding="utf-8")


if __name__ == "__main__":
    main()
