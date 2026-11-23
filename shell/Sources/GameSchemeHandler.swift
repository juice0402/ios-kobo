import Foundation
import WebKit

/// app.json の "origin": "scheme" のアプリだけ使う。ゲームを file:// ではなく kobo://localhost/ で開き、
/// アプリの中の Game/ のファイルを返す。
/// file:// のページからは fetch も XMLHttpRequest も止められるため（曲・効果音・声を fetch で読むゲーム。まぜまぜおかし屋）。
/// 住所（origin）が変わると localStorage のセーブの場所も変わるので、出したあとのアプリで切りかえない。
final class GameSchemeHandler: NSObject, WKURLSchemeHandler {
    static let scheme = "kobo"
    static let host = "localhost"

    private let root: URL
    private let queue = DispatchQueue(label: "GameSchemeHandler", qos: .userInitiated)
    /// 止められた（stop の来た）読み込み。止められたあとに task を呼ぶとアプリが落ちるため、メインで見る
    private var stopped = Set<ObjectIdentifier>()

    init(root: URL) {
        self.root = root.standardizedFileURL
    }

    /// 入口のページの住所（例 kobo://localhost/index.html）
    static func url(for relativePath: String) -> URL? {
        var c = URLComponents()
        c.scheme = scheme
        c.host = host
        c.path = "/" + relativePath
        return c.url
    }

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let url = task.request.url else {
            task.didFailWithError(URLError(.badURL))
            return
        }
        let id = ObjectIdentifier(task)
        var path = url.path
        if path.isEmpty || path == "/" { path = "/index.html" }
        let file = root.appendingPathComponent(String(path.dropFirst())).standardizedFileURL

        queue.async { [weak self] in
            guard let self else { return }
            // Game/ の外のファイルは返さない
            let inside = file.path.hasPrefix(self.root.path + "/")
            let data: Data? = inside ? (try? Data(contentsOf: file, options: .mappedIfSafe)) : nil
            DispatchQueue.main.async {
                if self.stopped.remove(id) != nil { return }
                let status = data == nil ? 404 : 200
                let body = data ?? Data()
                let headers = [
                    "Content-Type": data == nil ? "text/plain" : Self.mimeType(file.pathExtension),
                    "Content-Length": String(body.count),
                    "Cache-Control": "no-cache",
                ]
                guard let res = HTTPURLResponse(url: url, statusCode: status, httpVersion: "HTTP/1.1", headerFields: headers) else {
                    task.didFailWithError(URLError(.cannotParseResponse))
                    return
                }
                task.didReceive(res)
                task.didReceive(body)
                task.didFinish()
            }
        }
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {
        stopped.insert(ObjectIdentifier(task))
    }

    static func mimeType(_ ext: String) -> String {
        switch ext.lowercased() {
        case "html", "htm": return "text/html; charset=utf-8"
        case "js", "mjs": return "text/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json": return "application/json; charset=utf-8"
        case "txt": return "text/plain; charset=utf-8"
        case "svg": return "image/svg+xml"
        case "webp": return "image/webp"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "gif": return "image/gif"
        case "mp3": return "audio/mpeg"
        case "m4a": return "audio/mp4"
        case "wav": return "audio/wav"
        case "ogg": return "audio/ogg"
        case "woff2": return "font/woff2"
        case "woff": return "font/woff"
        case "ttf": return "font/ttf"
        case "otf": return "font/otf"
        default: return "application/octet-stream"
        }
    }
}
