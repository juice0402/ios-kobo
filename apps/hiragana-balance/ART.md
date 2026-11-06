# 絵と音の一覧（ひらがなバランス）

分け方はプロジェクトの claude/game-art-rule.md（A：Canva の AI で言葉から作った絵／B：Canva のライブラリの素材が入った絵／C：コード・手描き・権利がはっきりした素材）。アプリに入れてよいのは A と C。

| もの | 分類 | 出どころ |
| --- | --- | --- |
| ゲームの画面（方眼紙・定規・机・カード・回転の矢印・墨のしずく・花丸） | C | ゲームのコード（canvas と CSS）で描いている |
| 積む文字の形 | C | Yuji Syuku（SIL OFL 1.1）のアウトラインを太らせたもの |
| 画面の文字 | C | Klee One（SIL OFL 1.1）。アプリに同梱し、ライセンスの文（fonts/KleeOne-OFL.txt）も入れる |
| アイコン（icon.png） | C | ゲームの文字の形からコードで描いたもの。juice0402/hiragana-balance の assets/icons/icon_C_card.png（2026-10-07） |
| App Store のスクショ | C | アプリと同じゲームの画面を headless Chrome で撮ったもの（scripts/shots.py） |
| サポートのページの絵 | C | アイコンを小さくしたもの |
| 工房の見た目（skins/kobo。app.json の skin） | A | Canva の AI で言葉から作った絵（11/6 に Canva で確認。どれもアカウントの AI の生成物で、ライブラリの素材は入っていない）。プロンプトの記録はなく、絵の説明と ID を残す |
| ├ タイトル title.webp | A＋C | デザイン DAHZSUip0so（2026-10-28）。背景は AI の絵 MAHZScqTkV4「学校の机と文房具」。題名と積んだ文字は Yuji Syuku・Klee One（OFL）の形を図形にしたもの、テープ・花丸も図形。1200x1800 で書き出し |
| ├ 背景 bg.webp | A | デザイン DAHZV8OkgwM（2026-10-29）。AI の絵 MAHZVxO4qc0「クリーム色の壁と木の幅木、うすい方眼の床」 |
| ├ 机 desk.webp | A | デザイン DAHZVyCbIw8 の1ページ（2026-10-29）。AI の絵の背景を消したもの MAHZV_NSSSU「学校の机（正面から）」 |
| ├ ものさし ruler.webp | A | 同じデザインの2ページ。AI の絵 MAHZV7RJtEE「もようのない竹のものさし」（目盛りはコード） |
| ├ ゲームオーバー over.webp | A | 同じデザインの3ページ。AI の絵 MAHZWNcrk54「くずれた木のつみきと小さな机」 |
| ├ 木のコマ disc.webp | A | 同じデザインの4ページ。AI の絵の背景を消したもの MAHZWBlefSg |
| └ 紙 paper.webp | A | 同じデザインの5ページ。AI の絵 MAHZWCwtclM「クリーム色の画用紙」 |
| BGM | C | このゲームのオリジナル。ゲームの中で Web Audio で作曲・合成（音のファイルなし。前のフリー素材の曲は出どころが分からず 2026-11-06 に差しかえ） |
