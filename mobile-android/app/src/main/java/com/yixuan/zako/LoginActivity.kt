package com.yixuan.zako

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Bitmap
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.yixuan.zako.databinding.ActivityLoginBinding
import com.yixuan.zako.network.TronclassClient
import com.yixuan.zako.storage.TokenManager
import kotlinx.coroutines.launch
import java.util.regex.Pattern

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    private lateinit var tokenManager: TokenManager
    private val client = TronclassClient()
    private var capturedStudentId: Long = 0L
    private var isHandlingSuccess = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        tokenManager = TokenManager(this)

        binding.tvClose.setOnClickListener {
            finish()
        }

        binding.tvRefresh.setOnClickListener {
            binding.webView.reload()
        }

        setupWebView()
        binding.webView.loadUrl("https://lnt.xmu.edu.cn")
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(binding.webView, true)

        binding.webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            useWideViewPort = true
            loadWithOverviewMode = true
            cacheMode = WebSettings.LOAD_DEFAULT
            userAgentString = "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        }

        binding.webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                binding.progressBar.visibility = View.VISIBLE
                checkUrlAndCookie(url)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                binding.progressBar.visibility = View.GONE
                checkUrlAndCookie(url)
            }

            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url?.toString()
                checkUrlAndCookie(url)
                return false
            }

            override fun onLoadResource(view: WebView?, url: String?) {
                super.onLoadResource(view, url)
                if (url != null && capturedStudentId == 0L) {
                    val matcher = Pattern.compile("/student/(\\d+)/rollcalls").matcher(url)
                    if (matcher.find()) {
                        capturedStudentId = matcher.group(1)?.toLongOrNull() ?: 0L
                    }
                }
            }
        }
    }

    private fun checkUrlAndCookie(url: String?) {
        if (url == null || isHandlingSuccess) return

        if (url.contains("lnt.xmu.edu.cn") && !url.contains("ids.xmu.edu.cn")) {
            val cookie = CookieManager.getInstance().getCookie("https://lnt.xmu.edu.cn") ?: ""
            if (cookie.contains("session") || cookie.contains("SESSION") || cookie.contains("token") || cookie.contains("tronclass")) {
                isHandlingSuccess = true
                lifecycleScope.launch {
                    tokenManager.cookie = cookie
                    if (capturedStudentId > 0L) {
                        tokenManager.studentId = capturedStudentId
                    }

                    val sem = client.getSemesterInfo(cookie)
                    tokenManager.semesterId = sem.semesterId
                    tokenManager.academicYearId = sem.academicYearId

                    if (tokenManager.studentId == 0L) {
                        val courses = client.getCourses(cookie, sem.semesterId, sem.academicYearId)
                        if (courses.isNotEmpty()) {
                            val firstCourse = courses.first()
                            tokenManager.studentId = 1L
                        }
                    }

                    Toast.makeText(this@LoginActivity, "登录成功喵❤", Toast.LENGTH_SHORT).show()
                    setResult(Activity.RESULT_OK)
                    finish()
                }
            }
        }
    }
}
