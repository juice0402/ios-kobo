# 開発メモ（ios-kobo）

- 中身と使い方は README.md。ゲームの HTML はここに置かず、ビルドのたびに app.json の game.repo / game.ref から取る
- shell/ は全部のゲームで共通。ゲームごとの違いは app.json → Info.plist の Game〜 の値で渡す（GameEntry・GameLangGlobals・GameSafeArea・GameFitSize）
- アプリがゲームに渡すもの：`window.APP_LANGS`（端末の言語）・`APP_PLATFORM='ios'`・`APP_ZOOM`（iPad で拡大した倍率）。langGlobals の名前にも APP_LANGS を入れる
- スクショの台本（app.json の screenshots.scenes の js）はページの中で動く。ゲームの中の変数は見えない前提で、ボタンの click とキャンバスへの PointerEvent で動かす。直したら headless の Chrome で先に試す
- スクショは Linux の headless Chrome で撮る（scripts/shots.py render。画面の大きさ・倍率・iPad の拡大はアプリと同じ計算）。Actions の Mac のシミュレーターは GPU がなくキャンバスのゲームで止まるので、起動の確認（scripts/smoke.sh）だけにする
- 署名は App Store Connect API の Admin の鍵だけ（証明書・プロファイルは持たない）。scripts/upload.sh
- ストアの文は site-principles.md の「文章」の決まりを守る。長さは prepare.py が点検する
- 絵はプロジェクトの claude/game-art-rule.md（A・C だけアプリに入れる）。ゲームごとに apps/<ゲーム>/ART.md に絵と音の出どころを書く
- app.json の zoom "game"＝ゲームが自分で拡大（アプリはページを拡大しない）。skin＝game.extra の skins/<名前> を同梱し、window.APP_SKIN で渡す（prepare.py の inject_skin）
- App Store Connect の手作業（初回だけ）：アプリの作成・価格（無料）・App のプライバシー（データの収集なし）・年齢区分・審査の連絡先・TestFlight のテスター
