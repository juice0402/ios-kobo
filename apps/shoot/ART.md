# ぜんぶのせシップ（アプリ）の絵と音の出どころ

決まりはプロジェクトの claude/game-art-rule.md。ゲームのリポジトリは juice0402/shoot-game（くわしくはその docs/ART.md）。

| もの | 出どころ | アプリに入れる |
| --- | --- | --- |
| アイコン | Canva の AI で作った絵（A・2026-11-24・しょーくん「キャンバで描いてもらって」）。Canva のメディア MAHb0Ds2ZzA を作業用デザイン DAHb0PAE8ZI の2ページ（2048px）に置いて書き出し → 白い角を切って 1024px・透明なし | icon.png |
| ゲームの絵（機体・装備・敵・背景・エフェクト・表紙） | ぜんぶコードで描くドット（C） | index.html の中 |
| 音（BGM 12曲・効果音） | ゲームの中で Web Audio で作る（C）。音のファイルなし | index.html の中 |
| 字 | DotGothic16・Press Start 2P（SIL OFL 1.1）。Google Fonts の link を prepare.py が TTF にして同梱し、ライセンスの文も入れる | Game/fonts |

- B（Canva のライブラリの素材）は使わない
- アイコンだけ A。ゲームの中の絵は C のまま（Canva は使わない）
