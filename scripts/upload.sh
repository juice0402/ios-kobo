#!/bin/bash
# アプリを署名して App Store Connect（TestFlight）に送る。
#   scripts/upload.sh <app> <ビルド番号>
# 証明書は手で持たない：署名なしで組み立て → App Store Connect の鍵（Admin）でクラウドの配布用証明書を使って署名・送信。
# 環境変数: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8, APPLE_TEAM_ID
set -euo pipefail
APP="$1"
BUILD_NO="$2"
OUT="build/$APP"
PROJ="$OUT/project/App.xcodeproj"

KEY="$HOME/.appstoreconnect/private_keys/AuthKey_${ASC_KEY_ID}.p8"
mkdir -p "$(dirname "$KEY")"
printf '%s\n' "$ASC_KEY_P8" | sed 's/\\n/\n/g' > "$KEY"
chmod 600 "$KEY"
AUTH=(-allowProvisioningUpdates -authenticationKeyPath "$KEY" -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER_ID")

cat > "$OUT/ExportOptions.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key><string>app-store-connect</string>
  <key>destination</key><string>upload</string>
  <key>signingStyle</key><string>automatic</string>
  <key>teamID</key><string>${APPLE_TEAM_ID}</string>
  <key>uploadSymbols</key><true/>
  <key>manageAppVersionAndBuildNumber</key><false/>
</dict>
</plist>
EOF

archive() {
  rm -rf "$OUT/App.xcarchive"
  xcodebuild archive -project "$PROJ" -scheme App -configuration Release \
    -destination 'generic/platform=iOS' -archivePath "$OUT/App.xcarchive" \
    DEVELOPMENT_TEAM="$APPLE_TEAM_ID" CURRENT_PROJECT_VERSION="$BUILD_NO" -quiet "$@"
}
export_upload() {
  xcodebuild -exportArchive -archivePath "$OUT/App.xcarchive" -exportPath "$OUT/export" \
    -exportOptionsPlist "$OUT/ExportOptions.plist" "${AUTH[@]}"
}

if archive CODE_SIGNING_ALLOWED=NO && export_upload; then
  echo "送信できました（署名なしの組み立て → クラウドで署名）"
  exit 0
fi

echo "::warning::署名なしの組み立てからは送れなかったので、署名つきで組み立てなおします"
archive CODE_SIGN_STYLE=Automatic "${AUTH[@]}"
export_upload
echo "送信できました（署名つきの組み立て）"
