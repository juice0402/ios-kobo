# 開発メモ（ios-kobo）

- 中身と使い方は README.md。ゲームの HTML はここに置かず、ビルドのたびに app.json の game.repo / game.ref から取る
- shell/ は全部のゲームで共通。ゲームごとの違いは app.json → Info.plist の Game〜 の値で渡す（GameEntry・GameLangGlobals・GameSafeArea・GameFitSize）
- アプリがゲームに渡すもの：`window.APP_LANGS`（端末の言語）・`APP_PLATFORM='ios'`・`APP_ZOOM`（iPad で拡大した倍率）。langGlobals の名前にも APP_LANGS を入れる
- ゲームから呼べる関数（GameBridge.swift・README の表）：`APP_HAPTIC(kind)`・`APP_SHARE(text)`・Game Center のアプリだけ `APP_GAMECENTER`・`APP_SCORE(n)`・`APP_RANKING()`。app.json の `gameCenter.leaderboard` → GameLeaderboardID と entitlements、`storeUrl` → GameStoreURL。署名なしの組み立てには entitlements が入らないので upload.sh が ad-hoc で入れる
- スクショの台本（app.json の screenshots.scenes の js）はページの中で動く。ゲームの中の変数は見えない前提で、ボタンの click とキャンバスへの PointerEvent で動かす。直したら headless の Chrome で先に試す
- スクショは Linux の headless Chrome で撮る（scripts/shots.py render。画面の大きさ・倍率・iPad の拡大はアプリと同じ計算）。Actions の Mac のシミュレーターは GPU がなくキャンバスのゲームで止まるので、起動の確認（scripts/smoke.sh）だけにする
- 署名は App Store Connect API の Admin の鍵だけ（証明書・プロファイルは持たない）。scripts/upload.sh
- ストアの文は site-principles.md の「文章」の決まりを守る。長さは prepare.py が点検する
- 絵はプロジェクトの claude/game-art-rule.md（A・C だけアプリに入れる）。ゲームごとに apps/<ゲーム>/ART.md に絵と音の出どころを書く
- app.json の zoom "game"＝ゲームが自分で拡大（アプリはページを拡大しない）。skin＝game.extra の skins/<名前> を同梱し、window.APP_SKIN で渡す（prepare.py の inject_skin）
- App Store Connect の手作業（初回だけ）：アプリの作成・価格（無料）・App のプライバシー（データの収集なし）・年齢区分・審査の連絡先・TestFlight のテスター
- プレビュー動画は scripts/preview.py（app.json の preview）。ページの時計を止めて1コマずつ撮る。台本は時刻で動くので、ゲームの動きが機種でずれるときは preview.devices で上書き。テロップはゲームの部品にかけない
- 宣伝の絵と縦の宣伝動画は scripts/promo.py（app.json の promo）。見た目は promo.theme（neon＝案A・paper＝画用紙と机）。見出しは promo から入れ、手で打たない。neon を直すときはパチおばの絵が変わらないか、前と後のスクショをくらべる
