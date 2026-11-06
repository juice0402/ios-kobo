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
| あそびトークの工房の絵（?skin=kobo） | B | アプリには入れない（ゲームのリポジトリにもない。アプリは ?skin を渡さない） |
| BGM | C | このゲームのオリジナル。ゲームの中で Web Audio で作曲・合成（音のファイルなし。前のフリー素材の曲は出どころが分からず 2026-11-06 に差しかえ） |
