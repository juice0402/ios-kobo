# review-media（データだけの枝）

App Store の審査の添付ファイル（実機の画面収録など）を置く枝。main には入れない。

- `<app>/` のファイルを、Actions「iOS アプリ」の mode attach が「App Review に関する情報」に添付する（scripts/asc.py attach）
- 公開のリポジトリなので、通知・個人の情報（名前・メール・Game Center の名前など）が映っていないものだけ置く
- 動画は H.264 で小さくしてから（いまは横 1080・30fps）
