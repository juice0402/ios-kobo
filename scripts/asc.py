#!/usr/bin/env python3
"""App Store Connect API の小さな道具（鍵は GitHub の Secrets から環境変数で受け取る）。

  python3 scripts/asc.py setup      → バンドル ID を登録（なければ）し、アプリができているか調べる。
                                      CONTENT_RIGHTS があれば「コンテンツの権利」をその値にする
  python3 scripts/asc.py setup --game-center
                                    → そのうえで Game Center とリーダーボード（LEADERBOARD_ID）を用意する
  python3 scripts/asc.py key-json F → fastlane 用の鍵ファイルを F に書く
  python3 scripts/asc.py previews D → D（build/<app>/previews）のプレビュー動画を、直せるバージョンに送る（前のは入れかえ）

環境変数: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8, BUNDLE_ID, APP_NAME_EN, CONTENT_RIGHTS（空でもよい。--game-center のときは LEADERBOARD_ID も）
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
        set_content_rights(apps[0])
        if game_center:
            # うまくいかなくても TestFlight には送る（警告だけ。App Store Connect の画面でも作れる）
            try:
                setup_game_center(apps[0]["id"])
            except (ApiError, OSError, ValueError, KeyError, TypeError) as e:  # 通信・時間切れ・壊れた返事も警告だけ
                print(f"::warning::Game Center の用意ができませんでした（App Store Connect の画面で作ってください）: {e}")
    else:
        print(f"::warning::App Store Connect にまだアプリがありません。「新規 App」で {bundle} をえらんで作ってください")
        output("has_app", "false")


def set_content_rights(app):
    """app.json の store.thirdPartyContent（prepare.py が CONTENT_RIGHTS にする）を、アプリの contentRightsDeclaration に。
    同じならなにもしない。うまくいかなくても止めない（App Store Connect の画面の「App 情報」でも選べる）"""
    want = os.environ.get("CONTENT_RIGHTS", "")
    if not want:
        return
    if app["attributes"].get("contentRightsDeclaration") == want:
        print(f"コンテンツの権利: {want}（そのまま）")
        return
    try:
        call("PATCH", f"/apps/{app['id']}", {"data": {"type": "apps", "id": app["id"],
                                                      "attributes": {"contentRightsDeclaration": want}}}, soft=True)
        print(f"コンテンツの権利: {want} にしました")
    except (ApiError, OSError, ValueError) as e:
        print(f"::warning::コンテンツの権利を送れませんでした（App Store Connect の「App 情報」で選んでください）: {e}")


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


# ---------------------------------------------------------------- App プレビュー（動画）
# scripts/preview.py が作った build/<app>/previews/<言語>/<機種>.mp4 を、いま直せるバージョンの各言語へ送る。
# fastlane deliver は App プレビューを送れないので、App Store Connect API（appPreviewSets・appPreviews）で送る。
PREVIEW_TYPES = {"iphone": "IPHONE_67", "ipad": "IPAD_PRO_3GEN_129"}   # 6.9/6.7 インチ（886×1920。API の型は IPHONE_67 まで）・13 インチ（1200×1600）
EDITABLE = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED", "INVALID_BINARY"}


def put_bytes(op, data):
    """uploadOperations の1つ分（決まった URL・ヘッダーで、決まった範囲のバイトを送る）"""
    chunk = data[op["offset"]:op["offset"] + op["length"]]
    req = urllib.request.Request(op["url"], method=op.get("method", "PUT"), data=chunk,
                                 headers={h["name"]: h["value"] for h in op.get("requestHeaders", [])})
    with urllib.request.urlopen(req, timeout=300) as r:
        r.read()


def upload_preview(set_id, path, frame_tc):
    import hashlib
    data = open(path, "rb").read()
    made = call("POST", "/appPreviews", {"data": {"type": "appPreviews", "attributes": {
        "fileName": os.path.basename(path), "fileSize": len(data), "mimeType": "video/mp4", "previewFrameTimeCode": frame_tc},
        "relationships": {"appPreviewSet": {"data": {"type": "appPreviewSets", "id": set_id}}}}}, soft=True)["data"]
    for op in made["attributes"].get("uploadOperations") or []:
        put_bytes(op, data)
    call("PATCH", f"/appPreviews/{made['id']}", {"data": {"type": "appPreviews", "id": made["id"], "attributes": {
        "uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest(), "previewFrameTimeCode": frame_tc}}}, soft=True)
    return made["id"]


def previews(folder):
    """folder（build/<app>/previews）の動画を、いま直せるバージョンの同じ言語・同じ機種の枠に送る（前の動画は入れかえる）。
    うまくいかなくても止めない（警告。文とスクショはもう送ってあるので、ジョブを赤くしない。App Store Connect の画面でも入れられる）"""
    try:
        return send_previews(folder)
    except (SystemExit, Exception) as e:  # noqa: BLE001  鍵・通信・API・preview.json のどれで止まっても警告だけ
        print(f"::warning::プレビュー動画を送れませんでした（App Store Connect の画面で入れてください）: {e}")
        return 0


def send_previews(folder):
    info = json.load(open(os.path.join(folder, "preview.json"), encoding="utf-8"))
    bundle = env("BUNDLE_ID")
    q = urllib.parse.urlencode({"filter[bundleId]": bundle})
    apps = [d for d in call("GET", f"/apps?{q}", soft=True).get("data", []) if d["attributes"]["bundleId"] == bundle]
    if not apps:
        print(f"::warning::App Store Connect にアプリ {bundle} がないので、プレビュー動画は送りません")
        return 0
    versions = call("GET", f"/apps/{apps[0]['id']}/appStoreVersions?filter[platform]=IOS&limit=20", soft=True).get("data", [])
    ver = next((v for v in versions if v["attributes"].get("appStoreState") in EDITABLE), None)
    if not ver:
        print("::warning::直せるバージョン（提出の準備中など）がないので、プレビュー動画は送りません")
        return 0
    locs = {l["attributes"]["locale"]: l["id"] for l in
            call("GET", f"/appStoreVersions/{ver['id']}/appStoreVersionLocalizations?limit=50", soft=True).get("data", [])}
    sent = 0
    for rel in info["videos"]:
        lang, name = rel.split("/")
        kind = name.rsplit(".", 1)[0]
        loc = locs.get(lang)
        if not loc or kind not in PREVIEW_TYPES:
            print(f"::warning::{rel}: バージョンに {lang} がない（または知らない機種）ので送りません")
            continue
        try:
            sets = call("GET", f"/appStoreVersionLocalizations/{loc}/appPreviewSets?limit=50", soft=True).get("data", [])
            ps = next((s for s in sets if s["attributes"].get("previewType") == PREVIEW_TYPES[kind]), None)
            if not ps:
                ps = call("POST", "/appPreviewSets", {"data": {"type": "appPreviewSets",
                          "attributes": {"previewType": PREVIEW_TYPES[kind]},
                          "relationships": {"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": loc}}}}},
                          soft=True)["data"]
            old = [o["id"] for o in call("GET", f"/appPreviewSets/{ps['id']}/appPreviews?limit=10", soft=True).get("data", [])]
            # 新しい動画を入れてから前のを消す（入れるのに失敗しても、前の動画は残る）。1つの枠は3本までなので、3本あれば先に1本だけ消す
            if len(old) >= 3:
                call("DELETE", f"/appPreviews/{old.pop()}", soft=True)
            upload_preview(ps["id"], os.path.join(folder, rel), info.get("poster", "00:00:05:00"))
            for oid in old:
                call("DELETE", f"/appPreviews/{oid}", soft=True)
            print(f"プレビュー動画 {rel} → {PREVIEW_TYPES[kind]}（表紙 {info.get('poster')}）")
            sent += 1
        except (ApiError, OSError, ValueError, KeyError, TypeError) as e:
            print(f"::warning::プレビュー動画 {rel} を送れませんでした（App Store Connect の画面で入れてください）: {e}")
    print("::notice::プレビュー動画は App Store Connect で処理が終わるまで（数分〜）「処理中」になる")
    return sent


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
    elif len(sys.argv) >= 3 and sys.argv[1] == "previews":
        previews(sys.argv[2])
    else:
        sys.exit(__doc__)
