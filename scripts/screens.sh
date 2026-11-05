#!/bin/bash
# シミュレーターで組み立てて、iPhone（6.9 インチ）と iPad（13 インチ）でスクショを撮る。
#   scripts/screens.sh <app>
# 撮る場面は app.json の screenshots（言語ごと・場面ごとにアプリを起動しなおして撮る）。
set -uo pipefail
APP="$1"
P="build/$APP/project/App.xcodeproj"
OUT="build/$APP/fastlane/screenshots"
. "build/$APP/app.env"

xcodebuild build -project "$P" -scheme App -configuration Debug -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath build/dd CODE_SIGNING_ALLOWED=NO -quiet || exit 1
APP_PATH=$(ls -d build/dd/Build/Products/Debug-iphonesimulator/*.app | head -1)
echo "組み立て: $APP_PATH"

# 台本を「言語<TAB>場面<TAB>待つ秒<TAB>JS」の行にする
PLAN=$(python3 - "$APP" <<'EOF'
import json, sys
cfg = json.load(open(f"apps/{sys.argv[1]}/app.json", encoding="utf-8"))
sh = cfg.get("screenshots", {"languages": ["en-US"], "scenes": [{"name": "1", "wait": 4}]})
for lang in sh["languages"]:
    for s in sh["scenes"]:
        print("\t".join([lang, s["name"], str(s["wait"]), s.get("js", "").replace("\t", " ").replace("\n", " ")]))
EOF
)

failed=0
for kind in iphone ipad; do
  UDID=$(python3 scripts/shots.py pick "$kind") || exit 1
  xcrun simctl boot "$UDID" 2>/dev/null
  xcrun simctl bootstatus "$UDID" -b >/dev/null
  xcrun simctl install "$UDID" "$APP_PATH" || exit 1
  while IFS=$'\t' read -r lang scene wait js; do
    [ -z "$lang" ] && continue
    xcrun simctl terminate "$UDID" "$BUNDLE_ID" >/dev/null 2>&1
    SIMCTL_CHILD_SHOT_JS="$js" xcrun simctl launch "$UDID" "$BUNDLE_ID" \
      -AppleLanguages "($lang)" -AppleLocale "${lang/-/_}" >/dev/null || { failed=1; echo "::error::起動できません $kind $lang $scene"; continue; }
    sleep "$wait"
    mkdir -p "$OUT/$lang"
    f="$OUT/$lang/$scene-$kind.png"
    if xcrun simctl io "$UDID" screenshot --type=png "$f" >/dev/null 2>&1; then
      echo "撮影: $f $(python3 -c "from PIL import Image;print('x'.join(map(str,Image.open('$f').size)))")"
    else
      failed=1; echo "::error::撮れません $kind $lang $scene"
    fi
  done <<< "$PLAN"
  xcrun simctl terminate "$UDID" "$BUNDLE_ID" >/dev/null 2>&1
  xcrun simctl shutdown "$UDID" 2>/dev/null
done
exit $failed
