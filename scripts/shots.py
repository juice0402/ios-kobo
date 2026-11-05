#!/usr/bin/env python3
"""スクショまわりの小さな道具（Mac の Actions で使う）。

  python3 scripts/shots.py pick iphone|ipad        → 使うシミュレーターの UDID を出す
"""
import json
import re
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


if __name__ == "__main__":
    if sys.argv[1] == "pick":
        pick(sys.argv[2])
    else:
        sys.exit(__doc__)
