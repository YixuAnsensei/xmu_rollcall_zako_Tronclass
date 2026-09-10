package expo.modules.xmucookie

import android.webkit.CookieManager
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class XmuCookieModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("XmuCookie")

    OnCreate {
      CookieManager.getInstance().setAcceptCookie(true)
    }

    AsyncFunction("getCookieForUrlAsync") { url: String ->
      CookieManager.getInstance().getCookie(url)
    }

    AsyncFunction("clearCookiesAsync") {
      val cm = CookieManager.getInstance()
      cm.removeAllCookies(null)
      cm.flush()
    }
  }
}
