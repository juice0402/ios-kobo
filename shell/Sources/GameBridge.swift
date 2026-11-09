// ゲームから呼べる関数（全部のゲームで共通）。ページの JS からは次の名前で見える：
//   window.APP_HAPTIC(kind)  … 振動。light / medium / heavy / success / warning / error / select
//   window.APP_SHARE(text)   … 共有メニュー（Info.plist の GameStoreURL があれば、改行してあとに足す）
//   Game Center（Info.plist に GameLeaderboardID があるアプリだけ）：
//   window.APP_GAMECENTER    … ログインできたら true（そのとき window に 'app-gamecenter' イベント）
//   window.APP_SCORE(n)      … 最高記録を送る（整数）
//   window.APP_RANKING()     … ランキングの画面を開く
// JS → webkit.messageHandlers.app.postMessage({type, ...}) → このクラス。

import UIKit
import WebKit
import GameKit

final class GameBridge: NSObject, WKScriptMessageHandler, GKGameCenterControllerDelegate {
    weak var webView: WKWebView?

    private var lastHaptic: [String: CFTimeInterval] = [:]
    private var impacts: [UIImpactFeedbackGenerator.FeedbackStyle: UIImpactFeedbackGenerator] = [:]
    private lazy var notice = UINotificationFeedbackGenerator()
    private lazy var selection = UISelectionFeedbackGenerator()

    private var gcStarted = false
    private var gcReady = false
    private var pendingLogin: UIViewController?

    /// ページの最初（document start）に入れる JS
    static var startScript: String {
        var js = "(function(){var h=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.app;if(!h)return;"
            + "function post(m){try{h.postMessage(m)}catch(e){}}"
            + "var K={light:1,medium:1,heavy:1,success:1,warning:1,error:1,select:1},last={};"
            + "window.APP_HAPTIC=function(k){k=String(k);if(!Object.prototype.hasOwnProperty.call(K,k))return;"
            + "var t=Date.now();if(last[k]&&t-last[k]<50)return;last[k]=t;post({type:'haptic',kind:k})};"
            + "window.APP_SHARE=function(s){post({type:'share',text:s==null?'':String(s)})};"
        if GameSettings.leaderboardID != nil {
            js += "window.APP_GAMECENTER=false;"
                + "window.APP_SCORE=function(n){n=Math.floor(Number(n));if(window.APP_GAMECENTER!==true||!isFinite(n)||n<0)return;post({type:'score',value:n})};"
                + "window.APP_RANKING=function(){if(window.APP_GAMECENTER===true)post({type:'ranking'})};"
        }
        return js + "})();"
    }

    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
        switch type {
        case "haptic": haptic(body["kind"] as? String ?? "")
        case "share": share(body["text"] as? String ?? "")
        case "score": submit((body["value"] as? NSNumber)?.int64Value)
        case "ranking": showRanking()
        default: break
        }
    }

    /// ページを読み終えたとき（開きなおしたときも）。Game Center のログインは最初の1回だけ始める
    func pageDidLoad() {
        if GameSettings.leaderboardID != nil && !gcStarted {
            gcStarted = true
            GKLocalPlayer.local.authenticateHandler = { [weak self] login, _ in
                DispatchQueue.main.async {
                    guard let self else { return }
                    if let login {
                        // ログインしていない人には iOS のログイン画面（断られても遊べる）
                        self.pendingLogin = login
                        self.presentPendingLogin()
                    } else {
                        self.setReady(GKLocalPlayer.local.isAuthenticated)
                    }
                }
            }
        }
        presentPendingLogin()
        if gcReady { sendState() }
    }

    // MARK: - 振動

    private func haptic(_ kind: String) {
        let now = CACurrentMediaTime()
        if let t = lastHaptic[kind], now - t < 0.05 { return }
        lastHaptic[kind] = now
        switch kind {
        case "light": impact(.light)
        case "medium": impact(.medium)
        case "heavy": impact(.heavy)
        case "success": notice.notificationOccurred(.success)
        case "warning": notice.notificationOccurred(.warning)
        case "error": notice.notificationOccurred(.error)
        case "select": selection.selectionChanged()
        default: break
        }
    }

    private func impact(_ style: UIImpactFeedbackGenerator.FeedbackStyle) {
        let g = impacts[style] ?? UIImpactFeedbackGenerator(style: style)
        impacts[style] = g
        g.impactOccurred()
        g.prepare()
    }

    // MARK: - 共有

    private func share(_ text: String) {
        guard let view = webView, let top = topController(), !(top is UIActivityViewController) else { return }
        var t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if let url = GameSettings.storeURL { t += (t.isEmpty ? "" : "\n") + url }
        guard !t.isEmpty else { return }
        let sheet = UIActivityViewController(activityItems: [t], applicationActivities: nil)
        if let pop = sheet.popoverPresentationController {
            // iPad：画面の下の中央から出す
            let b = view.bounds
            pop.sourceView = view
            pop.sourceRect = CGRect(x: b.midX, y: b.maxY - view.safeAreaInsets.bottom - 12, width: 1, height: 1)
            pop.permittedArrowDirections = [.down]
        }
        top.present(sheet, animated: true)
    }

    // MARK: - Game Center

    private func setReady(_ ready: Bool) {
        gcReady = ready
        sendState()
    }

    private func sendState() {
        webView?.evaluateJavaScript(
            "if(window.APP_RANKING){window.APP_GAMECENTER=\(gcReady);window.dispatchEvent(new Event('app-gamecenter'))}")
    }

    private func presentPendingLogin() {
        guard let login = pendingLogin, let top = topController() else { return }
        pendingLogin = nil
        top.present(login, animated: true)
    }

    private func submit(_ value: Int64?) {
        guard gcReady, let value, value >= 0, let id = GameSettings.leaderboardID,
              GKLocalPlayer.local.isAuthenticated else { return }
        GKLeaderboard.submitScore(Int(value), context: 0, player: GKLocalPlayer.local, leaderboardIDs: [id]) { _ in }
    }

    private func showRanking() {
        guard gcReady, let id = GameSettings.leaderboardID, GKLocalPlayer.local.isAuthenticated,
              let top = topController(), !(top is GKGameCenterViewController) else { return }
        let vc = GKGameCenterViewController(leaderboardID: id, playerScope: .global, timeScope: .allTime)
        vc.gameCenterDelegate = self
        top.present(vc, animated: true)
    }

    func gameCenterViewControllerDidFinish(_ gameCenterViewController: GKGameCenterViewController) {
        gameCenterViewController.dismiss(animated: true)
    }

    private func topController() -> UIViewController? {
        var top = webView?.window?.rootViewController
        while let next = top?.presentedViewController { top = next }
        return top
    }
}
