#!/usr/bin/env python3
"""asc.py promo のテスト（本物の App Store Connect には送らない。API をにせものにする）

  python3 scripts/test_asc_promo.py
"""
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

    def __init__(self, versions, locs, refuse=()):
        self.log = []
        self.versions = versions      # [{versionString, appStoreState}]
        self.locs = locs              # {版の番号: [{locale, promotionalText}]}
        self.refuse = set(refuse)     # PATCH を断るローカライズの id

    def call(self, method, path, body=None, soft=False):
        self.log.append((method, path, body, soft))
        if path.startswith("/apps?"):
            return {"data": [{"id": "A1", "attributes": {"bundleId": "com.example.game"}}]}
        if path.startswith("/apps/A1/appStoreVersions"):
            return {"data": [{"id": f"V{i}", "attributes": a} for i, a in enumerate(self.versions)]}
        if "/appStoreVersionLocalizations?" in path:
            i = int(path.split("/")[2][1:])
            return {"data": [{"id": f"L{i}-{l['locale']}", "attributes": l} for l in self.locs.get(i, [])]}
        if method == "PATCH":
            lid = path.rsplit("/", 1)[1]
            if lid in self.refuse:
                if soft:
                    raise asc.ApiError(409, "STATE_ERROR")
                raise SystemExit("止まった")
            return {"data": {"id": lid}}
        raise AssertionError(f"知らない呼び出し {method} {path}")

    def patches(self):
        return [(p.rsplit("/", 1)[1], b["data"]["attributes"]["promotionalText"]) for m, p, b, _ in self.log if m == "PATCH"]


class PromoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        os.makedirs("apps/game/store/ja")
        os.makedirs("apps/game/store/en-US")
        with open("apps/game/app.json", "w") as f:
            json.dump({"bundleId": "com.example.game", "version": "1.0"}, f)
        self.write("ja", "あたらしい文\n")
        self.write("en-US", "New text\n")
        self.real_call = asc.call

    def tearDown(self):
        asc.call = self.real_call
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def write(self, loc, text):
        with open(f"apps/game/store/{loc}/promotional_text.txt", "w", encoding="utf-8") as f:
            f.write(text)

    def run_promo(self, fake):
        asc.call = fake.call
        return asc.promo("game")

    def test_live_version_gets_new_text(self):
        fake = FakeASC([{"versionString": "1.0", "appStoreState": "READY_FOR_SALE"}],
                       {0: [{"locale": "ja", "promotionalText": "古い文"}, {"locale": "en-US", "promotionalText": "Old"}]})
        self.assertEqual(self.run_promo(fake), 2)
        self.assertEqual(fake.patches(), [("L0-ja", "あたらしい文"), ("L0-en-US", "New text")])

    def test_same_text_is_not_sent(self):
        fake = FakeASC([{"versionString": "1.0", "appStoreState": "READY_FOR_SALE"}],
                       {0: [{"locale": "ja", "promotionalText": "あたらしい文"}, {"locale": "en-US", "promotionalText": "Old"}]})
        self.assertEqual(self.run_promo(fake), 1)
        self.assertEqual(fake.patches(), [("L0-en-US", "New text")])

    def test_live_and_editable_versions(self):
        fake = FakeASC([{"versionString": "1.1", "appStoreState": "PREPARE_FOR_SUBMISSION"},
                        {"versionString": "1.0", "appStoreState": "READY_FOR_SALE"},
                        {"versionString": "0.9", "appStoreState": "REPLACED_WITH_NEW_VERSION"}],
                       {0: [{"locale": "ja", "promotionalText": ""}], 1: [{"locale": "ja", "promotionalText": "古い"}],
                        2: [{"locale": "ja", "promotionalText": "もっと古い"}]})
        self.assertEqual(self.run_promo(fake), 2)
        self.assertEqual([p[0] for p in fake.patches()], ["L0-ja", "L1-ja"])   # 置きかわった古い版はさわらない

    def test_locale_without_folder_is_left_alone(self):
        fake = FakeASC([{"versionString": "1.0", "appStoreState": "READY_FOR_SALE"}],
                       {0: [{"locale": "zh-Hans", "promotionalText": "旧"}, {"locale": "ja", "promotionalText": "古い"}]})
        self.assertEqual(self.run_promo(fake), 1)
        self.assertEqual(fake.patches(), [("L0-ja", "あたらしい文")])

    def test_in_review_refusal_is_only_a_warning(self):
        fake = FakeASC([{"versionString": "1.0", "appStoreState": "WAITING_FOR_REVIEW"}],
                       {0: [{"locale": "ja", "promotionalText": "古い"}, {"locale": "en-US", "promotionalText": "Old"}]},
                       refuse={"L0-ja"})
        self.assertEqual(self.run_promo(fake), 1)
        self.assertTrue(all(soft for m, _, _, soft in fake.log if m == "PATCH"))

    def test_live_refusal_stops(self):
        fake = FakeASC([{"versionString": "1.0", "appStoreState": "READY_FOR_SALE"}],
                       {0: [{"locale": "ja", "promotionalText": "古い"}]}, refuse={"L0-ja"})
        with self.assertRaises(SystemExit):
            self.run_promo(fake)

    def test_too_long_text_stops_before_sending(self):
        self.write("ja", "あ" * 171)
        fake = FakeASC([{"versionString": "1.0", "appStoreState": "READY_FOR_SALE"}], {0: []})
        with self.assertRaises(SystemExit):
            self.run_promo(fake)
        self.assertEqual(fake.log, [])

    def test_no_version_to_send_stops(self):
        fake = FakeASC([{"versionString": "1.0", "appStoreState": "REMOVED_FROM_SALE"}], {})
        with self.assertRaises(SystemExit):
            self.run_promo(fake)
        self.assertEqual(fake.patches(), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
