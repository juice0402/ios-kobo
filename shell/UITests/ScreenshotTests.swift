// App Store 用のスクショを自動で撮る（シミュレーターで動かす）。
// 撮る場面は shots.json（scripts/prepare.py が app.json の screenshots から作る）。

import XCTest

final class ScreenshotTests: XCTestCase {
    struct Plan: Decodable {
        let languages: [String]
        let scenes: [Scene]
    }

    struct Scene: Decodable {
        let name: String
        let wait: Double
        let js: String?
    }

    override func setUp() {
        continueAfterFailure = true
    }

    func testScreenshots() throws {
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: "shots", withExtension: "json"))
        let plan = try JSONDecoder().decode(Plan.self, from: Data(contentsOf: url))

        for lang in plan.languages {
            for scene in plan.scenes {
                let app = XCUIApplication()
                app.launchArguments = ["-AppleLanguages", "(\(lang))", "-AppleLocale", lang.replacingOccurrences(of: "-", with: "_")]
                app.launchEnvironment["SHOT_JS"] = scene.js ?? ""
                print("SHOT start \(lang) \(scene.name)")
                app.launch()
                XCTAssertTrue(app.wait(for: .runningForeground, timeout: 30))
                Thread.sleep(forTimeInterval: scene.wait)

                let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
                attachment.name = "\(lang)__\(scene.name)"
                attachment.lifetime = .keepAlways
                add(attachment)
                print("SHOT done \(lang) \(scene.name)")
                app.terminate()
            }
        }
    }
}
