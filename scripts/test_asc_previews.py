#!/usr/bin/env python3
"""asc.py previews のテスト（本物の App Store Connect には送らない。API とアップロード先をにせものにする）

  python3 scripts/test_asc_previews.py
"""
import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.setdefault("jwt", types.SimpleNamespace(encode=lambda *a, **k: "t"))  # 鍵なしで読めるように
import asc  # noqa: E402


class FakeASC:
    """App Store Connect のにせもの。呼ばれた順に記録し、決まった返事をする"""

    def __init__(self, sets=None, old=None, state="PREPARE_FOR_SUBMISSION"):
        self.log = []
        self.sets = sets or {}      # 言語の id → [previewType]
        self.old = old or []        # 前からある動画の id
        self.state = state
        self.n = 0

    def call(self, method, path, body=None, soft=False):
        self.log.append((method, path, body))
        if path.startswith("/apps?"):
            return {"data": [{"id": "A1", "attributes": {"bundleId": "com.example.game"}}]}
        if path.startswith("/apps/A1/appStoreVersions"):
            return {"data": [{"id": "V0", "attributes": {"appStoreState": "READY_FOR_SALE"}},
                             {"id": "V1", "attributes": {"appStoreState": self.state}}]}
        if path.startswith("/appStoreVersions/V1/appStoreVersionLocalizations"):
            return {"data": [{"id": "L-ja", "attributes": {"locale": "ja"}}, {"id": "L-en", "attributes": {"locale": "en-US"}}]}
        if "/appPreviewSets?" in path:
            loc = path.split("/")[2]
            return {"data": [{"id": f"S-{loc}-{t}", "attributes": {"previewType": t}} for t in self.sets.get(loc, [])]}
        if method == "POST" and path == "/appPreviewSets":
            t = body["data"]["attributes"]["previewType"]
            loc = body["data"]["relationships"]["appStoreVersionLocalization"]["data"]["id"]
            return {"data": {"id": f"S-{loc}-{t}", "attributes": {"previewType": t}}}
        if path.endswith("/appPreviews?limit=10"):
            return {"data": [{"id": i} for i in self.old]}
        if method == "POST" and path == "/appPreviews":
            self.n += 1
            size = body["data"]["attributes"]["fileSize"]
            half = size // 2
            return {"data": {"id": f"P{self.n}", "attributes": {"uploadOperations": [
                {"method": "PUT", "url": f"https://upload.example/{self.n}/a", "offset": 0, "length": half,
                 "requestHeaders": [{"name": "Content-Type", "value": "video/mp4"}]},
                {"method": "PUT", "url": f"https://upload.example/{self.n}/b", "offset": half, "length": size - half,
                 "requestHeaders": [{"name": "Content-Type", "value": "video/mp4"}]}]}}}
        return {"data": {}}


class PreviewUploadTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for rel, data in [("ja/iphone.mp4", b"0123456789"), ("ja/ipad.mp4", b"abcdefgh"), ("en-US/iphone.mp4", b"xyz")]:
            p = Path(self.dir, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        Path(self.dir, "preview.json").write_text(json.dumps(
            {"poster": "00:00:15:06", "videos": ["ja/iphone.mp4", "ja/ipad.mp4", "en-US/iphone.mp4"]}))
        os.environ["BUNDLE_ID"] = "com.example.game"
        self.puts = []
        self.real = (asc.call, asc.put_bytes)
        asc.put_bytes = lambda op, data: self.puts.append((op["url"], data[op["offset"]:op["offset"] + op["length"]]))

    def tearDown(self):
        asc.call, asc.put_bytes = self.real

    def test_sends_each_video_to_its_set(self):
        fake = FakeASC(sets={"L-ja": ["IPHONE_67"]}, old=["OLD1"])
        asc.call = fake.call
        self.assertEqual(asc.previews(self.dir), 3)
        posts = [b for m, p, b in fake.log if m == "POST" and p == "/appPreviewSets"]
        # ja の iPhone の枠はもうある → 作らない。ja の iPad・en-US の iPhone は作る
        self.assertEqual(sorted((b["data"]["relationships"]["appStoreVersionLocalization"]["data"]["id"],
                                 b["data"]["attributes"]["previewType"]) for b in posts),
                         [("L-en", "IPHONE_67"), ("L-ja", "IPAD_PRO_3GEN_129")])
        # 前の動画は消してから入れる（入れかえ）
        self.assertEqual(sum(1 for m, p, _ in fake.log if m == "DELETE" and p == "/appPreviews/OLD1"), 3)
        # バイトは決まった範囲に分けて送り、合わせると元のファイルになる
        self.assertEqual(b"".join(d for u, d in self.puts if u.startswith("https://upload.example/1/")), b"0123456789")
        # 送ったあと、md5 と表紙のコマで「送った」にする
        patches = [b for m, p, b in fake.log if m == "PATCH"]
        self.assertEqual(len(patches), 3)
        self.assertEqual(patches[0]["data"]["attributes"]["sourceFileChecksum"], hashlib.md5(b"0123456789").hexdigest())
        self.assertTrue(all(b["data"]["attributes"]["uploaded"] for b in patches))
        self.assertTrue(all(b["data"]["attributes"]["previewFrameTimeCode"] == "00:00:15:06" for b in patches))
        # 送ったのは直せるバージョン（V1）だけ。公開中のバージョン（V0）はさわらない
        self.assertFalse(any("V0" in p for _, p, _ in fake.log))

    def test_no_editable_version_sends_nothing(self):
        fake = FakeASC(state="WAITING_FOR_REVIEW")
        asc.call = fake.call
        self.assertEqual(asc.previews(self.dir), 0)
        self.assertFalse(any(m in ("POST", "DELETE", "PATCH") for m, _, _ in fake.log))
        self.assertEqual(self.puts, [])

    def test_old_preview_is_deleted_after_the_new_one(self):
        fake = FakeASC(sets={"L-ja": ["IPHONE_67"]}, old=["OLD1"])
        asc.call = fake.call
        asc.previews(self.dir)
        first = [m for m, p, _ in fake.log if (m == "POST" and p == "/appPreviews") or (m == "DELETE")][:2]
        self.assertEqual(first, ["POST", "DELETE"])

    def test_api_error_at_start_is_a_warning(self):
        def broken(method, path, body=None, soft=False):
            if soft:
                raise asc.ApiError(401, "NOT_AUTHORIZED")
            raise SystemExit("::error::401")
        asc.call = broken
        self.assertEqual(asc.previews(self.dir), 0)   # SystemExit も止めずに警告だけ（ジョブを赤くしない）

    def test_failure_is_a_warning_not_a_stop(self):
        fake = FakeASC()
        def boom(method, path, body=None, soft=False):
            if method == "POST" and path == "/appPreviews":
                raise asc.ApiError(409, "STATE_ERROR")
            return fake.call(method, path, body, soft)
        asc.call = boom
        self.assertEqual(asc.previews(self.dir), 0)   # 止まらずに最後まで（3本とも警告）


if __name__ == "__main__":
    unittest.main(verbosity=1)
