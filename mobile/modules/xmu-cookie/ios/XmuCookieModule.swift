import ExpoModulesCore
import WebKit

public class XmuCookieModule: Module {
  public func definition() -> ModuleDefinition {
    Name("XmuCookie")

    OnCreate {
      HTTPCookieStorage.shared.cookieAcceptPolicy = .always
    }

    AsyncFunction("getCookieForUrlAsync") { (url: String, promise: Promise) in
      guard let target = URL(string: url), let host = target.host, !host.isEmpty else {
        promise.resolve(nil)
        return
      }
      let store = WKWebsiteDataStore.default().httpCookieStore
      store.getAllCookies { cookies in
        let matched = cookies.filter { cookie in
          guard let domain = cookie.domain else { return false }
          let clean = domain.hasPrefix(".") ? String(domain.dropFirst()) : domain
          return host == clean || host.hasSuffix("." + clean)
        }
        .sorted { $0.path.count > $1.path.count }
        if matched.isEmpty {
          promise.resolve(nil)
        } else {
          let header = matched.map { "\($0.name)=\($0.value)" }.joined(separator: "; ")
          promise.resolve(header)
        }
      }
    }

    AsyncFunction("clearCookiesAsync") { (promise: Promise) in
      WKWebsiteDataStore.default().removeData(
        ofTypes: [WKWebsiteDataStore.websiteDataTypeCookies],
        modifiedSince: Date(timeIntervalSince1970: 0)
      ) {
        promise.resolve()
      }
    }
  }
}
