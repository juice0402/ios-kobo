#!/bin/bash
# Mac のシミュレーターで、アプリが起動してゲームが出るかだけ確かめる（1枚撮って終わり）。
#   scripts/smoke.sh <app>
# Actions の Mac は GPU がなくキャンバスのゲームが重いので、長く動かさない。どの手順にも時間の上限をつける。
set -uo pipefail
APP="$1"
. "build/$APP/app.env"
limit() { local s="$1"; shift; perl -e 'alarm shift; exec @ARGV' "$s" "$@"; }

limit 1200 xcodebuild build -project "build/$APP/project/App.xcodeproj" -scheme App -configuration Debug \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath build/dd CODE_SIGNING_ALLOWED=NO -quiet || exit 1
APP_PATH=$(ls -d build/dd/Build/Products/Debug-iphonesimulator/*.app | head -1)
echo "組み立て: ${APP_PATH} （$(du -sh "${APP_PATH}" | cut -f1)）"

UDID=$(python3 scripts/shots.py pick iphone) || exit 1
limit 300 xcrun simctl boot "$UDID" 2>/dev/null
limit 300 xcrun simctl bootstatus "$UDID" -b >/dev/null || { echo "::error::シミュレーターが起動しません"; exit 1; }
limit 120 xcrun simctl install "$UDID" "$APP_PATH" || { echo "::error::入れられません"; exit 1; }
limit 120 xcrun simctl launch "$UDID" "$BUNDLE_ID" -AppleLanguages "(ja)" || { echo "::error::起動しません"; exit 1; }
sleep 15
mkdir -p "build/$APP/smoke"
limit 60 xcrun simctl io "$UDID" screenshot --type=png "build/$APP/smoke/iphone-ja.png" >/dev/null 2>&1 \
  || { echo "::error::画面を撮れません"; exit 1; }
# 起動してすぐ落ちていないか（落ちていればホーム画面が写る）
if limit 30 xcrun simctl spawn "$UDID" launchctl list 2>/dev/null | grep -q "UIKitApplication:$BUNDLE_ID"; then
  echo "起動の確認: OK（アプリは動いたまま）"
else
  echo "::error::アプリが起動のあと止まっています"; exit 1
fi
limit 30 xcrun simctl terminate "$UDID" "$BUNDLE_ID" >/dev/null 2>&1
limit 120 xcrun simctl shutdown "$UDID" 2>/dev/null
exit 0
