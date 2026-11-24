# PATH QUEST（アプリ）の絵と音の出どころ

決まりはプロジェクトの claude/game-art-rule.md。ゲームのリポジトリは juice0402/path-quest（引き継ぎはプロジェクトの claude/path-handoff.md）。

| もの | 出どころ | アプリに入れる |
| --- | --- | --- |
| 絵（騎士くん・敵・積み木・地面・タイトル・UI の木と紙） | Canva の AI で作った絵（A）。ゲームの games/path-quest/assets/ | index.html の中（base64） |
| ほかの絵（道・飾り・エフェクト） | コードで描く（C） | index.html の中 |
| アイコン | Canva の AI で作った絵（A・2026-11-24・作業用デザイン DAHZ0_Lb0zA の30ページ）。ゲームの docs/kobo/icon.png（1024×1024・透明なし） | icon.png |
| 音（曲・効果音） | ゲームの中で Web Audio で作る（C）。音のファイルなし | index.html の中 |
| 字 | Dela Gothic One・Zen Kaku Gothic New（SIL OFL 1.1）。Google Fonts の link を prepare.py が TTF にして同梱し、ライセンスの文も入れる | Game/fonts |

- B（Canva のライブラリの素材）は使わない（11/24【path】が Canva の持ち主と名前で確かめた）
- ほかの人のキャラクター・外部のライブラリのコードは使っていない
