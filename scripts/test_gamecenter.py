#!/usr/bin/env python3
"""Game Center のテスト（本物の App Store Connect には送らない。API とアップロード先をにせものにする）

  python3 scripts/test_gamecenter.py

  - gamecenter.py：gamecenter.json の点検（ID・点・言語・バッジの絵・app.json とのくいちがい）
  - prepare.py：gamecenter.json を写す・Game Center を有効にする（entitlements・Info.plist）
  - asc.py setup --game-center：実績を作る順番・何回動かしても同じ・ちがえば直す
  - asc.py gc-pending・submit-review：版といっしょに審査に出す部品
  - pages.py：プライバシーポリシーの Game Center の文
"""
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.modules.setdefault("jwt", types.SimpleNamespace(encode=lambda *a, **k: "t"))  # 鍵なしで読めるように
import asc  # noqa: E402
import gamecenter  # noqa: E402
import pages  # noqa: E402
import prepare  # noqa: E402


def badge(path, size=(1024, 1024), mode="RGB", fmt="PNG"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, (200, 60, 40) if mode == "RGB" else (200, 60, 40, 128)).save(path, fmt)


def ach(aid, points=10, hidden=False, **kw):
    a = {"id": aid, "points": points, "hidden": hidden, "image": f"achievements/{aid}.png",
         "ja": {"name": f"名前{aid}", "before": "まだ", "after": "できた"},
         "en-US": {"name": f"Name {aid}", "before": "Not yet", "after": "Done"}}
    a.update(kw)
    return a


def write_gc(folder, data, images=True):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "gamecenter.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if images:
        for a in data.get("achievements", []):
            badge(folder / f"achievements/{a['id']}.png")
    return folder / "gamecenter.json"


SAMPLE = {"leaderboard": {"id": "imo_best", "name": {"ja": "さいこうきろく", "en-US": "Best Score"},
                          "suffix": {"ja": "こ", "en-US": " pcs"}},
          "achievements": [ach("imo_first"), ach("imo_boss", 50, True)]}


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            r = fn(*a, **k)
        except SystemExit as e:
            r = e
    return r, buf.getvalue()


# ---------------------------------------------------------------- gamecenter.json の点検
class CheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def problems(self, data, app_lb="", images=True):
        path = write_gc(self.dir / "kobo", data, images)
        with self.assertRaises(gamecenter.GameCenterError) as c:
            gamecenter.load(path, app_lb)
        return "\n".join(c.exception.problems)

    def test_good_file(self):
        gc = gamecenter.load(write_gc(self.dir / "kobo", SAMPLE))
        self.assertEqual(gc["leaderboard"]["id"], "imo_best")
        self.assertEqual(gc["leaderboard"]["suffix"], {"ja": "こ", "en-US": " pcs"})
        self.assertEqual([a["id"] for a in gc["achievements"]], ["imo_first", "imo_boss"])
        self.assertTrue(gc["achievements"][1]["hidden"])
        self.assertTrue(gc["achievements"][0]["image"].is_file())
        self.assertIn("実績 2 こ（60 点・隠し 1 こ）", gamecenter.summary(gc))
        # 同じ ID ならくいちがいなし。コマンドも 0
        gamecenter.load(self.dir / "kobo/gamecenter.json", "imo_best")
        r, out = quiet(gamecenter.main, [str(self.dir / "kobo/gamecenter.json")])
        self.assertEqual(r, 0)

    def test_achievements_only_and_default_image(self):
        a = ach("imo_x")
        del a["image"]
        gc = gamecenter.load(write_gc(self.dir / "kobo", {"achievements": [a]}))
        self.assertIsNone(gc["leaderboard"])
        self.assertEqual(gc["achievements"][0]["image"].name, "imo_x.png")

    def test_bad_ids(self):
        p = self.problems({"achievements": [ach("Imo-Big"), ach("imo_a"), ach("imo_a"), ach("a" * 101)]}, images=False)
        self.assertIn("Imo-Big", p)
        self.assertIn("重なって", p)
        self.assertIn("a" * 101, p)

    def test_points(self):
        p = self.problems({"achievements": [ach("x0", 0), ach("x1", 101), ach("x2", True)]})
        self.assertEqual(p.count("points は 1〜100"), 3)
        many = [ach(f"x{i}", 100) for i in range(11)]
        self.assertIn("合計は 1000 まで（いまは 1100）", self.problems({"achievements": many}))

    def test_locales(self):
        a = ach("x")
        del a["en-US"]
        a["ja"]["before"] = ""
        a["ja"]["memo"] = "?"
        p = self.problems({"achievements": [a]})
        self.assertIn("en-US がありません", p)
        self.assertIn("ja.before", p)
        self.assertIn("知らない項目 memo", p)

    def test_apple_bad_chars(self):
        # 11/27 本物で断られた：実績の名前の ★・説明の 🥔 🚓。■ や「」・、は通った
        a = ach("x")
        a["ja"]["name"] = "ぜんぶの街で★3つ"
        a["en-US"]["after"] = "Got it 🚓"
        p = self.problems({"achievements": [a]})
        self.assertIn("ja.name に App Store Connect が受けつけない字 ★", p)
        self.assertIn("en-US.after に App Store Connect が受けつけない字 🚓", p)
        self.assertEqual(gamecenter.apple_bad_chars("■ ぽいっと！「わる芋」・ラインを2つに。〜"), [])
        self.assertEqual(gamecenter.apple_bad_chars("FEVER👻✨⭐"), ["👻", "✨", "⭐"])

    def test_images(self):
        data = {"achievements": [ach("big"), ach("alpha"), ach("none"), ach("gif", image="achievements/gif.gif"),
                                 ach("out", image="../secret.png"), ach("lowdpi")]}
        folder = self.dir / "kobo"
        write_gc(folder, data, images=False)
        badge(folder / "achievements/big.png", size=(512, 512))
        badge(folder / "achievements/alpha.png", mode="RGBA")
        Image.new("RGB", (1024, 1024)).save(folder / "achievements/lowdpi.png", dpi=(36, 36))
        with self.assertRaises(gamecenter.GameCenterError) as c:
            gamecenter.load(folder / "gamecenter.json")
        p = "\n".join(c.exception.problems)
        self.assertIn("実績 big: バッジの絵は 1024×1024（いまは 512×512）", p)
        self.assertIn("実績 alpha: バッジの絵は RGB・透明なし（いまは RGBA", p)
        self.assertIn("実績 none: バッジの絵 none.png がありません", p)
        self.assertIn("実績 gif: image は .png か .jpg", p)
        self.assertIn("実績 out: image は gamecenter.json のフォルダの中", p)
        self.assertIn("実績 lowdpi: バッジの絵は 72ppi 以上", p)

    def test_jpeg_is_ok(self):
        data = {"achievements": [ach("jp", image="achievements/jp.jpg")]}
        folder = self.dir / "kobo"
        write_gc(folder, data, images=False)
        badge(folder / "achievements/jp.jpg", fmt="JPEG")
        gamecenter.load(folder / "gamecenter.json")

    def test_leaderboard(self):
        self.assertIn("ちがいます", self.problems(SAMPLE, app_lb="hiragana_balance_best"))
        p = self.problems({"leaderboard": {"id": "bad id", "name": {"ja": "x"}, "suffix": "段"}})
        self.assertIn("leaderboard.id", p)
        self.assertIn("leaderboard.name.en-US", p)
        self.assertIn("leaderboard.suffix", p)
        self.assertIn("leaderboard も achievements もありません", self.problems({}))
        self.assertIn("知らない項目 achievement", self.problems({"achievement": []}))

    def test_command_reports_errors(self):
        path = write_gc(self.dir / "kobo", {"achievements": [ach("x", 500)]})
        r, out = quiet(gamecenter.main, [str(path)])
        self.assertEqual(r, 1)
        self.assertIn("::error::gamecenter.json: 実績 x: points", out)


# ---------------------------------------------------------------- prepare.py
class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.real_root = prepare.ROOT
        prepare.ROOT = self.root
        (self.root / "scripts").mkdir()
        self.src = self.root / "build/_src/imo/docs/kobo"
        self.out = self.root / "build/imo"

    def tearDown(self):
        prepare.ROOT = self.real_root
        shutil.rmtree(self.root, ignore_errors=True)

    def test_without_gamecenter_json_keeps_app_json(self):
        gc = prepare.game_center("imo", {"gameCenter": {"leaderboard": "buttobi_chase_best"}}, self.out)
        self.assertEqual(gc, {"leaderboard": "buttobi_chase_best", "enabled": True, "file": "", "achievements": 0})
        gc = prepare.game_center("imo", {}, self.out)
        self.assertFalse(gc["enabled"])

    def test_copies_and_enables(self):
        write_gc(self.src, {"achievements": [ach("imo_first")]})
        (self.root / "docs/imo").mkdir(parents=True)
        (self.root / "docs/imo/privacy.html").write_text("Game Center … achievements …")
        gc, out = quiet(prepare.game_center, "imo", {}, self.out)
        self.assertEqual(gc, {"leaderboard": "", "enabled": True, "file": "build/imo/gamecenter/gamecenter.json",
                              "achievements": 1})
        self.assertTrue((self.out / "gamecenter/achievements/imo_first.png").is_file())
        self.assertIn("実績 1 こ", out)

    def test_leaderboard_from_json_and_mismatch(self):
        write_gc(self.src, SAMPLE)
        gc, _ = quiet(prepare.game_center, "imo", {}, self.out)
        self.assertEqual(gc["leaderboard"], "imo_best")
        r, out = quiet(prepare.game_center, "imo", {"gameCenter": {"leaderboard": "other_best"}}, self.out)
        self.assertIsInstance(r, SystemExit)
        self.assertIn("ちがいます", out)

    def test_bad_json_stops(self):
        write_gc(self.src, {"achievements": [ach("BAD")]})
        r, out = quiet(prepare.game_center, "imo", {}, self.out)
        self.assertIsInstance(r, SystemExit)
        self.assertIn("::error::docs/kobo/gamecenter.json: 実績 BAD", out)

    def test_privacy_page_must_mention_achievements(self):
        write_gc(self.src, {"achievements": [ach("imo_first")]})
        (self.root / "docs/imo").mkdir(parents=True)
        (self.root / "docs/imo/privacy.html").write_text("Game Center: best score only")
        r, out = quiet(prepare.game_center, "imo", {}, self.out)
        self.assertIsInstance(r, SystemExit)
        self.assertIn("scripts/pages.py", out)

    def test_project_entitlements(self):
        cfg = {"bundleId": "com.example.imo", "version": "1.0", "name": {"en": "Imo", "ja": "いも"}}
        (self.root / "shell/Sources").mkdir(parents=True)
        (self.root / "shell/PrivacyInfo.xcprivacy").write_text("")
        (self.root / "apps/imo").mkdir(parents=True)
        Image.new("RGB", (64, 64)).save(self.root / "apps/imo/icon.png")
        proj = self.out / "project"
        prepare.make_project("imo", cfg, proj, 1, {"leaderboard": "", "enabled": True})
        spec = json.loads((proj / "project.json").read_text())["targets"]["App"]
        self.assertTrue(spec["entitlements"]["properties"]["com.apple.developer.game-center"])
        self.assertIs(spec["info"]["properties"]["GameCenter"], True)
        self.assertEqual(spec["info"]["properties"]["GameLeaderboardID"], "")
        shutil.rmtree(proj)
        prepare.make_project("imo", cfg, proj, 1)   # Game Center なし（今までどおり）
        spec = json.loads((proj / "project.json").read_text())["targets"]["App"]
        self.assertNotIn("entitlements", spec)
        self.assertIs(spec["info"]["properties"]["GameCenter"], False)


# ---------------------------------------------------------------- にせの App Store Connect
class FakeASC:
    """App Store Connect のにせもの。作ったものを覚えて、2回目は「ある」と返す"""

    def __init__(self, detail=True, loc404=False, item_error=None, versions=None):
        self.log = []
        self.n = 0
        self.detail = "GC1" if detail else None
        self.boards = {}      # id → attributes
        self.board_locs = {}  # id → (board, attributes)
        self.achs = {}        # id → attributes
        self.locs = {}        # id → (ach, attributes)
        self.images = {}      # id → (loc, attributes)
        self.loc404 = loc404
        self.item_error = item_error          # reviewSubmissionItems の部品で返すエラー
        self.versions = versions or {}        # 実績・ランキングの id → [state]
        self.subs = []

    def new(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def call(self, method, path, body=None, soft=False):
        self.log.append((method, path, body))
        attrs = (body or {}).get("data", {}).get("attributes", {})
        rel = (body or {}).get("data", {}).get("relationships", {})
        if path.startswith("/apps?"):
            return {"data": [{"id": "A1", "attributes": {"bundleId": "com.example.imo"}}]}
        if path.startswith("/apps/A1/appStoreVersions"):
            return {"data": [{"id": "V1", "attributes": {"versionString": "1.1", "appStoreState": "PREPARE_FOR_SUBMISSION"}}]}
        if path == "/apps/A1/gameCenterDetail":
            if not self.detail:
                raise asc.ApiError(404, "no detail")
            return {"data": {"id": self.detail}}
        if method == "POST" and path == "/gameCenterDetails":
            self.detail = "GC9"
            return {"data": {"id": "GC9"}}
        if path.startswith(f"/gameCenterDetails/{self.detail}/gameCenterLeaderboards"):
            return {"data": [{"id": i, "attributes": a} for i, a in self.boards.items()]}
        if method == "POST" and path == "/gameCenterLeaderboards":
            i = self.new("LB")
            self.boards[i] = dict(attrs)
            return {"data": {"id": i, "attributes": attrs}}
        if path.startswith("/gameCenterLeaderboards/") and path.endswith("/localizations?limit=50"):
            b = path.split("/")[2]
            return {"data": [{"id": i, "attributes": a} for i, (bb, a) in self.board_locs.items() if bb == b]}
        if method == "POST" and path == "/gameCenterLeaderboardLocalizations":
            i = self.new("LBL")
            self.board_locs[i] = (rel["gameCenterLeaderboard"]["data"]["id"], dict(attrs))
            return {"data": {"id": i}}
        if method == "PATCH" and path.startswith("/gameCenterLeaderboardLocalizations/"):
            self.board_locs[path.split("/")[2]][1].update(attrs)
            return {"data": {}}
        if path.startswith(f"/gameCenterDetails/{self.detail}/gameCenterAchievements"):
            return {"data": [{"id": i, "attributes": a} for i, a in self.achs.items()]}
        if method == "POST" and path == "/gameCenterAchievements":
            i = self.new("ACH")
            self.achs[i] = dict(attrs)
            return {"data": {"id": i, "attributes": attrs}}
        if method == "PATCH" and path.startswith("/gameCenterAchievements/"):
            self.achs[path.split("/")[2]].update(attrs)
            return {"data": {}}
        if path.startswith("/gameCenterAchievements/") and path.endswith("/localizations?limit=50"):
            if self.loc404:
                raise asc.ApiError(404, "not found")
            a = path.split("/")[2]
            return {"data": [{"id": i, "attributes": at} for i, (aa, at) in self.locs.items() if aa == a]}
        if method == "POST" and path == "/gameCenterAchievementLocalizations":
            i = self.new("AL")
            self.locs[i] = (rel["gameCenterAchievement"]["data"]["id"], dict(attrs))
            return {"data": {"id": i, "attributes": attrs}}
        if method == "PATCH" and path.startswith("/gameCenterAchievementLocalizations/"):
            self.locs[path.split("/")[2]][1].update(attrs)
            return {"data": {}}
        if path.endswith("/gameCenterAchievementImage"):
            loc = path.split("/")[2]
            got = [(i, a) for i, (l, a) in self.images.items() if l == loc]
            return {"data": {"id": got[0][0], "attributes": got[0][1]} if got else None}
        if method == "POST" and path == "/gameCenterAchievementImages":
            i = self.new("IMG")
            self.images[i] = (rel["gameCenterAchievementLocalization"]["data"]["id"], dict(attrs))
            return {"data": {"id": i, "attributes": {"uploadOperations": [
                {"method": "PUT", "url": f"https://upload.example/{i}", "offset": 0, "length": attrs["fileSize"],
                 "requestHeaders": []}]}}}
        if method == "PATCH" and path.startswith("/gameCenterAchievementImages/"):
            self.images[path.split("/")[2]][1]["assetDeliveryState"] = {"state": "COMPLETE"}
            return {"data": {}}
        if method == "DELETE" and path.startswith("/gameCenterAchievementImages/"):
            del self.images[path.split("/")[2]]
            return {}
        if path.startswith("/v2/") and path.split("?")[0].endswith("/versions"):
            rid = path.split("/")[3]
            return {"data": [{"id": f"{rid}-v{k}", "attributes": {"state": st}}
                             for k, st in enumerate(self.versions.get(rid, ["LIVE"]))]}
        if path.startswith("/reviewSubmissions?"):
            return {"data": [{"id": s} for s in self.subs]}
        if method == "POST" and path == "/reviewSubmissions":
            self.subs.append("SUB1")
            return {"data": {"id": "SUB1"}}
        if method == "POST" and path == "/reviewSubmissionItems":
            if self.item_error and "appStoreVersion" not in rel:
                raise asc.ApiError(*self.item_error)
            return {"data": {"id": self.new("ITEM")}}
        return {"data": {}}


class AscBase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        Path(self.root, "apps/imo").mkdir(parents=True)
        Path(self.root, "apps/imo/app.json").write_text(json.dumps({"bundleId": "com.example.imo", "version": "1.1"}))
        self.gc_path = write_gc(self.root / "build/imo/gamecenter", SAMPLE)
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.env = {k: os.environ.get(k) for k in ("GAMECENTER_JSON", "LEADERBOARD_ID", "GITHUB_OUTPUT")}
        os.environ["GAMECENTER_JSON"] = str(self.gc_path)
        os.environ["LEADERBOARD_ID"] = "imo_best"
        os.environ.pop("GITHUB_OUTPUT", None)
        self.puts = []
        self.real = (asc.call, asc.put_bytes)
        asc.put_bytes = lambda op, data: self.puts.append((op["url"], len(data)))

    def tearDown(self):
        asc.call, asc.put_bytes = self.real
        os.chdir(self.cwd)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)

    def posts(self, fake):
        return [(p, b) for m, p, b in fake.log if m == "POST"]


class SetupTest(AscBase):
    def test_creates_in_order_and_is_idempotent(self):
        fake = FakeASC(detail=False)
        asc.call = fake.call
        r, out = quiet(asc.setup_game_center, "A1")
        self.assertNotIsInstance(r, SystemExit, out)
        kinds = [p for p, _ in self.posts(fake)]
        self.assertEqual(kinds[0], "/gameCenterDetails")
        # 実績ごとに：実績 → ja の名前 → ja の絵 → en-US の名前 → en-US の絵
        first = kinds.index("/gameCenterAchievements")
        self.assertEqual(kinds[first:first + 5], ["/gameCenterAchievements", "/gameCenterAchievementLocalizations",
                                                  "/gameCenterAchievementImages", "/gameCenterAchievementLocalizations",
                                                  "/gameCenterAchievementImages"])
        self.assertEqual(kinds.count("/gameCenterAchievements"), 2)
        self.assertEqual(kinds.count("/gameCenterAchievementImages"), 4)   # 2つの実績 × 2つの言語
        boss = next(b for p, b in self.posts(fake) if p == "/gameCenterAchievements"
                    and b["data"]["attributes"]["vendorIdentifier"] == "imo_boss")["data"]["attributes"]
        self.assertEqual(boss, {"referenceName": "imo_boss", "vendorIdentifier": "imo_boss", "repeatable": False,
                                "points": 50, "showBeforeEarned": False})
        loc = next(a for _, (_, a) in fake.locs.items() if a["locale"] == "en-US")
        self.assertEqual(set(loc), {"locale", "name", "beforeEarnedDescription", "afterEarnedDescription"})
        img = next(b for p, b in self.posts(fake) if p == "/gameCenterAchievementImages")["data"]["attributes"]
        self.assertEqual(img["fileName"], "imo_first.png")
        self.assertEqual(len(self.puts), 4)
        # 送ったあとの PATCH は uploaded だけ（実績の絵は sourceFileChecksum を受けつけない・11/27 本物で 409）
        done = [b["data"]["attributes"] for m, p, b in fake.log
                if m == "PATCH" and p.startswith("/gameCenterAchievementImages/")]
        self.assertEqual(done, [{"uploaded": True}] * 4)
        # ランキングの名前と単位は gamecenter.json から
        names = {a["locale"]: a for _, a in fake.board_locs.values()}
        self.assertEqual(names["ja"]["formatterSuffix"], "こ")
        self.assertEqual(names["en-US"]["name"], "Best Score")

        # 2回目：何も作らない・送らない・直さない
        fake.log.clear()
        self.puts.clear()
        quiet(asc.setup_game_center, "A1")
        self.assertEqual([m for m, _, _ in fake.log if m != "GET"], [])
        self.assertEqual(self.puts, [])

    def test_fixes_changed_text_points_and_image(self):
        fake = FakeASC()
        asc.call = fake.call
        quiet(asc.setup_game_center, "A1")
        data = json.loads(self.gc_path.read_text())
        data["achievements"][0]["points"] = 25
        data["achievements"][0]["ja"]["name"] = "あたらしい名前"
        data["leaderboard"]["name"]["ja"] = "ベスト"
        self.gc_path.write_text(json.dumps(data, ensure_ascii=False))
        Image.new("RGB", (1024, 1024), (1, 2, 3)).save(self.gc_path.parent / "achievements/imo_boss.png",
                                                       compress_level=0)   # 大きさがちがう絵＝入れかえ
        fake.log.clear()
        _, out = quiet(asc.setup_game_center, "A1")
        changes = [(m, p.split("/")[1]) for m, p, _ in fake.log if m != "GET"]
        self.assertIn(("PATCH", "gameCenterAchievements"), changes)
        self.assertIn(("PATCH", "gameCenterAchievementLocalizations"), changes)
        self.assertIn(("PATCH", "gameCenterLeaderboardLocalizations"), changes)
        self.assertEqual(changes.count(("DELETE", "gameCenterAchievementImages")), 2)   # imo_boss の ja・en-US
        self.assertNotIn(("POST", "gameCenterAchievements"), changes)
        first = next(a for a in fake.achs.values() if a["vendorIdentifier"] == "imo_first")
        self.assertEqual(first["points"], 25)

    def test_patch_refused_is_warning(self):
        fake = FakeASC()
        asc.call = fake.call
        quiet(asc.setup_game_center, "A1")
        data = json.loads(self.gc_path.read_text())
        data["achievements"][0]["points"] = 99
        self.gc_path.write_text(json.dumps(data, ensure_ascii=False))
        real = fake.call

        def refuse(method, path, body=None, soft=False):
            if method == "PATCH" and path.startswith("/gameCenterAchievements/"):
                raise asc.ApiError(409, "STATE_ERROR live")
            return real(method, path, body, soft)
        asc.call = refuse
        r, out = quiet(asc.setup_game_center, "A1")
        self.assertNotIsInstance(r, SystemExit)
        self.assertIn("::warning::実績 imo_first を直せませんでした", out)

    def test_extra_achievement_is_kept(self):
        fake = FakeASC()
        fake.achs["OLD"] = {"vendorIdentifier": "imo_old", "points": 10, "showBeforeEarned": True}
        asc.call = fake.call
        _, out = quiet(asc.setup_game_center, "A1")
        self.assertIn("::notice::gamecenter.json にない実績", out)
        self.assertIn("imo_old", out)
        self.assertFalse(any(m == "DELETE" and "/gameCenterAchievements/" in p for m, p, _ in fake.log))

    def test_localization_404_is_warning(self):
        fake = FakeASC(loc404=True)
        asc.call = fake.call
        r, out = quiet(asc.setup_game_center, "A1")
        self.assertNotIsInstance(r, SystemExit)
        self.assertIn("名前と説明を API で読めません（404）", out)
        self.assertEqual(sum(1 for p, _ in self.posts(fake) if p == "/gameCenterAchievements"), 2)

    def test_leaderboard_only_like_before(self):
        os.environ["GAMECENTER_JSON"] = ""
        os.environ["LEADERBOARD_ID"] = "buttobi_chase_best"
        fake = FakeASC()
        asc.call = fake.call
        quiet(asc.setup_game_center, "A1")
        self.assertEqual({a["name"] for _, a in fake.board_locs.values()}, {"さいこうきろく", "Best Score"})
        self.assertFalse(any(p == "/gameCenterAchievements" for p, _ in self.posts(fake)))

    def test_setup_turns_errors_into_warning(self):
        fake = FakeASC()

        def broken(method, path, body=None, soft=False):
            if path.startswith("/bundleIds"):
                return {"data": [{"attributes": {"identifier": "com.example.imo"}}]}
            if path.startswith("/apps?"):
                return {"data": [{"id": "A1", "attributes": {"bundleId": "com.example.imo", "name": "Imo"}}]}
            if path == "/apps/A1/gameCenterDetail":
                raise asc.ApiError(500, "boom")
            return fake.call(method, path, body, soft)
        asc.call = broken
        os.environ["BUNDLE_ID"] = "com.example.imo"
        try:
            r, out = quiet(asc.setup, True)
        finally:
            os.environ.pop("BUNDLE_ID", None)
        self.assertNotIsInstance(r, SystemExit)
        self.assertIn("has_app=true", out)
        self.assertIn("::warning::Game Center の用意ができませんでした", out)


class ReviewTest(AscBase):
    def made(self, versions=None, item_error=None):
        fake = FakeASC(item_error=item_error)
        asc.call = fake.call
        quiet(asc.setup_game_center, "A1")
        ids = {a["vendorIdentifier"]: i for i, a in fake.achs.items()}
        ids.update({a["vendorIdentifier"]: i for i, a in fake.boards.items()})
        fake.versions = {ids[k]: v for k, v in (versions or {}).items()}
        fake.log.clear()
        return fake, ids

    def test_no_pending_uses_fastlane(self):
        fake, _ = self.made()
        items, out = quiet(asc.gc_pending, "imo")
        self.assertEqual(items, [])
        self.assertIn("gc_pending=false", out)

    def test_pending_items_go_with_the_version(self):
        fake, ids = self.made({"imo_best": ["PREPARE_FOR_SUBMISSION"], "imo_first": ["READY_FOR_REVIEW"],
                               "imo_boss": ["LIVE"]})
        items, out = quiet(asc.gc_pending, "imo")
        self.assertIn("gc_pending=true", out)
        self.assertEqual(sorted(i[0] for i in items), ["gameCenterAchievementVersion", "gameCenterLeaderboardVersion"])
        fake.log.clear()
        r, out = quiet(asc.submit_review, "imo")
        self.assertIs(r, True, out)
        steps = [(m, p) for m, p, _ in fake.log if m != "GET"]
        self.assertEqual(steps, [("POST", "/reviewSubmissions"), ("POST", "/reviewSubmissionItems"),
                                 ("POST", "/reviewSubmissionItems"), ("POST", "/reviewSubmissionItems"),
                                 ("PATCH", "/reviewSubmissions/SUB1")])
        rels = [list(b["data"]["relationships"]) for m, p, b in fake.log if p == "/reviewSubmissionItems"]
        self.assertEqual(rels[0], ["reviewSubmission", "appStoreVersion"])   # 版がいちばん先
        ach_item = next(b for m, p, b in fake.log if p == "/reviewSubmissionItems"
                        and "gameCenterAchievementVersion" in b["data"]["relationships"])
        self.assertEqual(ach_item["data"]["relationships"]["gameCenterAchievementVersion"]["data"],
                         {"type": "gameCenterAchievementVersions", "id": f"{ids['imo_first']}-v0"})
        patch = fake.log[-1][2]
        self.assertEqual(patch["data"]["attributes"], {"submitted": True})

    def test_uses_existing_draft(self):
        fake, _ = self.made({"imo_first": ["PREPARE_FOR_SUBMISSION"]})
        fake.subs.append("DRAFT")
        quiet(asc.submit_review, "imo")
        self.assertFalse(any(m == "POST" and p == "/reviewSubmissions" for m, p, _ in fake.log))
        self.assertTrue(any(m == "PATCH" and p == "/reviewSubmissions/DRAFT" for m, p, _ in fake.log))

    def test_already_in_draft_is_ok(self):
        fake, _ = self.made({"imo_first": ["READY_FOR_REVIEW"]}, item_error=(409, "ENTITY_ERROR already added"))
        r, out = quiet(asc.submit_review, "imo")
        self.assertIs(r, True, out)

    def test_component_refused_does_not_submit(self):
        fake, _ = self.made({"imo_first": ["PREPARE_FOR_SUBMISSION"]}, item_error=(409, "relationship not allowed"))
        r, out = quiet(asc.submit_review, "imo")
        self.assertIs(r, False)
        self.assertFalse(any(m == "PATCH" for m, _, _ in fake.log))
        self.assertIn("::notice::App Store Connect の画面で", out)
        self.assertIn("submitted=false", out)

    def test_pending_read_error_falls_back(self):
        fake, _ = self.made()

        def broken(method, path, body=None, soft=False):
            if path.startswith("/v2/"):
                raise asc.ApiError(404, "no versions api")
            return fake.call(method, path, body, soft)
        asc.call = broken
        items, out = quiet(asc.gc_pending, "imo")
        self.assertEqual(items, [])
        self.assertIn("gc_pending=false", out)
        self.assertIn("::notice::最初のランキングと実績は版といっしょの審査が要る", out)


# ---------------------------------------------------------------- pages.py
class PagesTest(unittest.TestCase):
    CFG = {"name": {"ja": "いも", "en": "Imo"}, "game": {"repo": "juice0402/x", "ref": "abc"}}

    def test_parts(self):
        self.assertEqual(pages.game_center_parts(self.CFG, fetch=lambda u: None), set())
        got = pages.game_center_parts(self.CFG, fetch=lambda u: json.dumps({"achievements": [{"id": "a"}]}))
        self.assertEqual(got, {"achievements"})
        urls = []
        pages.game_center_parts({**self.CFG, "gameCenter": {"leaderboard": "x"}},
                                fetch=lambda u: urls.append(u) or json.dumps(SAMPLE))
        self.assertEqual(urls, ["https://raw.githubusercontent.com/juice0402/x/abc/docs/kobo/gamecenter.json"])

    def test_privacy_text(self):
        both = pages.privacy("imo", self.CFG, {}, {"leaderboard", "achievements"})
        self.assertIn("最高スコアと取った実績を Apple の Game Center に送り", both)
        self.assertIn("your best score and the achievements you earn are sent", both)
        only = pages.privacy("imo", self.CFG, {}, {"achievements"})
        self.assertIn("取った実績を Apple の Game Center に送り、実績の画面にのせます", only)
        self.assertIn("achievements", only)
        lb = pages.privacy("imo", self.CFG, {}, {"leaderboard"})
        self.assertIn("最高スコアを Apple の Game Center に送り、ランキングにのせます。", lb)
        none = pages.privacy("imo", self.CFG, {}, set())
        self.assertNotIn("<h3>Game Center</h3>", none)


if __name__ == "__main__":
    unittest.main(verbosity=1)
