#!/usr/bin/env python3
"""スクショまわりの小さな道具（Mac の Actions で使う）。

  python3 scripts/shots.py pick iphone|ipad        → 使うシミュレーターの UDID を出す
  python3 scripts/shots.py export <xcresult> <出力先> <iphone|ipad>
        → UI テストが撮った画像を fastlane（deliver）の並び（<言語>/<番号>.png）で取り出す
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# App Store に必要な大きさ：iPhone 6.9 インチ・iPad 13 インチ
WANT = {"iphone": [r"iPhone \d+ Pro Max", r"iPhone .*Pro Max", r"iPhone .*Plus"],
        "ipad": [r"iPad Pro 13-inch", r"iPad Pro \(12\.9-inch\)", r"iPad Air 13-inch"]}


def runtime_version(key):
    m = re.search(r"iOS-(\d+)-(\d+)", key)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def pick(kind):
    data = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
    runtimes = sorted((k for k in data["devices"] if ".iOS-" in k), key=runtime_version, reverse=True)
    for pattern in WANT[kind]:
        for rt in runtimes:
            for d in data["devices"][rt]:
                if re.fullmatch(pattern + r"(?: \(.*\))?", d["name"]) or re.search(pattern, d["name"]):
                    print(d["udid"])
                    print(f"{kind}: {d['name']} ({rt.split('.')[-1]})", file=sys.stderr)
                    return
    sys.exit(f"{kind} のシミュレーターが見つかりません")


def export(xcresult, out_dir, kind):
    tmp = Path(out_dir) / f"_raw_{kind}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    subprocess.run(["xcrun", "xcresulttool", "export", "attachments", "--path", xcresult,
                    "--output-path", str(tmp)], check=True)
    manifest = json.loads((tmp / "manifest.json").read_text())
    found = []

    def walk(x):
        if isinstance(x, dict):
            if "exportedFileName" in x:
                found.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(manifest)
    count = 0
    for att in found:
        name = att.get("suggestedHumanReadableName") or att.get("name") or ""
        name = re.sub(r"\.(png|jpe?g|heic)$", "", name, flags=re.I)
        name = re.sub(r"_\d+_[0-9A-Fa-f-]{8,}$", "", name)  # xcresulttool が足す番号と ID
        if "__" not in name:
            continue
        lang, scene = name.split("__", 1)
        dest = Path(out_dir) / lang / f"{scene}-{kind}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp / att["exportedFileName"], dest)
        count += 1
    shutil.rmtree(tmp)
    print(f"{kind}: {count} 枚")
    if count == 0:
        sys.exit("スクショが取り出せませんでした")


if __name__ == "__main__":
    if sys.argv[1] == "pick":
        pick(sys.argv[2])
    elif sys.argv[1] == "export":
        export(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        sys.exit(__doc__)
