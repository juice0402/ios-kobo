import SwiftUI
import WebKit

struct GameWebView: UIViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> GameHostView {
        GameHostView(coordinator: context.coordinator)
    }

    func updateUIView(_ uiView: GameHostView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        // ゲームの中のリンク（クレジットのライセンスなど）は Safari で開き、アプリの画面は替えない
        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if let url = action.request.url, let scheme = url.scheme?.lowercased(),
               ["http", "https", "mailto", "tel"].contains(scheme),
               action.targetFrame?.isMainFrame ?? true {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }

        // target="_blank" や window.open
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = action.request.url, url.scheme?.lowercased() != "file" {
                UIApplication.shared.open(url)
            }
            return nil
        }

        // メモリ不足などでページの処理が落ちたら、開きなおす（記録は端末に残っている）
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            webView.reload()
        }

        // alert / confirm をアプリのダイアログで出す
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            present(alert, from: webView, orElse: completionHandler)
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
            alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
            present(alert, from: webView) { completionHandler(false) }
        }

        private func present(_ alert: UIAlertController, from view: UIView, orElse fallback: @escaping () -> Void) {
            var top = view.window?.rootViewController
            while let next = top?.presentedViewController { top = next }
            guard let top else { fallback(); return }
            top.present(alert, animated: true)
        }
    }
}

/// WKWebView を入れる箱。画面の大きさが決まってからゲームを読み込み、大きい画面では拡大する
final class GameHostView: UIView {
    let webView: WKWebView
    private var loaded = false
    private var zoom: CGFloat = 1

    init(coordinator: GameWebView.Coordinator) {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.dataDetectorTypes = []
        config.suppressesIncrementalRendering = true
        webView = WKWebView(frame: .zero, configuration: config)
        super.init(frame: .zero)

        backgroundColor = .clear
        webView.navigationDelegate = coordinator
        webView.uiDelegate = coordinator
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        webView.scrollView.isScrollEnabled = false
        webView.scrollView.bounces = false
        webView.scrollView.contentInsetAdjustmentBehavior = .never
        webView.allowsLinkPreview = false
        webView.allowsBackForwardNavigationGestures = false
        #if DEBUG
        if #available(iOS 16.4, *) { webView.isInspectable = true }
        #endif
        addSubview(webView)
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override func layoutSubviews() {
        super.layoutSubviews()
        webView.frame = bounds
        guard bounds.width > 0, bounds.height > 0 else { return }
        let z = Self.zoom(for: bounds.size)
        if !loaded {
            loaded = true
            zoom = z
            webView.pageZoom = z
            load()
        } else if abs(z - zoom) > 0.01 {
            zoom = z
            webView.pageZoom = z
            webView.evaluateJavaScript("window.APP_ZOOM=\(z);window.dispatchEvent(new Event('resize'));")
        }
        webView.scrollView.pinchGestureRecognizer?.isEnabled = false
    }

    /// iPhone ではそのまま（1倍）。iPad のように広い画面では、ゲームの大きさが画面いっぱいになるまで拡大
    static func zoom(for size: CGSize) -> CGFloat {
        guard let fit = GameSettings.fitSize else { return 1 }
        let z = min(size.width / fit.width, size.height / fit.height)
        guard z > 1.15 else { return 1 }
        return (z * 20).rounded(.down) / 20
    }

    private func load() {
        let ucc = webView.configuration.userContentController

        // 端末の言語をゲームに渡す（WKWebView の navigator.language は英語のままになることがあるため）
        let langs = (try? JSONSerialization.data(withJSONObject: Locale.preferredLanguages))
            .flatMap { String(data: $0, encoding: .utf8) } ?? "[]"
        var start = "window.APP_LANGS=\(langs);window.APP_PLATFORM='ios';window.APP_ZOOM=\(zoom);"
        for name in GameSettings.langGlobals where name.range(of: "^[A-Za-z_$][A-Za-z0-9_$]*$", options: .regularExpression) != nil {
            start += "window.\(name)=window.APP_LANGS;"
        }
        // 消音スイッチに従う（iOS 16.4 から）
        start += "try{if(navigator.audioSession)navigator.audioSession.type='ambient'}catch(e){}"
        ucc.addUserScript(WKUserScript(source: start, injectionTime: .atDocumentStart, forMainFrameOnly: true))

        // 長押しのメニュー・文字の選択・タップの灰色を出さない（アプリらしい手ざわり）
        let css = "html{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;-webkit-tap-highlight-color:transparent}"
            + "input,textarea,[contenteditable]{-webkit-user-select:text;user-select:text}"
        let addCSS = "(function(){var s=document.createElement('style');s.textContent=\(Self.jsString(css));document.head.appendChild(s)})();"
        ucc.addUserScript(WKUserScript(source: addCSS, injectionTime: .atDocumentEnd, forMainFrameOnly: true))

        // スクショの自動撮影のときだけ（scripts/screens.sh が環境変数で渡す）
        if let shot = ProcessInfo.processInfo.environment["SHOT_JS"], !shot.isEmpty {
            let run = "window.addEventListener('load',function(){setTimeout(function(){try{\(shot)}catch(e){console.log(e)}},400)});"
            ucc.addUserScript(WKUserScript(source: run, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        }

        guard let base = Bundle.main.resourceURL,
              case let url = base.appendingPathComponent(GameSettings.entry),
              FileManager.default.fileExists(atPath: url.path) else {
            webView.loadHTMLString("<p style='font:20px sans-serif;padding:40px'>Game file not found.</p>", baseURL: nil)
            return
        }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
    }

    private static func jsString(_ s: String) -> String {
        let data = (try? JSONSerialization.data(withJSONObject: [s])) ?? Data("[\"\"]".utf8)
        let arr = String(data: data, encoding: .utf8) ?? "[\"\"]"
        return "\(arr)[0]"
    }
}
