import SwiftUI
import WebKit

struct GameBrowser: UIViewRepresentable {
    let url: URL
    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = true
        let web = WKWebView(frame: .zero, configuration: config)
        web.scrollView.bounces = false
        web.scrollView.isScrollEnabled = false
        web.load(URLRequest(url: url))
        return web
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

struct ContentView: View {
    private var platformURL: URL? {
        guard let value = Bundle.main.object(forInfoDictionaryKey: "SamiDevPlatformURL") as? String,
              var parts = URLComponents(string: value), parts.scheme == "https",
              let host = parts.host, !host.isEmpty,
              host != "game.example.com", host != "example.com",
              parts.user == nil, parts.password == nil,
              parts.query == nil, parts.fragment == nil,
              ["", "/", "/platform/"].contains(parts.path) else { return nil }
        parts.path = "/platform/"
        return parts.url
    }
    var body: some View {
        if let url = platformURL {
            GameBrowser(url: url).ignoresSafeArea()
        } else {
            Text("يلزم ضبط SamiDevPlatformURL في إعدادات التطبيق على نطاق المنصة الفعلي عبر HTTPS.")
                .padding()
        }
    }
}
