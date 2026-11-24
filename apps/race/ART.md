# ぶっとびチェイス（アプリ）の絵と音の出どころ

決まりはプロジェクトの claude/game-art-rule.md。ゲームのリポジトリは juice0402/buttobi-chase（くわしくはその docs/ART.md）。

| もの | 出どころ | アプリに入れる |
| --- | --- | --- |
| タイトルの絵（縦・横） | Canva の AI で作った絵（A・2026-11-17）。ゲームの assets/title.webp・title-wide.webp | index.html の中（base64） |
| アイコン | Canva の AI で作った絵（A・2026-11-17）。ゲームの docs/kobo/icon.png（1024×1024） | icon.png |
| ほかの絵（車・街・エフェクト・UI） | コードで描く（C） | index.html の中 |
| 音（曲・効果音） | ゲームの中で Web Audio で作る（C）。音のファイルなし | index.html の中 |
| 字 | Dela Gothic One・Zen Maru Gothic（SIL OFL 1.1）。Google Fonts の link を prepare.py が TTF にして同梱し、ライセンスの文も入れる | Game/fonts |

- B（Canva のライブラリの素材）は使わない
- ほかの人のキャラクター・実在の車の形やマーク・外部のライブラリのコードは使っていない
