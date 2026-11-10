# 宣伝の絵の試作（11/10【ios】・夜 #10 が scripts/ に作り直す）

- make.py：案 a（ネオンの看板・しょーくんが選んだ）と案 b。`python3 make.py a <場面> <見出し1> <見出し2> <スクショ> <出力> <幅> <高さ>`。パスはチャットの作業場所のもの（FONTS＝build/pachioba/project/Game/fonts、ASSETS＝ゲームの index.html から取り出した絵）
- endcard.py：縦の宣伝動画のおわりの1枚（タイトルのスクショからロゴとおばけを切り出す）
- 動画は ffmpeg：各1枚を 2160×3840 に広げて zoompan（偶数は 1.0→1.07、奇数は 1.07→1.0、d=90・30fps）→ xfade（circleopen・slideleft・slideup・slideleft・slideup・fadewhite、0.4秒、offset=2.6×k）→ 最初 0.4秒 fade in・最後 0.5秒 fade out → libx264 crf 18・無音のステレオ AAC
- motion.py：動く文字つきの縦の宣伝動画（しょーくん 11/10「業者の作った動画みたいに」）。HTML の render(t) で1コマずつ描いて撮り、ffmpeg でつなぐ。1行目は1文字ずつ上から弾む／2行目は場面ごとに neon（チカチカ点く）・slam（ドーンと大きく入って画面がゆれ、光の輪）・spin（数字がスロットのようにまわって止まる）・pop（1文字ずつ弾む）／光のすじ／画面は下から上がってゆっくり寄る／切りかえは速いスワイプ＋フラッシュ／おわりはロゴがはねて出る。20.8秒・30fps・1080×1920
