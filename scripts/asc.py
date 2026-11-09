#!/usr/bin/env python3
"""App Store Connect API の小さな道具（鍵は GitHub の Secrets から環境変数で受け取る）。

  python3 scripts/asc.py setup      → バンドル ID を登録（なければ）し、アプリができているか調べる
  python3 scripts/asc.py setup --game-center
                                    → そのうえで Game Center とリーダーボード（LEADERBOARD_ID）を用意する
  python3 scripts/asc.py key-json F → fastlane 用の鍵ファイルを F に書く

環境変数: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8, BUNDLE_ID, APP_NAME_EN（--game-center のときは LEADERBOARD_ID も）
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


class ApiError(Exception):
    def __init__(self, code, text):
        super().__init__(f"{code} {text}")
        self.code = code


def call(method, path, body=None, soft=False):
    """soft=True のときは止めずに ApiError を投げる（呼んだ側で警告にする）"""
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:600]
        if soft:
            raise ApiError(e.code, f"{method} {path} → {detail}")
        sys.exit(f"::error::App Store Connect API {method} {path} → {e.code} {detail}")


def output(key, value):
    print(f"{key}={value}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{key}={value}\n")


def setup(game_center=False):
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
        if game_center:
            # うまくいかなくても TestFlight には送る（警告だけ。App Store Connect の画面でも作れる）
            try:
                setup_game_center(apps[0]["id"])
            except (ApiError, urllib.error.URLError, KeyError, TypeError) as e:
                print(f"::warning::Game Center の用意ができませんでした（App Store Connect の画面で作ってください）: {e}")
    else:
        print(f"::warning::App Store Connect にまだアプリがありません。「新規 App」で {bundle} をえらんで作ってください")
        output("has_app", "false")


# リーダーボードの決まり（全部のゲームで共通：整数・大きい順・最高記録を残す）
LEADERBOARD = {"referenceName": "Best Score", "defaultFormatter": "INTEGER",
               "submissionType": "BEST_SCORE", "scoreSortType": "DESC"}
LEADERBOARD_NAMES = {"ja": "さいこうきろく", "en-US": "Best Score"}


def setup_game_center(app_id):
    """アプリの Game Center（gameCenterDetail）と、LEADERBOARD_ID のリーダーボード・名前（ja・en-US）を、なければ作る"""
    lb_id = env("LEADERBOARD_ID")
    try:
        detail = call("GET", f"/apps/{app_id}/gameCenterDetail", soft=True).get("data")
    except ApiError as e:
        if e.code != 404:
            raise
        detail = None
    if detail:
        print("Game Center: 有効")
    else:
        detail = call("POST", "/gameCenterDetails", {"data": {"type": "gameCenterDetails", "relationships": {
            "app": {"data": {"type": "apps", "id": app_id}}}}}, soft=True)["data"]
        print("Game Center: 有効にしました")

    boards = call("GET", f"/gameCenterDetails/{detail['id']}/gameCenterLeaderboards?limit=200", soft=True).get("data", [])
    board = next((b for b in boards if b["attributes"].get("vendorIdentifier") == lb_id), None)
    if board:
        print(f"リーダーボード {lb_id}: あり")
    else:
        board = call("POST", "/gameCenterLeaderboards", {"data": {
            "type": "gameCenterLeaderboards",
            "attributes": {**LEADERBOARD, "vendorIdentifier": lb_id},
            "relationships": {"gameCenterDetail": {"data": {"type": "gameCenterDetails", "id": detail["id"]}}}}},
            soft=True)["data"]
        print(f"リーダーボード {lb_id}: 作りました")

    have = {l["attributes"].get("locale") for l in
            call("GET", f"/gameCenterLeaderboards/{board['id']}/localizations?limit=50", soft=True).get("data", [])}
    for locale, name in LEADERBOARD_NAMES.items():
        if locale in have:
            continue
        call("POST", "/gameCenterLeaderboardLocalizations", {"data": {
            "type": "gameCenterLeaderboardLocalizations",
            "attributes": {"locale": locale, "name": name},
            "relationships": {"gameCenterLeaderboard": {"data": {"type": "gameCenterLeaderboards", "id": board["id"]}}}}},
            soft=True)
        print(f"リーダーボードの名前 {locale}: {name}")
    print("::notice::Game Center は、App Store Connect のバージョンの画面で「Game Center」をオンにし、リーダーボードを足してから審査に出す")


def key_json(path):
    with open(path, "w") as f:
        json.dump({"key_id": env("ASC_KEY_ID"), "issuer_id": env("ASC_ISSUER_ID"),
                   "key": private_key(), "in_house": False}, f)
    os.chmod(path, 0o600)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "setup":
        setup(game_center="--game-center" in sys.argv[2:])
    elif len(sys.argv) >= 3 and sys.argv[1] == "key-json":
        key_json(sys.argv[2])
    else:
        sys.exit(__doc__)
