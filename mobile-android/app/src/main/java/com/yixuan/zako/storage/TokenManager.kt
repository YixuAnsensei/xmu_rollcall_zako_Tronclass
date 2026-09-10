package com.yixuan.zako.storage

import android.content.Context
import android.content.SharedPreferences

class TokenManager(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("zako_rollcall_prefs", Context.MODE_PRIVATE)

    var cookie: String
        get() = prefs.getString("cookie", "") ?: ""
        set(value) = prefs.edit().putString("cookie", value).apply()

    var studentId: Long
        get() = prefs.getLong("student_id", 0L)
        set(value) = prefs.edit().putLong("student_id", value).apply()

    var semesterId: String
        get() = prefs.getString("semester_id", "29") ?: "29"
        set(value) = prefs.edit().putString("semester_id", value).apply()

    var academicYearId: String
        get() = prefs.getString("academic_year_id", "12") ?: "12"
        set(value) = prefs.edit().putString("academic_year_id", value).apply()

    val isLoggedIn: Boolean
        get() = cookie.isNotBlank() && studentId > 0L

    fun clear() {
        prefs.edit().clear().apply()
    }
}
