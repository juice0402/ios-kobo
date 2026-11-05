# 開発メモ（ios-kobo）

- 中身と使い方は README.md。ゲームの HTML はここに置かず、ビルドのたびに app.json の game.repo / game.ref から取る
- shell/ は全部のゲームで共通。ゲームごとの違いは app.json → Info.plist の Game〜 の値で渡す（GameEntry・GameLangGlobals・GameSafeArea・GameFitSize）
- アプリがゲームに渡すもの：`window.APP_LANGS`（端末の言語）・`APP_PLATFORM='ios'`・`APP_ZOOM`（iPad で拡大した倍率）。langGlobals の名前にも APP_LANGS を入れる
- スクショの台本（app.json の screenshots.scenes の js）はページの中で動く。ゲームの中の変数は見えない前提で、ボタンの click とキャンバスへの PointerEvent で動かす。直したら headless の Chrome で先に試す
- 署名は App Store Connect API の Admin の鍵だけ（証明書・プロファイルは持たない）。scripts/upload.sh
- ストアの文は site-principles.md の「文章」の決まりを守る。長さは prepare.py が点検する
- App Store Connect の手作業（初回だけ）：アプリの作成・価格（無料）・App のプライバシー（データの収集なし）・年齢区分・審査の連絡先・TestFlight のテスター
