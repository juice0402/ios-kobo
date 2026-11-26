// ゲームから呼べる関数（全部のゲームで共通）。ページの JS からは次の名前で見える：
//   window.APP_HAPTIC(kind)  … 振動。light / medium / heavy / success / warning / error / select
//   window.APP_SHARE(text)   … 共有メニュー（Info.plist の GameStoreURL があれば、改行してあとに足す）
//   window.APP_REVIEW()      … App Store のレビューのお願い（同じバージョンでは1回だけ。1.5秒待ってから）
//   Game Center（Info.plist の GameCenter が true か GameLeaderboardID があるアプリだけ）：
//   window.APP_GAMECENTER    … ログインできたら true（そのとき window に 'app-gamecenter' イベント）
//   window.APP_ACHIEVE(id, percent) … 実績を報告（percent はなくてよい＝100）。ログイン前はためて、ログインのあとに送る
//   window.APP_ACHIEVEMENTS() … 実績の画面を開く
//   ランキングがあるアプリ（GameLeaderboardID）だけ：
//   window.APP_SCORE(n)      … 最高記録を送る（整数。ログイン前は最高値を1つためて、ログインのあとに送る）
//   window.APP_RANKING()     … ランキングの画面を開く
// JS → webkit.messageHandlers.app.postMessage({type, ...}) → このクラス。

import UIKit
import WebKit
import GameKit
import StoreKit

final class GameBridge: NSObject, WKScriptMessageHandler, GKGameCenterControllerDelegate {
    weak var webView: WKWebView?

    private var lastHaptic: [String: CFTimeInterval] = [:]
    private var impacts: [UIImpactFeedbackGenerator.FeedbackStyle: UIImpactFeedbackGenerator] = [:]
    private lazy var notice = UINotificationFeedbackGenerator()
    private lazy var selection = UISelectionFeedbackGenerator()

    private var gcStarted = false
    private var gcReady = false
    private var pendingLogin: UIViewController?
    private var achSending = false
    private var achAgain = false

    // ログイン前（や送れなかったとき）の実績と最高記録。アプリを閉じても残す
    private static let pendingAchKey = "gcPendingAchievements"   // [id: percent]
    private static let doneAchKey = "gcDoneAchievements"         // 100% を送れた id（もう送らない）
    private static let pendingScoreKey = "gcPendingScore"

    private static let reviewKey = "appReviewAskedVersion"
    private var reviewWaiting = false

    /// ページの最初（document start）に入れる JS
    static var startScript: String {
        var js = "(function(){var h=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.app;if(!h)return;"
            + "function post(m){try{h.postMessage(m)}catch(e){}}"
            + "var K={light:1,medium:1,heavy:1,success:1,warning:1,error:1,select:1},last={};"
            + "window.APP_HAPTIC=function(k){k=String(k);if(!Object.prototype.hasOwnProperty.call(K,k))return;"
            + "var t=Date.now();if(last[k]&&t-last[k]<50)return;last[k]=t;post({type:'haptic',kind:k})};"
            + "window.APP_SHARE=function(s){post({type:'share',text:s==null?'':String(s)})};"
            + "window.APP_REVIEW=function(){post({type:'review'})};"
        if GameSettings.gameCenter {
            js += "window.APP_GAMECENTER=false;"
                + "window.APP_ACHIEVE=function(id,p){id=String(id==null?'':id);if(!/^[a-z0-9_]{1,100}$/.test(id))return;"
                + "p=p==null?100:Number(p);if(!isFinite(p))return;post({type:'achieve',id:id,percent:Math.max(0,Math.min(100,p))})};"
                + "window.APP_ACHIEVEMENTS=function(){if(window.APP_GAMECENTER===true)post({type:'achievements'})};"
        }
        if GameSettings.leaderboardID != nil {
            js += "window.APP_SCORE=function(n){n=Math.floor(Number(n));if(!isFinite(n)||n<0)return;post({type:'score',value:n})};"
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
        case "achieve": achieve(body["id"] as? String ?? "", (body["percent"] as? NSNumber)?.doubleValue ?? 100)
        case "achievements": showAchievements()
        case "review": review()
        default: break
        }
    }

    /// ページを読み終えたとき（開きなおしたときも）。Game Center のログインは最初の1回だけ始める
    func pageDidLoad() {
        if GameSettings.gameCenter && !gcStarted {
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

    // MARK: - レビューのお願い

    /// 同じバージョンでは1回だけ。1.5秒待って、アプリが前に出ていてほかの画面（共有・Game Center・ログイン）が
    /// 出ていないときだけ出す。出さなかったときは覚えない（次のチャンスに回す）。出すかどうかは最後に Apple が決める
    private func review() {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? ""
        guard !reviewWaiting, UserDefaults.standard.string(forKey: Self.reviewKey) != version else { return }
        reviewWaiting = true
        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            guard let self else { return }
            self.reviewWaiting = false
            guard UIApplication.shared.applicationState == .active, self.pendingLogin == nil,
                  let window = self.webView?.window, let scene = window.windowScene,
                  window.rootViewController?.presentedViewController == nil else { return }
            UserDefaults.standard.set(version, forKey: Self.reviewKey)
            AppStore.requestReview(in: scene)
        }
    }

    // MARK: - Game Center

    private func setReady(_ ready: Bool) {
        gcReady = ready
        sendState()
        if ready {   // ログイン前にためた分を送る
            flushScore()
            flushAchievements()
        }
    }

    private func sendState() {
        webView?.evaluateJavaScript(
            "if('APP_GAMECENTER' in window){window.APP_GAMECENTER=\(gcReady);window.dispatchEvent(new Event('app-gamecenter'))}")
    }

    private func presentPendingLogin() {
        guard let login = pendingLogin, let top = topController() else { return }
        pendingLogin = nil
        top.present(login, animated: true)
    }

    /// 最高記録。ログイン前・送れなかったときは、いちばん大きい値を1つだけためておき、ログインのあとに送る
    private func submit(_ value: Int64?) {
        guard let value, value >= 0, GameSettings.leaderboardID != nil else { return }
        let d = UserDefaults.standard
        if (d.object(forKey: Self.pendingScoreKey) as? NSNumber)?.int64Value ?? -1 < value {
            d.set(NSNumber(value: value), forKey: Self.pendingScoreKey)
        }
        flushScore()
    }

    private func flushScore() {
        let d = UserDefaults.standard
        guard gcReady, GKLocalPlayer.local.isAuthenticated, let id = GameSettings.leaderboardID,
              let value = (d.object(forKey: Self.pendingScoreKey) as? NSNumber)?.int64Value else { return }
        GKLeaderboard.submitScore(Int(value), context: 0, player: GKLocalPlayer.local, leaderboardIDs: [id]) { error in
            DispatchQueue.main.async {
                // 送れたら消す（そのあいだにもっと大きい記録が来ていたら、それは残す）
                if error == nil, (d.object(forKey: Self.pendingScoreKey) as? NSNumber)?.int64Value == value {
                    d.removeObject(forKey: Self.pendingScoreKey)
                }
            }
        }
    }

    // MARK: - 実績

    /// 実績の報告。100% を一度送れたものは送らない。ほかはためて、ログインしていれば送る（同じ id は大きい % だけ残す）
    private func achieve(_ id: String, _ percent: Double) {
        guard GameSettings.gameCenter, !id.isEmpty, percent.isFinite else { return }
        let d = UserDefaults.standard
        if (d.stringArray(forKey: Self.doneAchKey) ?? []).contains(id) { return }
        var pending = d.dictionary(forKey: Self.pendingAchKey) as? [String: Double] ?? [:]
        let p = min(max(percent, 0), 100)
        if let old = pending[id], old >= p { flushAchievements(); return }
        pending[id] = p
        d.set(pending, forKey: Self.pendingAchKey)
        flushAchievements()
    }

    private func flushAchievements() {
        guard gcReady, GKLocalPlayer.local.isAuthenticated else { return }
        if achSending { achAgain = true; return }   // 送っているあいだに来た分は、終わってからもう一度
        let d = UserDefaults.standard
        let pending = d.dictionary(forKey: Self.pendingAchKey) as? [String: Double] ?? [:]
        guard !pending.isEmpty else { return }
        let list = pending.map { (entry: (key: String, value: Double)) -> GKAchievement in
            let a = GKAchievement(identifier: entry.key)
            a.percentComplete = entry.value
            a.showsCompletionBanner = true
            return a
        }
        achSending = true
        GKAchievement.report(list) { [weak self] error in
            DispatchQueue.main.async {
                guard let self else { return }
                self.achSending = false
                if error == nil {
                    var now = d.dictionary(forKey: Self.pendingAchKey) as? [String: Double] ?? [:]
                    var done = d.stringArray(forKey: Self.doneAchKey) ?? []
                    for (id, p) in pending where now[id] == p {
                        now[id] = nil
                        if p >= 100 && !done.contains(id) { done.append(id) }
                    }
                    d.set(now, forKey: Self.pendingAchKey)
                    d.set(done, forKey: Self.doneAchKey)
                }
                // 失敗したときはためたまま（次のログインか、次の APP_ACHIEVE で送りなおす）
                if self.achAgain {
                    self.achAgain = false
                    self.flushAchievements()
                }
            }
        }
    }

    private func showAchievements() {
        guard gcReady, GKLocalPlayer.local.isAuthenticated,
              let top = topController(), !(top is GKGameCenterViewController) else { return }
        let vc = GKGameCenterViewController(state: .achievements)
        vc.gameCenterDelegate = self
        top.present(vc, animated: true)
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
