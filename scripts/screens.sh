#!/bin/bash
# シミュレーターで組み立てて、iPhone と iPad でスクショを撮る。
#   scripts/screens.sh <app>
# 失敗しても撮れた分は取り出し、失敗の理由を出してから止まる。
set -uo pipefail
APP="$1"
P="build/$APP/project/App.xcodeproj"
OUT="build/$APP/fastlane/screenshots"

xcodebuild build-for-testing -project "$P" -scheme App -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath build/dd CODE_SIGNING_ALLOWED=NO -quiet || exit 1

failed=0
for kind in iphone ipad; do
  UDID=$(python3 scripts/shots.py pick "$kind") || exit 1
  R="build/$APP/$kind.xcresult"
  xcrun simctl boot "$UDID" 2>/dev/null
  xcrun simctl bootstatus "$UDID" -b >/dev/null
  xcodebuild test-without-building -project "$P" -scheme App -destination "id=$UDID" \
    -derivedDataPath build/dd -resultBundlePath "$R" 2>&1 \
    | grep -E "SHOT|error|Test Case|Executed|XCTAssert|failed|passed" | grep -v -E "^\s*$" | tail -20
  st=${PIPESTATUS[0]}
  if [ "$st" -ne 0 ]; then
    failed=1
    echo "::error::$kind のスクショのテストが失敗しました"
    xcrun xcresulttool get test-results summary --path "$R" --format json 2>/dev/null \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); [print("  ", f.get("testName"), ":", f.get("failureText")) for f in d.get("testFailures", [])]' || true
  fi
  python3 scripts/shots.py export "$R" "$OUT" "$kind" || failed=1
  xcrun simctl shutdown "$UDID" 2>/dev/null
done
exit $failed
