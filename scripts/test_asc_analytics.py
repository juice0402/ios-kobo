#!/usr/bin/env python3
"""asc.py analytics のテスト（本物の App Store Connect には送らない。API と segment の中身をにせものにする）

  python3 scripts/test_asc_analytics.py
"""
import csv
import gzip
import importlib.util
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

API = asc.API
DISC = "Date\tApp Name\tApp Apple Identifier\tEvent\tPage Type\tSource Type\tEngagement Type\tDevice\tPlatform Version\tTerritory\tCounts\tUnique Counts\n"
DOWN = "Date\tApp Name\tApp Apple Identifier\tDownload Type\tApp Version\tDevice\tPlatform Version\tSource Type\tPage Type\tPre-Order\tTerritory\tCounts\n"


def disc(day, event, n, page="No page"):
    return f"{day}\tGame\t1\t{event}\t{page}\tApp Store search\t\tiPhone\tiOS 26\tJP\t{n}\t{n}\n"


def down(day, kind, n):
    return f"{day}\tGame\t1\t{kind}\t1.0\tiPhone\tiOS 26\tApp Store search\tProduct page\tNo\tJP\t{n}\n"


class FakeASC:
    """App Store Connect のにせもの。reports が None なら報告はまだない。
    instances: 報告の名前 → [(processingDate, [segment の中身…])]"""

    def __init__(self, has_request=True, instances=None, names=None):
        self.log = []
        self.has_request = has_request
        self.instances = instances or {}
        self.names = names if names is not None else ["App Store Discovery and Engagement Standard",
                                                      "App Store Discovery and Engagement Detailed",
                                                      "App Downloads Standard", "App Downloads Detailed",
                                                      "App Crashes"]
        self.files = {}

    def call(self, method, path, body=None, soft=False):
        self.log.append((method, path, body))
        if path.startswith("/apps?"):
            return {"data": [{"id": "A1", "attributes": {"bundleId": "com.example.game"}}]}
        if path.startswith("/apps/A1/analyticsReportRequests"):
            if not self.has_request:
                return {"data": [{"id": "R0", "attributes": {"accessType": "ONGOING", "stoppedDueToInactivity": True}}]}
            return {"data": [{"id": "R1", "attributes": {"accessType": "ONGOING", "stoppedDueToInactivity": False}}]}
        if method == "POST" and path == "/analyticsReportRequests":
            return {"data": {"id": "R2", "attributes": {"accessType": "ONGOING"}}}
        if path.startswith("/analyticsReportRequests/R1/reports"):
            # 2ページに分けて返す（links.next をたどるか）
            data = [{"id": f"REP{i}", "attributes": {"name": n}} for i, n in enumerate(self.names)]
            if "cursor=2" in path:
                return {"data": data[2:]}
            return {"data": data[:2], "links": {"next": f"{API}/analyticsReportRequests/R1/reports?limit=200&cursor=2"}}
        if path.startswith("/analyticsReports/"):
            rep = self.names[int(path.split("/")[2][3:])]
            return {"data": [{"id": f"{rep}|{i}", "attributes": {"granularity": "DAILY", "processingDate": d}}
                             for i, (d, _) in enumerate(self.instances.get(rep, []))]}
        if path.startswith("/analyticsReportInstances/"):
            rep, i = path.split("/")[2].split("|")
            segs = self.instances[rep][int(i)][1]
            out = []
            for j, text in enumerate(segs):
                url = f"https://download.example/{rep}/{i}/{j}?sig=secret"
                self.files[url] = gzip.compress(text.encode())
                out.append({"id": f"S{i}{j}", "attributes": {"url": url}})
            return {"data": out}
        return {"data": []}


class AnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)
        Path("apps/game").mkdir(parents=True)
        Path("apps/game/app.json").write_text(json.dumps({"bundleId": "com.example.game"}))
        self.real = (asc.call, asc.fetch_segment)
        self.csv = Path("build/game/metrics/game.csv")

    def tearDown(self):
        asc.call, asc.fetch_segment = self.real
        os.chdir(self.cwd)

    def use(self, fake):
        asc.call = fake.call
        real_fetch = self.real[1]

        class Res:
            def __init__(self, data):
                self.data = data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self.data

        def fetch(url):
            # 本物の fetch_segment（gzip を解く所）を通す。落とす所だけにせもの
            orig = asc.urllib.request.urlopen
            asc.urllib.request.urlopen = lambda u, timeout=0: Res(fake.files[u])
            try:
                return real_fetch(url)
            finally:
                asc.urllib.request.urlopen = orig
        asc.fetch_segment = fetch

    def rows(self):
        with open(self.csv, newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]

    def test_creates_request_when_missing(self):
        fake = FakeASC(has_request=False)
        self.use(fake)
        self.assertEqual(asc.analytics("game"), 0)
        posts = [b for m, p, b in fake.log if m == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["data"]["attributes"]["accessType"], "ONGOING")
        self.assertEqual(posts[0]["data"]["relationships"]["app"]["data"]["id"], "A1")
        self.assertFalse(self.csv.exists())

    def test_does_not_create_request_when_present(self):
        fake = FakeASC(instances={})
        self.use(fake)
        asc.analytics("game")
        self.assertFalse(any(m == "POST" for m, _, _ in fake.log))

    def test_sums_segments_and_uses_latest_instance_per_day(self):
        fake = FakeASC(instances={
            "App Store Discovery and Engagement Standard": [
                ("2026-11-10", [DISC + disc("2026-11-08", "Impression", 100) + disc("2026-11-09", "Impression", 7),
                                DISC + disc("2026-11-08", "Impression", 20)
                                + disc("2026-11-08", "Page view", 9, "Product page")
                                + disc("2026-11-08", "Page view", 5, "In-app event")
                                + disc("2026-11-08", "Tap", 3, "Product page")]),
                # 新しいインスタンス：11/09 は入れかえ（7 と足さない）
                ("2026-11-11", [DISC + disc("2026-11-09", "IMPRESSION", 50) + disc("2026-11-09", "page view", 6, "product page")]),
            ],
            "App Downloads Standard": [
                ("2026-11-10", [DOWN + down("2026-11-08", "First-time Download", 8) + down("2026-11-08", "Redownload", 2)
                                + down("2026-11-08", "Auto-update", 40) + down("2026-11-08", "Manual update", 4)
                                + down("2026-11-08", "Restore", 1),
                                DOWN + down("2026-11-08", "First-time Download", 5)]),
            ],
        })
        self.use(fake)
        self.assertEqual(asc.analytics("game"), 2)
        self.assertEqual(self.rows(), [
            {"date": "2026-11-08", "impressions": "120", "product_page_views": "9", "first_time_downloads": "13", "redownloads": "2"},
            {"date": "2026-11-09", "impressions": "50", "product_page_views": "6", "first_time_downloads": "0", "redownloads": "0"},
        ])
        # Detailed の報告は落とさない
        self.assertFalse(any("REP1" in p or "REP3" in p for _, p, _ in fake.log))

    def test_same_day_is_replaced_and_sorted(self):
        self.csv.parent.mkdir(parents=True)
        self.csv.write_text("date,impressions,product_page_views,first_time_downloads,redownloads\n"
                            "2026-11-09,1,1,1,1\n2026-11-01,10,2,3,0\n")
        fake = FakeASC(instances={
            "App Store Discovery and Engagement Standard": [("2026-11-11", [DISC + disc("2026-11-09", "Impression", 30)])],
            "App Downloads Standard": [("2026-11-11", [DOWN + down("2026-11-09", "Redownload", 6)
                                                       + down("2026-11-10", "First-time Download", 5)])],
        })
        self.use(fake)
        asc.analytics("game")
        self.assertEqual([tuple(r.values()) for r in self.rows()], [
            ("2026-11-01", "10", "2", "3", "0"),
            ("2026-11-09", "30", "0", "0", "6"),
            ("2026-11-10", "0", "0", "5", "0"),
        ])

    def test_day_with_no_rows_or_empty_file_does_not_break(self):
        # 5人より少ない行は消されるので、行がない日・ヘッダーだけのファイル・空のファイル・segment なしがある
        fake = FakeASC(instances={
            "App Store Discovery and Engagement Standard": [("2026-11-10", [DISC, ""]), ("2026-11-11", [])],
            "App Downloads Standard": [("2026-11-11", [DOWN + down("2026-11-09", "First-time Download", 5)])],
        })
        self.use(fake)
        self.assertEqual(asc.analytics("game"), 1)
        self.assertEqual(self.rows(), [{"date": "2026-11-09", "impressions": "0", "product_page_views": "0",
                                        "first_time_downloads": "5", "redownloads": "0"}])

    def test_no_reports_yet(self):
        fake = FakeASC(names=[])
        self.use(fake)
        self.assertEqual(asc.analytics("game"), 0)
        self.assertFalse(self.csv.exists())

    def test_unknown_value_stops_without_counting(self):
        fake = FakeASC(instances={
            "App Store Discovery and Engagement Standard": [("2026-11-10", [DISC + disc("2026-11-08", "Glance", 9)])],
            "App Downloads Standard": [],
        })
        self.use(fake)
        with self.assertRaises(SystemExit) as e:
            asc.analytics("game")
        self.assertIn("Glance".lower(), str(e.exception))
        self.assertFalse(self.csv.exists())

    def test_missing_column_stops(self):
        fake = FakeASC(instances={
            "App Store Discovery and Engagement Standard": [],
            "App Downloads Standard": [("2026-11-10", ["Date\tKind\tCounts\n2026-11-08\tFirst-time Download\t5\n"])],
        })
        self.use(fake)
        with self.assertRaises(SystemExit) as e:
            asc.analytics("game")
        self.assertIn("download type", str(e.exception))
        self.assertFalse(self.csv.exists())

    def test_unknown_report_name_stops(self):
        fake = FakeASC(names=["App Store Discovery and Engagement Standard", "App Crashes"])
        self.use(fake)
        with self.assertRaises(SystemExit) as e:
            asc.analytics("game")
        self.assertIn("app downloads standard", str(e.exception))

    def test_download_error_does_not_print_signed_url(self):
        def broken(url, timeout=0):
            raise asc.urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        orig = asc.urllib.request.urlopen
        asc.urllib.request.urlopen = broken
        try:
            with self.assertRaises(asc.MetricsError) as e:
                self.real[1]("https://download.example/x?sig=secret")
        finally:
            asc.urllib.request.urlopen = orig
        self.assertNotIn("secret", str(e.exception))
        self.assertNotIn("download.example", str(e.exception))


class WorkflowTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML がない")
    def test_metrics_yml_reads(self):
        import yaml
        doc = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github/workflows/metrics.yml").read_text())
        self.assertIn("jobs", doc)
        self.assertTrue("on" in doc or True in doc)   # YAML 1.1 では on が True になる
        self.assertIn("17 1 * * *", [c["cron"] for c in (doc.get("on") or doc.get(True))["schedule"]])


if __name__ == "__main__":
    unittest.main(verbosity=1)
