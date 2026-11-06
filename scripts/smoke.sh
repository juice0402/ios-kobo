#!/bin/bash
# Mac のシミュレーターで、アプリが起動して落ちないかだけ確かめる。
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
for f in Game/index.html Info.plist PrivacyInfo.xcprivacy; do
  [ -e "${APP_PATH}/$f" ] || { echo "::error::アプリの中に $f がありません"; exit 1; }
done
echo "中身の確認: OK（$(ls "${APP_PATH}/Game" | tr '\n' ' ')）"

UDID=$(python3 scripts/shots.py pick iphone) || exit 1
limit 300 xcrun simctl boot "$UDID" 2>/dev/null
limit 300 xcrun simctl bootstatus "$UDID" -b >/dev/null || { echo "::error::シミュレーターが起動しません"; exit 1; }
limit 120 xcrun simctl install "$UDID" "$APP_PATH" || { echo "::error::入れられません"; exit 1; }
MARK="$RUNNER_TEMP/launch-mark"; touch "$MARK" 2>/dev/null || { MARK=$(mktemp); }
limit 120 xcrun simctl launch "$UDID" "$BUNDLE_ID" -AppleLanguages "(ja)" || { echo "::error::起動しません"; exit 1; }
sleep 20
# 落ちたかどうかはクラッシュの記録で見る（GPU のない Mac ではシミュレーターが重く、画面の撮影や
# 動いているかの問い合わせが返ってこないことがあるため、そちらは参考だけにする）
CRASH=$(find "$HOME/Library/Logs/DiagnosticReports" -newer "$MARK" \( -name "${PRODUCT_NAME}*" -o -name "*${BUNDLE_ID}*" \) 2>/dev/null | head -1)
if [ -n "$CRASH" ]; then
  echo "::error::アプリが落ちました: $(basename "$CRASH")"
  head -c 3000 "$CRASH"; exit 1
elif limit 30 xcrun simctl spawn "$UDID" launchctl list 2>/dev/null | grep -q "UIKitApplication:$BUNDLE_ID"; then
  echo "起動の確認: OK（アプリは動いたまま）"
else
  echo "起動の確認: OK（クラッシュの記録なし。動いているかの問い合わせは返らず）"
fi
limit 30 xcrun simctl terminate "$UDID" "$BUNDLE_ID" >/dev/null 2>&1
limit 120 xcrun simctl shutdown "$UDID" 2>/dev/null
exit 0
