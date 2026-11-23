# まぜまぜおかし屋（アプリ）の絵と音の出どころ

くわしい一覧はゲームのリポジトリの docs/ART.md（juice0402/mazemaze-okashiya）。決まりはプロジェクトの claude/game-art-rule.md。

| もの | 出どころ | アプリに入れる |
| --- | --- | --- |
| 絵（キャラ・背景・カード・UI・幕・円盤など） | Codex（絵の依頼箱 juice0402/art-irai）で言葉から作った絵（A）・コードで描いた絵（C） | assets/art |
| 曲 | Lyria（Google・koe-irai で作った）と、コードで作った曲（C） | assets/bgm |
| 声（掛け声） | Gemini TTS（koe-irai） | assets/koe |
| 効果音 | koe-irai の sfx の集：Wyzowl（CC0）・Oculus Audio Pack 01（CC BY 4.0。ゲームのせっていにクレジット）など | assets/se |
| 字 | Zen Maru Gothic・Dela Gothic One・Mochiy Pop One（SIL OFL 1.1。必要な字にしぼった woff2・ライセンスの文も同梱） | assets/font/web・logo.woff2・OFL-*.txt |
| アイコン | 仮：タイトルの絵（title-bg・title-fore・title-honoka）を組んだもの。本番は Codex に頼む（【okashi】） | icon.png |

- 入れないもの：assets/art-stock・assets/slim.json・assets/font/chars.txt・chars-core.txt（字を削るときだけ使う）
- Lyria と Gemini TTS の規約の読み直しの結果は、プロジェクトの claude/reports/ios.md
