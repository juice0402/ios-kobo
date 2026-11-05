#!/usr/bin/env python3
"""App Store Connect API の小さな道具（鍵は GitHub の Secrets から環境変数で受け取る）。

  python3 scripts/asc.py setup      → バンドル ID を登録（なければ）し、アプリができているか調べる
  python3 scripts/asc.py key-json F → fastlane 用の鍵ファイルを F に書く

環境変数: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8, BUNDLE_ID, APP_NAME_EN
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import jwt  # PyJWT（cryptography と一緒に入れる）

API = "https://api.appstoreconnect.apple.com/v1"


def env(name):
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"::error::{name} がありません（GitHub の Secrets を確かめてください）")
    return v


def private_key():
    key = env("ASC_KEY_P8").replace("\\n", "\n")
    if "BEGIN PRIVATE KEY" not in key:
        sys.exit("::error::ASC_KEY_P8 は .p8 ファイルの中身を -----BEGIN PRIVATE KEY----- から丸ごと貼ってください")
    return key


def token():
    now = int(time.time())
    return jwt.encode({"iss": env("ASC_ISSUER_ID"), "iat": now, "exp": now + 1000, "aud": "appstoreconnect-v1"},
                      private_key(), algorithm="ES256", headers={"kid": env("ASC_KEY_ID"), "typ": "JWT"})


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:600]
        sys.exit(f"::error::App Store Connect API {method} {path} → {e.code} {detail}")


def output(key, value):
    print(f"{key}={value}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{key}={value}\n")


def setup():
    bundle = env("BUNDLE_ID")
    q = urllib.parse.urlencode({"filter[identifier]": bundle, "limit": 200})
    found = [d for d in call("GET", f"/bundleIds?{q}").get("data", []) if d["attributes"]["identifier"] == bundle]
    if found:
        print(f"バンドル ID {bundle}: 登録ずみ")
    else:
        name = "".join(c for c in env("APP_NAME_EN") if c.isalnum() or c == " ")[:60] or "Game"
        call("POST", "/bundleIds", {"data": {"type": "bundleIds", "attributes": {
            "identifier": bundle, "name": name, "platform": "IOS"}}})
        print(f"バンドル ID {bundle}: 登録しました")
    q = urllib.parse.urlencode({"filter[bundleId]": bundle})
    apps = [d for d in call("GET", f"/apps?{q}").get("data", []) if d["attributes"]["bundleId"] == bundle]
    if apps:
        print(f"App Store Connect のアプリ: あり（{apps[0]['attributes']['name']}）")
        output("has_app", "true")
    else:
        print(f"::warning::App Store Connect にまだアプリがありません。「新規 App」で {bundle} をえらんで作ってください")
        output("has_app", "false")


def key_json(path):
    with open(path, "w") as f:
        json.dump({"key_id": env("ASC_KEY_ID"), "issuer_id": env("ASC_ISSUER_ID"),
                   "key": private_key(), "in_house": False}, f)
    os.chmod(path, 0o600)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "setup":
        setup()
    elif len(sys.argv) >= 3 and sys.argv[1] == "key-json":
        key_json(sys.argv[2])
    else:
        sys.exit(__doc__)
