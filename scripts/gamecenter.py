#!/usr/bin/env python3
"""ゲームの docs/kobo/gamecenter.json（Game Center のランキングと実績）を読んで点検する。

  python3 scripts/gamecenter.py <gamecenter.json のパス> [--leaderboard <app.json の gameCenter.leaderboard>]

ゲームのチャットが、PR の前に自分のリポジトリで動かす点検と同じ（prepare.py もビルドのたびにこれを使う）。
形はプロジェクトの claude/gamecenter-spec.md。点検すること:
  - leaderboard：id（英数字・_・. で100文字まで）・name の ja と en-US・suffix（なくてよい）
  - achievements：id（英小文字・数字・_ で100文字まで・重なりなし）・points（1〜100・合計1000まで）・
    hidden（true/false）・ja と en-US の name・before・after・バッジの絵
  - バッジの絵：image（なければ achievements/<id>.png。gamecenter.json と同じフォルダから）が
    1024×1024 の PNG か JPEG・RGB（透明なし）・72ppi 以上（ppi が書いていない絵は 72 とみなす）
  - app.json の gameCenter.leaderboard と gamecenter.json の leaderboard.id が両方あってちがえば止める
Pillow が要る（pip install pillow）。うまくいけば中身の短いまとめを出して 0、だめなら ::error:: を出して 1。
"""
import json
import re
import sys
from pathlib import Path

LOCALES = ("ja", "en-US")
ID_RE = re.compile(r"[a-z0-9_]{1,100}")
LEADERBOARD_RE = re.compile(r"[A-Za-z0-9_.]{1,100}")
MAX_POINTS, MAX_TOTAL = 100, 1000
IMAGE_SIZE = (1024, 1024)


class GameCenterError(Exception):
    """gamecenter.json のまちがい（全部まとめて1つ）"""

    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


def _text(v):
    return isinstance(v, str) and v.strip() != "" and "\n" not in v


def _check_image(path, label, problems):
    from PIL import Image
    if not path.is_file():
        problems.append(f"{label}: バッジの絵 {path.name} がありません")
        return
    try:
        with Image.open(path) as im:
            fmt, size, mode, info = im.format, im.size, im.mode, dict(im.info)
    except Exception as e:  # noqa: BLE001  絵として読めないもの
        problems.append(f"{label}: バッジの絵 {path.name} を読めません（{e}）")
        return
    if fmt not in ("PNG", "JPEG"):
        problems.append(f"{label}: バッジの絵は PNG か JPEG（いまは {fmt}）")
    if size != IMAGE_SIZE:
        problems.append(f"{label}: バッジの絵は 1024×1024（いまは {size[0]}×{size[1]}）")
    if mode != "RGB" or "transparency" in info:
        problems.append(f"{label}: バッジの絵は RGB・透明なし（いまは {mode}{'・透明あり' if 'transparency' in info else ''}。"
                        "Image.open(p).convert('RGB').save(p) で直せる）")
    dpi = info.get("dpi")
    if dpi and min(float(dpi[0]), float(dpi[1])) < 71.5:
        problems.append(f"{label}: バッジの絵は 72ppi 以上（いまは {dpi[0]:.0f}ppi）")


def _check_locales(obj, label, keys, problems, required=True):
    for loc in LOCALES:
        d = obj.get(loc)
        if d is None and not required:
            continue
        if not isinstance(d, dict):
            problems.append(f"{label}: {loc} がありません（ja と en-US の両方を書く）")
            continue
        for k in keys:
            if not _text(d.get(k)):
                problems.append(f"{label}: {loc}.{k} がない・空・改行入り")
        extra = sorted(set(d) - set(keys))
        if extra:
            problems.append(f"{label}: {loc} に知らない項目 {', '.join(extra)}（使えるのは {', '.join(keys)}）")


def load(path, app_leaderboard=""):
    """gamecenter.json を読んで点検し、そろえた形で返す。まちがいがあれば GameCenterError。
    返す形: {"leaderboard": {"id", "name": {ja,en-US}, "suffix": {ja,en-US} か {}} か None,
             "achievements": [{"id", "points", "hidden", "image"（Path）, "ja": {...}, "en-US": {...}}]}"""
    path = Path(path)
    problems = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GameCenterError([f"{path.name} を読めません（{e}）"])
    if not isinstance(data, dict):
        raise GameCenterError([f"{path.name} は {{\"leaderboard\": …, \"achievements\": […]}} の形"])
    extra = sorted(set(data) - {"leaderboard", "achievements"})
    if extra:
        problems.append(f"知らない項目 {', '.join(extra)}（使えるのは leaderboard・achievements）")

    lb = data.get("leaderboard")
    out_lb = None
    if lb is not None:
        if not isinstance(lb, dict):
            problems.append("leaderboard は {\"id\", \"name\", \"suffix\"} の形")
        else:
            lid = lb.get("id")
            if not isinstance(lid, str) or not LEADERBOARD_RE.fullmatch(lid):
                problems.append(f"leaderboard.id は英数字・_・. で100文字まで（いまは {lid!r}）")
            name = lb.get("name") if isinstance(lb.get("name"), dict) else {}
            for loc in LOCALES:
                if not _text(name.get(loc)):
                    problems.append(f"leaderboard.name.{loc} がない・空")
            suffix = lb.get("suffix")
            if suffix is not None and not (isinstance(suffix, dict) and all(isinstance(suffix.get(l), str) for l in suffix)
                                           and set(suffix) <= set(LOCALES)):
                problems.append("leaderboard.suffix は {\"ja\": \"段\", \"en-US\": \" floors\"} の形（なくてよい）")
                suffix = None
            lextra = sorted(set(lb) - {"id", "name", "suffix"})
            if lextra:
                problems.append(f"leaderboard に知らない項目 {', '.join(lextra)}")
            out_lb = {"id": lid, "name": {l: name.get(l) for l in LOCALES},
                      "suffix": {l: suffix[l] for l in LOCALES if suffix and suffix.get(l)} if suffix else {}}
            if app_leaderboard and isinstance(lid, str) and lid != app_leaderboard:
                problems.append(f"app.json の gameCenter.leaderboard（{app_leaderboard}）と gamecenter.json の "
                                f"leaderboard.id（{lid}）がちがいます（ランキングの ID は変えない）")

    achs = data.get("achievements", [])
    out_achs = []
    if not isinstance(achs, list):
        problems.append("achievements は [ … ] の形")
        achs = []
    seen, total = set(), 0
    for i, a in enumerate(achs):
        if not isinstance(a, dict):
            problems.append(f"achievements[{i}] は {{…}} の形")
            continue
        aid = a.get("id")
        label = f"実績 {aid}" if isinstance(aid, str) else f"achievements[{i}]"
        if not isinstance(aid, str) or not ID_RE.fullmatch(aid):
            problems.append(f"{label}: id は英小文字・数字・_ で100文字まで（いまは {aid!r}）")
        elif aid in seen:
            problems.append(f"{label}: id が重なっています")
        seen.add(aid)
        pts = a.get("points")
        if not isinstance(pts, int) or isinstance(pts, bool) or not 1 <= pts <= MAX_POINTS:
            problems.append(f"{label}: points は 1〜{MAX_POINTS} の整数（いまは {pts!r}）")
        else:
            total += pts
        hidden = a.get("hidden", False)
        if not isinstance(hidden, bool):
            problems.append(f"{label}: hidden は true か false")
        _check_locales(a, label, ("name", "before", "after"), problems)
        img_rel = a.get("image", f"achievements/{aid}.png")
        img = None
        if not isinstance(img_rel, str) or img_rel.startswith("/") or ".." in Path(img_rel).parts:
            problems.append(f"{label}: image は gamecenter.json のフォルダの中の相対パス（例 achievements/{aid}.png）")
        else:
            img = path.parent / img_rel
            if img.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                problems.append(f"{label}: image は .png か .jpg")
            else:
                _check_image(img, label, problems)
        aextra = sorted(set(a) - {"id", "points", "hidden", "image", *LOCALES})
        if aextra:
            problems.append(f"{label}: 知らない項目 {', '.join(aextra)}")
        out_achs.append({"id": aid, "points": pts, "hidden": hidden is True, "image": img,
                         **{l: a.get(l) for l in LOCALES}})
    if total > MAX_TOTAL:
        problems.append(f"points の合計は {MAX_TOTAL} まで（いまは {total}）")
    if out_lb is None and not out_achs and not problems:
        problems.append("leaderboard も achievements もありません")
    if problems:
        raise GameCenterError(problems)
    return {"leaderboard": out_lb, "achievements": out_achs}


def summary(gc):
    lb = gc["leaderboard"]
    achs = gc["achievements"]
    parts = [f"ランキング {lb['id']}" if lb else "ランキングなし",
             f"実績 {len(achs)} こ（{sum(a['points'] for a in achs)} 点・隠し {sum(a['hidden'] for a in achs)} こ）"]
    return "Game Center: " + "・".join(parts)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="gamecenter.py", description="gamecenter.json の点検")
    ap.add_argument("path")
    ap.add_argument("--leaderboard", default="", help="app.json の gameCenter.leaderboard（くらべるとき）")
    a = ap.parse_args(argv)
    try:
        gc = load(a.path, a.leaderboard)
    except GameCenterError as e:
        for p in e.problems:
            print(f"::error::gamecenter.json: {p}")
        return 1
    print(summary(gc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
