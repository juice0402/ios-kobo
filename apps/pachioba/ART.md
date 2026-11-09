# 絵と音の一覧（パチおば）

分け方はプロジェクトの claude/game-art-rule.md（A：Canva の AI で言葉から作った絵／B：Canva のライブラリの素材が入った絵／C：コード・手描き・権利がはっきりした素材）。アプリに入れてよいのは A と C。
パチおばの Canva の絵は、どれも Canva の AI（generate-image）で言葉から作り、参考の絵も同じ AI の絵だけ（ライブラリの素材は使っていない）。大きい絵は作業用デザイン DAHaSyBw7z8 に置いて書き出した。作り方の記録は juice0402/kugidama-defense の dev/canva.md。

| もの | 分類 | 出どころ |
| --- | --- | --- |
| ゲームの画面の しくみ（台の レール・杭・玉の 動き・光・火花・文字の ふちどり・ゲージ・画面の 切りかえの 動き） | C | ゲームの コード（canvas と CSS）で 描いている |
| おばけ（46種類＋ポーズちがい・計80まい） | A | Canva の AI で 言葉から 作った 絵（generate-image。参考の 絵も 同じ AI の 絵 MAHaRoS65JU）。背景は Canva の 背景を 消す で 消した。フォルダ FAHaRyNhEFg。ID は juice0402/kugidama-defense の dev/canva/manifest.json の ghosts |
| 台の 奥の 景色（9まい） | A | Canva の AI の 絵：meadow MAHaS59YJ0A・forest MAHaTJ03nvk・mansion MAHaTHpaKUo・desert MAHaTBQKtV4・snow MAHaTL4PneM・volcano MAHaTWTW6vk・castle MAHaTUWy9G8・space MAHaTYm_tsg・heaven MAHaTdUz4NM |
| 台の 枠（9まい） | A | Canva の AI の 絵：meadow MAHaTH_DRw0・forest MAHaTLeK5us・mansion MAHaTJShV-E・desert MAHaTNk3d-s・snow MAHaTAF0n0Y・volcano MAHaTcwKmQU・castle MAHaTY0z2k0・space MAHaTUnvlYI・heaven MAHaTdoi-cU |
| 台の 中の 大きな 物（ピラミッド・雪の 結晶・火山） | A | Canva の AI の 絵：desert_pyr MAHaY1kFV_E・snow_flake MAHaZF4TWG4・volcano_mt MAHaZFeptNk |
| タワー（23）・ギミック（11）・玉（24）の 絵 | A | Canva の AI の 絵。ID は manifest.json の towers・gimmicks・balls |
| ハンドル（9） | A | Canva の AI の 絵：meadow MAHaT0bdOYk・forest MAHaT0In9zM・mansion MAHaTxeZHWA・desert MAHaT1hPMLo・snow MAHaTxJyqM8・volcano MAHaTy_HElM・castle MAHaTzuGgdc・space MAHaT24BVtQ・heaven MAHaT9GFKPw |
| タイトルの 絵 | A | Canva の AI の 絵：key MAHaT97WE4o |
| ボタン・パネル・カード・アイコン・タブ | A | Canva の AI の 絵。ID は manifest.json の ui |
| 演出（FEVER・ボス・WAVE の 板・リボン・王冠・光の すじ） | A | Canva の AI の 絵：fever MAHaUSeH5cQ・boss MAHaUdBLf3g・sheet1 MAHaUv4ucfs・rays |
| アイコン（icon.png） | A | タイトルの 絵（key MAHaT97WE4o）の まん中を 正方形に 切りぬいた もの（文字なし） |
| 画面の 文字 | C | Bungee・Kiwi Maru・M PLUS Rounded 1c（どれも SIL OFL 1.1）。アプリに 同梱し、ライセンスの 文（fonts/*-OFL.txt）も 入れる |
| App Store の スクショ | A＋C | アプリと 同じ ゲームの 画面を headless Chrome で 撮った もの（scripts/shots.py） |
| サポートの ページの 絵 | A | アイコンを 小さく した もの |
| BGM（台ごとの 9曲・ホール・エンディング・ジングル）と 効果音 | C | この ゲームの オリジナル。ゲームの 中で Web Audio で 作曲・合成（音の ファイルなし） |
