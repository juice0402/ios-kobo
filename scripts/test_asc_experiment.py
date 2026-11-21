#!/usr/bin/env python3
"""asc.py experiment のテスト（本物の App Store Connect には送らない。API とアップロード先をにせものにする）

  python3 scripts/test_asc_experiment.py
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

SCENES = ["1-title", "2-play", "3-score"]


class FakeASC:
    """App Store Connect のにせもの。呼ばれた順に記録し、作ったものを覚えて返す"""

    def __init__(self, experiments=None, live=True, treatments=None, locs=None, sets=None, shots=None):
        self.log = []
        self.live = live
        self.experiments = experiments or []   # [{"id", "attributes": {"name", "state", "trafficProportion"}}]
        self.treatments = treatments or {}     # テストの id → [トリートメント]
        self.locs = locs or {}                 # トリートメントの id → [ローカリゼーション]
        self.sets = sets or {}                 # ローカリゼーションの id → [枠]
        self.shots = shots or {}               # 枠の id → [スクショの id]
        self.n = 0

    def new_id(self, head):
        self.n += 1
        return f"{head}{self.n}"

    def call(self, method, path, body=None, soft=False):
        self.log.append((method, path, body))
        attrs = (body or {}).get("data", {}).get("attributes", {})
        rel = (body or {}).get("data", {}).get("relationships", {})
        if path.startswith("/apps?"):
            return {"data": [{"id": "A1", "attributes": {"bundleId": "com.example.game"}}]}
        if path.startswith("/apps/A1/appStoreVersions"):
            states = ["PREPARE_FOR_SUBMISSION"] + (["READY_FOR_SALE"] if self.live else [])
            return {"data": [{"id": f"V{i}", "attributes": {"appStoreState": s, "versionString": f"1.{i}"}}
                             for i, s in enumerate(states)]}
        if path.startswith("/apps/A1/appStoreVersionExperimentsV2"):
            return {"data": self.experiments}
        if method == "POST" and path == "/v2/appStoreVersionExperiments":
            e = {"id": self.new_id("E"), "attributes": {**attrs, "state": "PREPARE_FOR_SUBMISSION"}}
            self.experiments.append(e)
            return {"data": e}
        if path.startswith("/v2/appStoreVersionExperiments/") and path.endswith("/appStoreVersionExperimentTreatments?limit=50"):
            return {"data": self.treatments.get(path.split("/")[3], [])}
        if method == "POST" and path == "/appStoreVersionExperimentTreatments":
            t = {"id": self.new_id("T"), "attributes": attrs}
            self.treatments.setdefault(rel["appStoreVersionExperimentV2"]["data"]["id"], []).append(t)
            return {"data": t}
        if "/appStoreVersionExperimentTreatmentLocalizations?" in path:
            return {"data": self.locs.get(path.split("/")[2], [])}
        if method == "POST" and path == "/appStoreVersionExperimentTreatmentLocalizations":
            return {"data": {"id": f"L-{attrs['locale']}", "attributes": attrs}}
        if path.endswith("/appScreenshotSets?limit=50"):
            return {"data": self.sets.get(path.split("/")[2], [])}
        if method == "POST" and path == "/appScreenshotSets":
            loc = rel["appStoreVersionExperimentTreatmentLocalization"]["data"]["id"]
            return {"data": {"id": f"S-{loc}-{attrs['screenshotDisplayType']}", "attributes": attrs}}
        if path.endswith("/appScreenshots?limit=50"):
            return {"data": [{"id": i} for i in self.shots.get(path.split("/")[2], [])]}
        if method == "POST" and path == "/appScreenshots":
            sid = self.new_id("P")
            size = attrs["fileSize"]
            return {"data": {"id": sid, "attributes": {"uploadOperations": [
                {"method": "PUT", "url": f"https://upload.example/{sid}", "offset": 0, "length": size,
                 "requestHeaders": [{"name": "Content-Type", "value": "image/png"}]}]}}}
        return {"data": {}}


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        Path(self.root, "apps/game").mkdir(parents=True)
        Path(self.root, "apps/game/app.json").write_text(json.dumps(
            {"bundleId": "com.example.game", "screenshots": {"scenes": [{"name": s} for s in SCENES]}}))
        self.shots = Path(self.root, "shots")
        for lang in ("ja", "en-US"):
            for kind in ("iphone", "ipad"):
                for s in reversed(SCENES):   # 書いた順ではなく、場面の順に入れるか
                    p = self.shots / lang / f"{s}-{kind}.png"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(f"{lang}/{s}-{kind}".encode())
        self.cwd = os.getcwd()
        os.chdir(self.root)
        os.environ.pop("GITHUB_OUTPUT", None)
        self.puts = []
        self.real = (asc.call, asc.put_bytes)
        asc.put_bytes = lambda op, data: self.puts.append((op["url"], data[op["offset"]:op["offset"] + op["length"]]))

    def tearDown(self):
        asc.call, asc.put_bytes = self.real
        os.chdir(self.cwd)

    def run_with(self, fake, **kw):
        asc.call = fake.call
        return asc.experiment("game", str(self.shots), **kw)

    def writes(self, fake):
        return [(m, p) for m, p, _ in fake.log if m != "GET"]

    def test_creates_everything_in_order(self):
        fake = FakeASC()
        self.assertEqual(self.run_with(fake), "E1")
        kinds = [p.split("?")[0] for m, p in self.writes(fake) if m == "POST"]
        # テスト → トリートメント → ローカリゼーション → 枠 → スクショ の順
        self.assertEqual(kinds[:4], ["/v2/appStoreVersionExperiments", "/appStoreVersionExperimentTreatments",
                                     "/appStoreVersionExperimentTreatmentLocalizations", "/appScreenshotSets"])
        # 公開中のバージョンを先に見つけてから、テストを作る
        first_post = next(i for i, (m, _, _) in enumerate(fake.log) if m == "POST")
        self.assertTrue(any(p.startswith("/apps/A1/appStoreVersions") for _, p, _ in fake.log[:first_post]))
        body = next(b for m, p, b in fake.log if p == "/v2/appStoreVersionExperiments")["data"]
        self.assertEqual(body["type"], "appStoreVersionExperiments")
        self.assertEqual(body["attributes"], {"name": asc.EXPERIMENT_NAME, "platform": "IOS", "trafficProportion": 50})
        self.assertEqual(body["relationships"]["app"]["data"], {"type": "apps", "id": "A1"})
        tr = next(b for m, p, b in fake.log if p == "/appStoreVersionExperimentTreatments")["data"]
        self.assertEqual(tr["attributes"], {"name": "画用紙と机"})
        self.assertEqual(tr["relationships"]["appStoreVersionExperimentV2"]["data"]["id"], "E1")
        locales = [b["data"]["attributes"]["locale"] for m, p, b in fake.log
                   if p == "/appStoreVersionExperimentTreatmentLocalizations"]
        self.assertEqual(locales, ["ja", "en-US"])
        sets = sorted(b["data"]["attributes"]["screenshotDisplayType"] for m, p, b in fake.log if p == "/appScreenshotSets")
        self.assertEqual(sets, ["APP_IPAD_PRO_3GEN_129", "APP_IPAD_PRO_3GEN_129", "APP_IPHONE_67", "APP_IPHONE_67"])
        # スクショは場面の順・枠ごとに3枚・合わせて12枚
        names = [b["data"]["attributes"]["fileName"] for m, p, b in fake.log if m == "POST" and p == "/appScreenshots"]
        self.assertEqual(len(names), 12)
        self.assertEqual(names[:3], ["1-title-iphone.png", "2-play-iphone.png", "3-score-iphone.png"])
        # バイトはアップロード先へ、md5 で「送った」にする
        self.assertEqual(self.puts[0][1], b"ja/1-title-iphone")
        patch = next(b for m, p, b in fake.log if m == "PATCH")["data"]["attributes"]
        self.assertEqual(patch, {"uploaded": True, "sourceFileChecksum": hashlib.md5(b"ja/1-title-iphone").hexdigest()})
        # 審査への提出・開始はしない（reviewSubmissions もテストの state も送らない）
        self.assertFalse(any("reviewSubmission" in p for _, p, _ in fake.log))
        self.assertFalse(any(m == "PATCH" and "Experiments/" in p for m, p in self.writes(fake)))

    def test_percent_and_name(self):
        fake = FakeASC()
        self.run_with(fake, percent=30, name="ためし")
        body = next(b for m, p, b in fake.log if p == "/v2/appStoreVersionExperiments")["data"]
        self.assertEqual(body["attributes"]["trafficProportion"], 30)
        self.assertEqual(body["attributes"]["name"], "ためし")

    def test_preparing_test_is_replaced(self):
        fake = FakeASC(
            experiments=[{"id": "E9", "attributes": {"name": asc.EXPERIMENT_NAME, "state": "PREPARE_FOR_SUBMISSION",
                                                     "trafficProportion": 20}}],
            treatments={"E9": [{"id": "T9", "attributes": {"name": "画用紙と机"}},
                               {"id": "T8", "attributes": {"name": "ほかの案"}}]},
            locs={"T9": [{"id": "L9", "attributes": {"locale": "ja"}}]},
            sets={"L9": [{"id": "S9", "attributes": {"screenshotDisplayType": "APP_IPHONE_67"}}]},
            shots={"S9": ["OLD1", "OLD2"]})
        self.assertEqual(self.run_with(fake), "E9")
        w = self.writes(fake)
        self.assertNotIn(("POST", "/v2/appStoreVersionExperiments"), w)   # 作らない
        self.assertIn(("PATCH", "/v2/appStoreVersionExperiments/E9"), w)    # 割合を 50 に
        self.assertIn(("DELETE", "/appStoreVersionExperimentTreatments/T8"), w)   # トリートメントは1つに
        self.assertNotIn(("POST", "/appStoreVersionExperimentTreatments"), w)
        # ja はあるので作らず、en-US だけ作る。ja の iPhone の枠もあるので作らない
        locales = [b["data"]["attributes"]["locale"] for m, p, b in fake.log
                   if p == "/appStoreVersionExperimentTreatmentLocalizations"]
        self.assertEqual(locales, ["en-US"])
        self.assertNotIn("S-L9-APP_IPHONE_67", [p for _, p in w])
        # 前のスクショは消してから、新しいのを入れる
        i_del = w.index(("DELETE", "/appScreenshots/OLD1"))
        self.assertIn(("DELETE", "/appScreenshots/OLD2"), w)
        first_up = next(i for i, (m, p) in enumerate(w) if m == "POST" and p == "/appScreenshots")
        self.assertLess(i_del, first_up)
        self.assertEqual(sum(1 for m, p in w if m == "POST" and p == "/appScreenshots"), 12)

    def test_running_or_finished_test_is_not_touched(self):
        for state in ("IN_REVIEW", "ACCEPTED", "COMPLETED", "STOPPED"):
            fake = FakeASC(experiments=[{"id": "E7", "attributes": {"name": asc.EXPERIMENT_NAME, "state": state}}])
            with self.assertRaises(SystemExit):
                self.run_with(fake)
            self.assertEqual(self.writes(fake), [], state)
            self.assertEqual(self.puts, [])

    def test_other_name_running_does_not_block_and_is_untouched(self):
        fake = FakeASC(experiments=[{"id": "E7", "attributes": {"name": "前のテスト", "state": "ACCEPTED"}}])
        self.run_with(fake)
        self.assertFalse(any("E7" in p for _, p in self.writes(fake)))

    def test_no_live_version_stops(self):
        fake = FakeASC(live=False)
        with self.assertRaises(SystemExit):
            self.run_with(fake)
        self.assertEqual(self.writes(fake), [])

    def test_missing_shots_stop_before_any_call(self):
        for p in (self.shots / "en-US").glob("*-ipad.png"):
            p.unlink()
        fake = FakeASC()
        with self.assertRaises(SystemExit):
            self.run_with(fake)
        self.assertEqual(fake.log, [])

    def test_bad_percent(self):
        fake = FakeASC()
        with self.assertRaises(SystemExit):
            self.run_with(fake, percent=0)
        self.assertEqual(fake.log, [])

    def test_v2_paths_go_to_v2(self):
        seen = []

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"{}"
        real_open, real_token = asc.urllib.request.urlopen, asc.token
        asc.urllib.request.urlopen = lambda req, timeout=0: seen.append(req.full_url) or R()
        asc.token = lambda: "t"
        try:
            asc.call = self.real[0]
            asc.call("GET", "/v2/appStoreVersionExperiments/E1")
            asc.call("GET", "/apps/A1")
        finally:
            asc.urllib.request.urlopen, asc.token = real_open, real_token
        self.assertEqual(seen, ["https://api.appstoreconnect.apple.com/v2/appStoreVersionExperiments/E1",
                                "https://api.appstoreconnect.apple.com/v1/apps/A1"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
