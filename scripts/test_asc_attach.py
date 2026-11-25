#!/usr/bin/env python3
"""asc.py attach のテスト（本物の App Store Connect には送らない。API とアップロード先をにせものにする）

  python3 scripts/test_asc_attach.py
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

    def __init__(self, old=None, detail=True, states=None):
        self.log = []
        self.old = old or []          # 前からある添付 [{id, fileName, fileSize, state}]
        self.detail = detail          # App Review に関する情報がもうあるか
        self.states = states or [{"versionString": "1.0", "appStoreState": "READY_FOR_SALE"},
                                 {"versionString": "1.1", "appStoreState": "PREPARE_FOR_SUBMISSION"}]
        self.n = 0

    def call(self, method, path, body=None, soft=False):
        self.log.append((method, path, body))
        if path.startswith("/apps?"):
            return {"data": [{"id": "A1", "attributes": {"bundleId": "com.example.game"}}]}
        if path.startswith("/apps/A1/appStoreVersions"):
            return {"data": [{"id": f"V{i}", "attributes": a} for i, a in enumerate(self.states)]}
        if path.endswith("/appStoreReviewDetail"):
            if not self.detail:
                raise asc.ApiError(404, "not found")
            return {"data": {"id": "D1"}}
        if method == "POST" and path == "/appStoreReviewDetails":
            return {"data": {"id": "D2"}}
        if "/appStoreReviewAttachments?" in path:
            return {"data": [{"id": o["id"], "attributes": {"fileName": o["fileName"], "fileSize": o["fileSize"],
                                                           "assetDeliveryState": {"state": o["state"]}}} for o in self.old]}
        if method == "POST" and path == "/appStoreReviewAttachments":
            self.n += 1
            size = body["data"]["attributes"]["fileSize"]
            half = size // 2
            return {"data": {"id": f"N{self.n}", "attributes": {"uploadOperations": [
                {"method": "PUT", "url": f"https://upload.example/{self.n}/a", "offset": 0, "length": half, "requestHeaders": []},
                {"method": "PUT", "url": f"https://upload.example/{self.n}/b", "offset": half, "length": size - half,
                 "requestHeaders": []}]}}}
        if method == "GET" and path.startswith("/appStoreReviewAttachments/"):
            return {"data": {"attributes": {"assetDeliveryState": {"state": "COMPLETE"}}}}
        return {"data": {}}


class AttachTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        Path(self.root, "apps/game").mkdir(parents=True)
        Path(self.root, "apps/game/app.json").write_text(json.dumps({"bundleId": "com.example.game", "version": "1.1"}))
        self.media = Path(self.root, "media")
        self.media.mkdir()
        Path(self.media, "review.mp4").write_bytes(b"0123456789")
        Path(self.media, "memo.txt").write_bytes(b"skip me")
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.puts = []
        self.real = (asc.call, asc.put_bytes)
        asc.put_bytes = lambda op, data: self.puts.append((op["url"], data[op["offset"]:op["offset"] + op["length"]]))

    def tearDown(self):
        asc.call, asc.put_bytes = self.real
        os.chdir(self.cwd)

    def test_uploads_to_the_editable_version(self):
        fake = FakeASC()
        asc.call = fake.call
        self.assertEqual(asc.attach("game", str(self.media), wait=0), 1)
        post = next(b for m, p, b in fake.log if m == "POST" and p == "/appStoreReviewAttachments")
        self.assertEqual(post["data"]["attributes"], {"fileName": "review.mp4", "fileSize": 10})
        self.assertEqual(post["data"]["relationships"]["appStoreReviewDetail"]["data"]["id"], "D1")
        self.assertTrue(any(p == "/apps/A1/appStoreVersions?filter[platform]=IOS&limit=20" for _, p, _ in fake.log))
        self.assertEqual(b"".join(d for _, d in self.puts), b"0123456789")   # 2つに分けて全部送る
        patch = next(b for m, p, b in fake.log if m == "PATCH")
        self.assertEqual(patch["data"]["attributes"]["sourceFileChecksum"], hashlib.md5(b"0123456789").hexdigest())
        self.assertFalse(any(m == "DELETE" for m, _, _ in fake.log))        # memo.txt は送らない・ほかは消さない

    def test_replaces_same_name_after_upload(self):
        fake = FakeASC(old=[{"id": "OLD", "fileName": "review.mp4", "fileSize": 99, "state": "COMPLETE"},
                            {"id": "MINE", "fileName": "screen.mov", "fileSize": 5, "state": "COMPLETE"}])
        asc.call = fake.call
        self.assertEqual(asc.attach("game", str(self.media), wait=0), 1)
        kinds = [(m, p) for m, p, _ in fake.log if m in ("POST", "DELETE")]
        self.assertEqual(kinds, [("POST", "/appStoreReviewAttachments"), ("DELETE", "/appStoreReviewAttachments/OLD")])

    def test_skips_when_same_file_is_there(self):
        fake = FakeASC(old=[{"id": "OLD", "fileName": "review.mp4", "fileSize": 10, "state": "COMPLETE"}])
        asc.call = fake.call
        self.assertEqual(asc.attach("game", str(self.media), wait=0), 0)
        self.assertFalse(any(m in ("POST", "DELETE", "PATCH") for m, _, _ in fake.log))

    def test_makes_review_detail_when_missing(self):
        fake = FakeASC(detail=False)
        asc.call = fake.call
        asc.attach("game", str(self.media), wait=0)
        made = next(b for m, p, b in fake.log if m == "POST" and p == "/appStoreReviewDetails")
        self.assertEqual(made["data"]["relationships"]["appStoreVersion"]["data"]["id"], "V1")
        post = next(b for m, p, b in fake.log if m == "POST" and p == "/appStoreReviewAttachments")
        self.assertEqual(post["data"]["relationships"]["appStoreReviewDetail"]["data"]["id"], "D2")

    def test_stops_when_version_is_in_review(self):
        fake = FakeASC(states=[{"versionString": "1.1", "appStoreState": "WAITING_FOR_REVIEW"}])
        asc.call = fake.call
        with self.assertRaises(SystemExit):
            asc.attach("game", str(self.media), wait=0)
        self.assertFalse(any(m == "POST" for m, _, _ in fake.log))

    def test_nothing_to_attach(self):
        fake = FakeASC()
        asc.call = fake.call
        self.assertEqual(asc.attach("game", str(Path(self.root, "none")), wait=0), 0)
        self.assertEqual(fake.log, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
