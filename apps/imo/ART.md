# ぽいっと！いも工場（アプリ）の絵と音の出どころ

決まりはプロジェクトの claude/game-art-rule.md。ゲームのリポジトリは juice0402/poitto-imo-kojo。

| もの | 出どころ | アプリに入れる |
| --- | --- | --- |
| 絵（じゃがいも・工場・施設・UI・アイコン） | ぜんぶコードで描いたドット絵（C） | index.html の中 |
| 音（曲・効果音） | ゲームの中で Web Audio で作る（C）。音のファイルなし | index.html の中 |
| 字 | DotGothic16（SIL OFL 1.1）。Google Fonts の link を prepare.py が TTF にして同梱し、ライセンスの文も入れる | Game/fonts |
| アイコン | ゲームの #shot=icon を 1024×1024 で撮ったもの（にこにこいも・C）。ゲームの store/app-icon.png | icon.png |

- ほかの人のキャラクター・外部のライブラリのコードは使っていない
