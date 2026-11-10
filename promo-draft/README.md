# 宣伝の絵の試作（11/10【ios】・夜 #10 が scripts/ に作り直す）

- make.py：案 a（ネオンの看板・しょーくんが選んだ）と案 b。`python3 make.py a <場面> <見出し1> <見出し2> <スクショ> <出力> <幅> <高さ>`。パスはチャットの作業場所のもの（FONTS＝build/pachioba/project/Game/fonts、ASSETS＝ゲームの index.html から取り出した絵）
- endcard.py：縦の宣伝動画のおわりの1枚（タイトルのスクショからロゴとおばけを切り出す）
- 動画は ffmpeg：各1枚を 2160×3840 に広げて zoompan（偶数は 1.0→1.07、奇数は 1.07→1.0、d=90・30fps）→ xfade（circleopen・slideleft・slideup・slideleft・slideup・fadewhite、0.4秒、offset=2.6×k）→ 最初 0.4秒 fade in・最後 0.5秒 fade out → libx264 crf 18・無音のステレオ AAC
