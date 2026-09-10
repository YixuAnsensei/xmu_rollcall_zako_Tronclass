package com.yixuan.zako

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.yixuan.zako.databinding.ActivityMainBinding
import com.yixuan.zako.engine.RadarEngine
import com.yixuan.zako.model.Course
import com.yixuan.zako.model.RollcallRecord
import com.yixuan.zako.network.TronclassClient
import com.yixuan.zako.storage.TokenManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var tokenManager: TokenManager
    private val client = TronclassClient()
    private lateinit var radarEngine: RadarEngine

    private val courseList = mutableListOf<Course>()
    private var selectedCourse: Course? = null
    private var currentRollcall: RollcallRecord? = null
    private var currentNumberCode: String? = null

    private val loginLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            updateLoginUi()
            loadCourses()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        tokenManager = TokenManager(this)
        radarEngine = RadarEngine(client)

        setupListeners()
        updateLoginUi()

        if (tokenManager.isLoggedIn) {
            appendLog("⚡ 检测到历史登录凭证，正在唤醒主人课程喵❤...")
            loadCourses()
        } else {
            appendLog("👉 尚未登录，请点击右上角【登录 Tronclass】喵~")
        }
    }

    private fun setupListeners() {
        binding.btnLogin.setOnClickListener {
            val intent = Intent(this, LoginActivity::class.java)
            loginLauncher.launch(intent)
        }

        binding.btnRefreshCourses.setOnClickListener {
            if (!tokenManager.isLoggedIn) {
                Toast.makeText(this, "请先登录喵❤", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            loadCourses()
        }

        binding.spinnerCourses.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                if (position in courseList.indices) {
                    selectedCourse = courseList[position]
                    binding.tvSelectedCourseInfo.text = "已选课程: ${selectedCourse?.title} (ID: ${selectedCourse?.id})"
                    appendLog("👉 已切换课程：${selectedCourse?.title}喵")
                }
            }

            override fun onNothingSelected(parent: AdapterView<*>?) {
                selectedCourse = null
            }
        }

        binding.btnCheckRollcall.setOnClickListener {
            checkRollcall()
        }

        binding.btnNumberSign.setOnClickListener {
            executeNumberSign()
        }

        binding.btnRadarSign.setOnClickListener {
            executeRadarSign()
        }

        binding.tvClearLog.setOnClickListener {
            binding.tvLogs.text = ""
        }
    }

    private fun updateLoginUi() {
        if (tokenManager.isLoggedIn) {
            binding.tvLoginStatus.text = "已连接厦大畅课喵❤ (学号: ${tokenManager.studentId})"
            binding.tvLoginStatus.setTextColor(getColor(R.color.color_success))
            binding.btnLogin.text = getString(R.string.btn_relogin)
        } else {
            binding.tvLoginStatus.text = getString(R.string.status_not_logged_in)
            binding.tvLoginStatus.setTextColor(getColor(R.color.color_danger))
            binding.btnLogin.text = getString(R.string.btn_login)
        }
    }

    private fun loadCourses() {
        lifecycleScope.launch {
            appendLog("❤ 正在拉取学期课程列表喵...")
            try {
                val cookie = tokenManager.cookie
                val sem = client.getSemesterInfo(cookie)
                tokenManager.semesterId = sem.semesterId
                tokenManager.academicYearId = sem.academicYearId

                val courses = client.getCourses(cookie, sem.semesterId, sem.academicYearId)
                courseList.clear()
                courseList.addAll(courses)

                if (courses.isEmpty()) {
                    appendLog("⚠️ 课程列表为空，可能需要重新登录以刷新 Cookie 喵。")
                    Toast.makeText(this@MainActivity, "未获取到课程喵", Toast.LENGTH_SHORT).show()
                    return@launch
                }

                val titles = courses.map { it.title }
                val adapter = ArrayAdapter(this@MainActivity, R.layout.item_spinner_course, titles)
                adapter.setDropDownViewResource(R.layout.item_spinner_course)
                binding.spinnerCourses.adapter = adapter

                appendLog("✅ 成功加载 ${courses.size} 门课程喵❤！")
                if (courses.isNotEmpty()) {
                    selectedCourse = courses[0]
                    binding.tvSelectedCourseInfo.text = "已选课程: ${selectedCourse?.title} (ID: ${selectedCourse?.id})"
                }
            } catch (e: Exception) {
                appendLog("❌ 加载课程失败: ${e.message}")
            }
        }
    }

    private fun checkRollcall() {
        val course = selectedCourse
        if (course == null) {
            Toast.makeText(this, "请先选择一门课程喵！", Toast.LENGTH_SHORT).show()
            return
        }

        lifecycleScope.launch {
            appendLog("----------------------------------------")
            appendLog("🔍 正在探测课程【${course.title}】的最新签到喵...")
            try {
                val cookie = tokenManager.cookie
                val studentId = tokenManager.studentId
                val rc = client.getLatestRollcall(cookie, course.id, studentId)

                if (rc == null || rc.effectiveId == 0L) {
                    appendLog("⚠️ 这门课目前没有任何签到记录喵~")
                    binding.tvRollcallTime.text = "最新签到：暂无数据"
                    binding.tvRollcallCode.text = "签到码：无记录"
                    binding.tvRollcallStatus.text = "状态：无签到"
                    currentRollcall = null
                    currentNumberCode = null
                    return@launch
                }

                currentRollcall = rc
                val rid = rc.effectiveId
                appendLog("🎯 找到最新签到记录 (ID: $rid, 时间: ${rc.timeString})")

                val detail = client.getNumberCode(cookie, rid)
                currentNumberCode = detail.numberCode

                binding.tvRollcallTime.text = "签到时间: ${rc.timeString} (ID: $rid)"

                if (!detail.numberCode.isNullOrBlank()) {
                    binding.tvRollcallCode.text = "签到码：【 ${detail.numberCode} 】"
                    appendLog("🎉 成功提取数字签到码：【 ${detail.numberCode} 】")
                } else {
                    binding.tvRollcallCode.text = "签到码：无数字码 (可能为雷达/GPS)"
                    appendLog("ℹ️ 未提取到数字签到码，可能是雷达或定位签到喵！")
                }

                val isRadarActive = client.findActiveRadar(cookie, rid)
                val statusText = when {
                    detail.status == "finished" -> "已结束"
                    detail.status == "active" -> "进行中 (活跃)"
                    isRadarActive -> "雷达签到正在进行中！"
                    else -> detail.status ?: "未知"
                }

                binding.tvRollcallStatus.text = "状态: $statusText"
                appendLog("📋 状态检测完成: $statusText")
            } catch (e: Exception) {
                appendLog("❌ 探测签到异常: ${e.message}")
            }
        }
    }

    private fun executeNumberSign() {
        val rc = currentRollcall
        val code = currentNumberCode

        if (rc == null || rc.effectiveId == 0L) {
            Toast.makeText(this, "请先点击【探测签到】喵！", Toast.LENGTH_SHORT).show()
            return
        }

        if (code.isNullOrBlank()) {
            Toast.makeText(this, "没有可提交的数字签到码喵！", Toast.LENGTH_SHORT).show()
            return
        }

        lifecycleScope.launch {
            appendLog("🐾 正在向 Tronclass 提交数字签到码: $code ...")
            try {
                val (ok, body) = client.submitNumberCode(tokenManager.cookie, rc.effectiveId, code)
                if (ok) {
                    appendLog("✅ 数字签到提交成功喵❤！签到码：$code")
                    Toast.makeText(this@MainActivity, "签到成功喵❤", Toast.LENGTH_LONG).show()
                } else {
                    appendLog("❌ 数字签到提交失败：$body")
                    Toast.makeText(this@MainActivity, "提交失败，请看日志", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                appendLog("❌ 提交异常: ${e.message}")
            }
        }
    }

    private fun executeRadarSign() {
        val rc = currentRollcall
        if (rc == null || rc.effectiveId == 0L) {
            Toast.makeText(this, "请先点击【探测签到】获取签到ID喵！", Toast.LENGTH_SHORT).show()
            return
        }

        lifecycleScope.launch {
            appendLog("========================================")
            appendLog("🛰 启动 zako 雷达引擎，四校区探针准备就绪...")
            try {
                val result = radarEngine.executeRadarSign(tokenManager.cookie, rc.effectiveId) { logMsg ->
                    lifecycleScope.launch(Dispatchers.Main) {
                        appendLog(logMsg)
                    }
                }

                if (result.success) {
                    appendLog("🎉🎉 雷达签到成功完成喵❤❤❤！校区：${result.campus}")
                    Toast.makeText(this@MainActivity, "雷达签到成功喵！", Toast.LENGTH_LONG).show()
                } else {
                    appendLog("❌ 雷达签到未完成: ${result.message}")
                    Toast.makeText(this@MainActivity, "雷达签到失败: ${result.message}", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                appendLog("❌ 雷达引擎运行异常: ${e.message}")
            }
        }
    }

    private fun appendLog(msg: String) {
        val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        val time = timeFormat.format(Date())
        val formatted = "[$time] $msg\n"
        binding.tvLogs.append(formatted)

        binding.scrollLogs.post {
            binding.scrollLogs.fullScroll(View.FOCUS_DOWN)
        }
    }
}
