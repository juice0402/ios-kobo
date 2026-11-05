# ios-kobo

あそびトーク ゲーム工房のゲームを、iPhone・iPad のアプリにして App Store に出すしくみ。
GitHub Actions の Mac（公開リポジトリなので無料）で組み立てる。手元に Mac はいらない。

## しくみ

```
apps/<ゲーム>/app.json   名前・バンドル ID・ゲームのリポジトリと版・言語・スクショの台本
apps/<ゲーム>/icon.png   アイコン（1024px・透明なし）
apps/<ゲーム>/store/     App Store の文（ja・en-US：名前・サブタイトル・説明・キーワード・宣伝文）
apps/<ゲーム>/pages.json サポートのページの文
shell/                   全部のゲームで共通のアプリ（SwiftUI ＋ WKWebView。ゲームは同梱でネット不要）
scripts/prepare.py       ゲームを取りこみ、フォントを同梱し、オフラインの点検をして Xcode のプロジェクトを作る
scripts/pages.py         サポートとプライバシーポリシーのページを docs/ に作る（GitHub Pages）
.github/workflows/ios.yml
```

Actions の「iOS アプリ」を手で動かすときの「すること」:

| すること | 中身 | Apple の鍵 |
| --- | --- | --- |
| check | 組み立て・オフラインの点検・スクショ（iPhone 6.9 インチ・iPad 13 インチ） | いらない |
| testflight | 署名して TestFlight へ | いる |
| store | ストアの文とスクショを送る（審査には出さない） | いる |
| review | ストアの文とスクショを送って審査に出す | いる |

main に push すると、全部のゲームで check が動く。

## ゲームを足す

1. `apps/<名前>/` に app.json・icon.png・store/・pages.json を置く（hiragana-balance をまねる）
2. `python3 scripts/pages.py` で docs/ を作りなおしてコミット
3. Actions で check → スクショを見て OK なら testflight

## 工房の公開の流れにつなぐ

ゲームのリポジトリのリリース（タグ）のあとに、次を送ると TestFlight まで動く（ゲームのリポジトリに、このリポジトリの Actions を動かせるトークンが要る）。

```
gh workflow run ios.yml -R juice0402/ios-kobo -f app=<名前> -f mode=testflight -f ref=<タグ>
```

App Store に出す版は、app.json の `game.ref` をその版に上げてコミットしておく。

## Secrets（Apple の鍵）

`ASC_KEY_ID`・`ASC_ISSUER_ID`・`ASC_KEY_P8`（.p8 の中身）・`APPLE_TEAM_ID`。
鍵は App Store Connect の「ユーザとアクセス → 統合 → App Store Connect API」で、役割 Admin のチームキーを作る（クラウドで署名するため Admin が必要）。

## 決まり

- リポジトリに個人情報（本名・住所・電話番号・メールアドレス）を入れない
- Canva の素材・Canva の AI の絵はアプリに入れない（ゲームのファイルを配る形になるため）
- ライセンスのファイルは置かない（著作権は作者のまま）
