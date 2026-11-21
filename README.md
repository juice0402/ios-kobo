# ios-kobo

あそびトーク ゲーム工房のゲームを、iPhone・iPad のアプリにして App Store に出すしくみ。
GitHub Actions の Mac（公開リポジトリなので無料）で組み立てる。手元に Mac はいらない。

## しくみ

```
apps/<ゲーム>/app.json   名前・バンドル ID・ゲームのリポジトリと版・言語・スクショの台本
apps/<ゲーム>/icon.png   アイコン（1024px・透明なし）
apps/<ゲーム>/store/     App Store の文（ja・en-US：名前・サブタイトル・説明・キーワード・宣伝文）
apps/<ゲーム>/pages.json サポートのページの文
shell/                   全部のゲームで共通のアプリ（SwiftUI ＋ WKWebView。ゲームは同梱でネット不要）
scripts/prepare.py       ゲームを取りこみ、フォントを同梱し、オフラインの点検をして Xcode のプロジェクトを作る
scripts/pages.py         サポートとプライバシーポリシーのページを docs/ に作る（GitHub Pages）
scripts/shots.py         App Store のスクショ（Linux の headless Chrome）
scripts/promo.py         スクショを宣伝の絵（案A）に包む・縦の宣伝動画（app.json に promo があるアプリ）
scripts/preview.py       App Store のプレビュー動画（本物の画面の録画＋テロップ。app.json に preview があるアプリ）
.github/workflows/ios.yml
.github/workflows/metrics.yml  App Store の数字を毎日集めて枝 metrics へ
```

Actions の「iOS アプリ」を手で動かすときの「すること」:

| すること | 中身 | Apple の鍵 |
| --- | --- | --- |
| check | オフラインの点検・スクショ（iPhone 6.9 インチ・iPad 13 インチ）・Mac で組み立ててシミュレーターで起動 | いらない |
| testflight | 署名して TestFlight へ | いる |
| store | ストアの文とスクショを送る（審査には出さない） | いる |
| review | 審査に出す（文とスクショは送らない。先に store で送る。deliver は文を送ると審査の添付ファイルを消すため） | いる |
| preview | プレビュー動画と縦の宣伝動画を作って成果物にするだけ（App Store Connect には送らない。Mac も使わない） | いらない |
| experiment | 宣伝の絵に包んだスクショで、公開中のページの A/B テストを作る（審査への提出と開始はしない。Mac は使わない。下の「A/B テスト」） | いる |

store では、app.json に preview があるアプリはプレビュー動画も作り、文とスクショのあとに `asc.py previews` で送る（前の動画は入れかえ。fastlane deliver はプレビュー動画を送れないため App Store Connect API で）。promo があるアプリは、スクショが宣伝の絵（案A）に包まれてから送られる。

main に push したときと PR のときに、全部のゲームで check が動く。

## 数字を集める（metrics.yml・asc.py analytics）

Actions の「App Store の数字」が毎日 10:17（日本時間）に、App Store Connect の Analytics Reports API で数字を集め、データだけの枝 `metrics` の `metrics/<app>.csv` に足す（main には push しない）。対象は app.json に `storeUrl` があるアプリ。手で動かすときはアプリの名前を入れられる。

列は `date,impressions,product_page_views,first_time_downloads,redownloads`。報告は App Store Discovery and Engagement と App Store Downloads の Standard・DAILY。

| 列 | 数えるもの |
| --- | --- |
| impressions | Event が Impression |
| product_page_views | Event が Page view で、Page Type が Product page |
| first_time_downloads | Download Type が First-time Download |
| redownloads | Download Type が Redownload（アップデート・復元は数えない） |

- はじめて動かすと、そのアプリの報告（ONGOING）を頼むだけ。最初の報告は24〜48時間後
- その日の数字が決まるのは2〜3日あと。同じ日は、いちばん新しい報告の数で入れかえる（前の報告と足さない）
- 5人・5台より少ない行は Apple が消し、数字にノイズも足されるので、小さいアプリは少なめに出る
- 知らない値・足りない列・知らない報告の名前があると、勝手に数えずに止める（`asc.py` の `ANALYTICS_REPORTS` を直す）
- テストは `python3 scripts/test_asc_analytics.py`（にせの App Store Connect。ios.yml の check でも動く）

## A/B テスト（プロダクトページの最適化・asc.py experiment）

いま公開中のページのスクショを、宣伝の絵（app.json の promo。ひらがなバランスは「画用紙と机」）に包んだスクショとくらべる。スクショだけのテストは新しい版がいらない（アイコンを変えるときだけ版が要る）。プレビュー動画はテストに入れない。

1. Actions の「iOS アプリ」を、app にアプリ、すること に experiment をえらんで動かす。スクショを撮って包み、`asc.py experiment` が App Store Connect にテスト「スクショ 画用紙と机」を作る（トリートメント「画用紙と机」1つ・ja と en-US・iPhone 6.9 インチと iPad 13 インチ・半分の人に新しいスクショ）。同じ名前のテストが準備中なら、作らずに中身を入れかえる。審査中・動いている・終わったテストにはさわらない
2. App Store Connect の「アプリ」→ ひらがなバランス →「プロダクトページの最適化」で、テストを開いてスクショを見て、審査に提出する（ためす案は App Review の承認が要る）
3. 承認されたら、同じ画面で「テストを開始」。テストは一度に1つ・最長90日。iOS 15 以上の人に出る
4. 結果は App Store Connect の「アナリティクス」→「プロダクトページの最適化」で見る（インプレッション・コンバージョン率・改善率）。信頼度が90%になるまで待ってから決める。新しいスクショのほうがよければ、その画面で「トリートメントを適用」

- 割合や名前を変えるときは `python3 scripts/asc.py experiment <app> <スクショのフォルダ> --percent 30 --name 名前`（フォルダは fastlane/screenshots/<言語>/<場面>-<機種>.png の並び）
- テストは `python3 scripts/test_asc_experiment.py`（にせの App Store Connect。ios.yml の check でも動く）

## ゲームから呼べる関数（shell/Sources/GameBridge.swift）

アプリの中だけ window に入る。ゲームは「あるときだけ呼ぶ」書き方にする（ブラウザでは今までどおり）。

| 関数 | 中身 |
| --- | --- |
| `APP_HAPTIC(kind)` | 振動。`light` `medium` `heavy` `success` `warning` `error` `select`（同じ kind は 50ms に1回まで） |
| `APP_SHARE(text)` | 共有メニュー。app.json の `storeUrl` があれば、改行してあとに足す |
| `APP_REVIEW()` | App Store のレビューのお願い（StoreKit）。同じバージョンでは1回だけ、1.5秒待ってほかの画面が出ていないときに。出すかは Apple が決める（365日に3回まで・TestFlight では出ない） |
| `APP_GAMECENTER` | Game Center にログインできたら `true`（そのとき window に `app-gamecenter` イベント） |
| `APP_SCORE(n)` | 最高記録を送る（整数。ログインしていないときは何もしない） |
| `APP_RANKING()` | ランキング（全員・全期間）を開く |

Game Center の3つは、app.json に `"gameCenter": {"leaderboard": "<ID>"}` があるアプリだけ。testflight のときに `scripts/asc.py setup --game-center` が App Store Connect の Game Center とリーダーボード（Best Score・整数・大きい順・最高記録）を、なければ作る。審査に出す前に、バージョンの画面で Game Center をオンにしてリーダーボードを足す（手作業）。

## プレビュー動画（app.json の preview・scripts/preview.py）

アプリの中と同じ HTML を headless Chrome で開き、ページの時計を止めて1コマずつ進めながら撮る（重くてもなめらか・毎回同じ動画）。
iPhone 886×1920・iPad 1200×1600、15〜30秒、30fps、H.264、無音のステレオ AAC。録画はアプリの画面だけで、テロップ・カットイン・指の丸を上に重ねる（Apple 2.3.4）。

| キー | 中身 |
| --- | --- |
| `languages` | 作る言語（ストアの言語） |
| `font`・`style` | テロップのフォント（ゲームに入っている OFL のもの。`build/_fonts` の名前）・見た目（`neon`・`paper`） |
| `capY` | テロップの高さ（画面の上から 0〜1。ゲームの部品にかからない所） |
| `poster` | 表紙のコマ（秒） |
| `seed` | `Math.random` の並び（ゲームより先に入れる。毎回同じ動き） |
| `init` | ゲームより先に動かす JS（Game Center のボタンを出すためのにせの `APP_GAMECENTER` など） |
| `scenes[]` | `len`（秒）・`hash`（`#` のあと）・`js`（読みこんだあと）・`warm`（撮る前に進める秒）・`steps`（`[秒, JS]`）・`captions`（`at`・`to`・`text`〔言語ごとも可〕・`y`）・`cutins` |
| `devices` | 機種ごとに上書きする分（`{"ipad": {"seed": 13}}`。場面の中にも書ける） |

台本の JS で使える道具：`__pv.click(sel)`・`__pv.tap(x,y)`・`__pv.drag(pts,ms)`・`__pv.turn(sel,回数,ms)`・`__pv.hold(sel,ms)`（指の丸も出る）。
ためすときは `python3 scripts/preview.py render <app> --device iphone --lang ja --fast`。

## 宣伝の絵と縦の宣伝動画（app.json の promo・scripts/promo.py）

`promo.headlines`（場面ごとの見出し2行。言語ごとにも書ける）で、スクショを宣伝の絵に包む。iPhone 1320×2868・iPad 2064×2752。元のスクショは `build/<app>/promo/raw`。
見た目は `promo.theme`：`neon`（決めなければこれ）＝案A「ネオンの看板」（紫の夜空・アーチ・光る枠。パチおば）／`paper`＝「画用紙と机」（方眼の画用紙・テープに書いた1行目・墨の2行目と朱の花丸・竹のものさし・白いふちの画面。ひらがなバランス）。paper は `promo.art` にゲームの中の絵（paper・ruler・title）の道を書く。
`promo.motion` があると、縦の宣伝動画（1080×1920・18〜20秒・動く文字）も作る。SNS・あそびトーク用で App Store には送らない。おわりの文は `promo.end.texts`（app.json に `storeUrl` があれば `live`＝「App Storeで配信中」、なければ `soon`＝「配信予定」）。neon のおわりはタイトルから切り出したロゴとおばけ（`promo.end` の logo・ghosts）、paper のおわりはタイトルの絵。paper の場面に `clip`（`from` 秒・`crop` の割合）があると、プレビュー動画（先に preview.py render）のテロップのない所を切り取って画面の中で動かす。
ためすときは `python3 scripts/promo.py shots <app>` → `python3 scripts/promo.py video <app>`（どちらも先に prepare.py と shots.py render）。
`promo.extraVideos` に足すと、別の縦の宣伝動画も作る（`build/<app>/promo/<app>-promo-<name>.mp4`）。いまは theme `sumi`＝「筆と墨」（海外向け・英語の見出し）：和紙に筆の文字（縦書き・ローマ字・朱の判）→ 墨のひと筆の帯の見出しと掛け軸のように開く画面 → 画面いっぱいの墨のひと筆で切りかえ → タイトルの絵の掛け軸。見出しは `promo.headlines` のその言語、フォントは `fonts`（google/fonts の OFL を build/_fonts に取ってくる）。1本だけ作るときは `python3 scripts/promo.py video <app> <name>`（main＝いつもの動画）。

## ゲームを足す

1. `apps/<名前>/` に app.json・icon.png・store/・pages.json・ART.md（絵と音の一覧。プロジェクトの claude/game-art-rule.md の A・B・C）を置く（hiragana-balance をまねる）。B の絵はアプリに入れない
   - pages.json の `browserVersion: false`＝ブラウザ版がまだ工房にない（サポートのページは「ほかのゲームは工房で」の文になる）
   - スクショの場面をボタンの click で作りにくいゲームは、ゲームの側に「自動のためし（navigator.webdriver）のときだけ動く」場面を用意して、台本で呼んでもよい（パチおばの `location.hash='shot=play:7'`。人がさわるアプリでは動かない）
2. `python3 scripts/pages.py` で docs/ を作りなおしてコミット
3. Actions で check → スクショを見て OK なら testflight

## 工房の公開の流れにつなぐ

ゲームのリポジトリのリリース（タグ）のあとに、次を送ると TestFlight まで動く（ゲームのリポジトリに、このリポジトリの Actions を動かせるトークンが要る）。

```
gh workflow run ios.yml -R juice0402/ios-kobo -f app=<名前> -f mode=testflight -f ref=<タグ>
```

App Store に出す版は、app.json の `game.ref` をその版に上げてコミットしておく。

審査の「コンテンツの権利」は app.json の `store.thirdPartyContent`（true＝ほかの人が作った素材を使っていて、使う権利がある。フォントや Canva の絵も入る）。testflight・store・review のたびに `asc.py setup` がアプリに送り、review のときは deliver にも渡す。

## Secrets（Apple の鍵）

`ASC_KEY_ID`・`ASC_ISSUER_ID`・`ASC_KEY_P8`（.p8 の中身）・`APPLE_TEAM_ID`。
鍵は App Store Connect の「ユーザとアクセス → 統合 → App Store Connect API」で、役割 Admin のチームキーを作る（クラウドで署名するため Admin が必要）。

## 決まり

- リポジトリに個人情報（本名・住所・電話番号・メールアドレス）を入れない
- Canva の素材・Canva の AI の絵はアプリに入れない（ゲームのファイルを配る形になるため）
- ライセンスのファイルは置かない（著作権は作者のまま）
