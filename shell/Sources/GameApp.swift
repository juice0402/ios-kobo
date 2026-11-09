// ゲーム工房のアプリの入れ物（全部のゲームで共通）。
// ゲームの HTML はアプリの中の Game/ に入っていて、ネットなしで動く。
// アプリごとの違いは Info.plist の Game〜 の値（scripts/prepare.py が app.json から入れる）。

import SwiftUI
import AVFoundation

@main
struct GameApp: App {
    init() {
        // 消音スイッチに従い、ほかのアプリの音楽を止めない（ゲームの音のふつうの扱い）
        try? AVAudioSession.sharedInstance().setCategory(.ambient, options: [.mixWithOthers])
    }

    var body: some Scene {
        WindowGroup {
            GameScreen()
        }
    }
}

struct GameScreen: View {
    var body: some View {
        ZStack {
            Color("GameBackground").ignoresSafeArea()
            if GameSettings.ignoresSafeArea {
                GameWebView().ignoresSafeArea()
            } else {
                GameWebView()
            }
        }
        .statusBarHidden(true)
        .persistentSystemOverlays(.hidden)
        .defersSystemGestures(on: .all)
    }
}

enum GameSettings {
    private static let info = Bundle.main.infoDictionary ?? [:]

    static var entry: String { info["GameEntry"] as? String ?? "Game/index.html" }

    static var langGlobals: [String] { info["GameLangGlobals"] as? [String] ?? [] }

    static var ignoresSafeArea: Bool { (info["GameSafeArea"] as? String) == "ignore" }

    /// Game Center のリーダーボードの ID（app.json の gameCenter.leaderboard）。ないアプリは Game Center を使わない
    static var leaderboardID: String? { nonEmpty(info["GameLeaderboardID"]) }

    /// 共有の文のあとに足すストアの URL（app.json の storeUrl。公開のあとに入れる）
    static var storeURL: String? { nonEmpty(info["GameStoreURL"]) }

    private static func nonEmpty(_ v: Any?) -> String? {
        guard let s = (v as? String)?.trimmingCharacters(in: .whitespaces), !s.isEmpty else { return nil }
        return s
    }

    /// ゲームが気持ちよく見える大きさ（CSS の px）。iPad など大きい画面では、これが画面いっぱいになるよう拡大する
    static var fitSize: CGSize? {
        guard let parts = info["GameFitSize"] as? [NSNumber], parts.count == 2 else { return nil }
        return CGSize(width: parts[0].doubleValue, height: parts[1].doubleValue)
    }
}
