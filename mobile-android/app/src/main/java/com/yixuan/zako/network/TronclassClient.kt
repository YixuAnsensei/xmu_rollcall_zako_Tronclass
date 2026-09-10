package com.yixuan.zako.network

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.yixuan.zako.model.Course
import com.yixuan.zako.model.RollcallDetail
import com.yixuan.zako.model.RollcallRecord
import com.yixuan.zako.model.SemesterInfo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.UUID
import java.util.concurrent.TimeUnit

class TronclassClient {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .followRedirects(true)
        .build()

    private val gson = Gson()
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()
    private val baseUrl = "https://lnt.xmu.edu.cn"

    private fun buildRequest(url: String, cookie: String): Request.Builder {
        return Request.Builder()
            .url(url)
            .header("cookie", cookie)
            .header("accept", "application/json, text/plain, */*")
            .header("accept-language", "zh-CN,zh;q=0.9")
            .header("user-agent", "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
    }

    suspend fun getSemesterInfo(cookie: String): SemesterInfo = withContext(Dispatchers.IO) {
        val request = buildRequest("$baseUrl/api/current-semester-info", cookie).get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val bodyStr = response.body?.string().orEmpty()
                    val obj = gson.fromJson(bodyStr, JsonObject::class.java)
                    val sId = obj.getAsJsonObject("semester")?.get("id")?.asString ?: "29"
                    val yId = obj.getAsJsonObject("academic_year")?.get("id")?.asString ?: "12"
                    SemesterInfo(sId, yId)
                } else {
                    SemesterInfo("29", "12")
                }
            }
        } catch (e: Exception) {
            SemesterInfo("29", "12")
        }
    }

    suspend fun getCourses(cookie: String, semesterId: String, academicYearId: String): List<Course> = withContext(Dispatchers.IO) {
        val payload = JsonObject().apply {
            val conditions = JsonObject().apply {
                val semArr = com.google.gson.JsonArray().apply { add(semesterId) }
                val yearArr = com.google.gson.JsonArray().apply { add(academicYearId) }
                add("semester_id", semArr)
                add("academic_year_id", yearArr)
                addProperty("keyword", "")
                addProperty("classify_type", "recently_started")
                addProperty("display_studio_list", false)
            }
            add("conditions", conditions)
            addProperty("fields", "id,name,display_name")
            addProperty("page", 1)
            addProperty("page_size", 50)
            addProperty("showScorePassedStatus", false)
        }

        val request = buildRequest("$baseUrl/api/my-courses", cookie)
            .header("content-type", "application/json")
            .header("referer", "$baseUrl/user/index")
            .post(payload.toString().toRequestBody(jsonMedia))
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return@withContext emptyList()
            val bodyStr = response.body?.string().orEmpty()
            val root = gson.fromJson(bodyStr, JsonObject::class.java)
            val arr = root.getAsJsonArray("courses") ?: root.getAsJsonArray("data") ?: return@withContext emptyList()

            val list = mutableListOf<Course>()
            val seen = mutableSetOf<Long>()
            for (elem in arr) {
                if (!elem.isJsonObject) continue
                val c = gson.fromJson(elem, Course::class.java)
                if (c != null && seen.add(c.id)) {
                    list.add(c)
                }
            }
            list
        }
    }

    suspend fun getLatestRollcall(cookie: String, courseId: Long, studentId: Long): RollcallRecord? = withContext(Dispatchers.IO) {
        val url = "$baseUrl/api/course/$courseId/student/$studentId/rollcalls?page=1&page_size=99"
        val request = buildRequest(url, cookie).get().build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return@withContext null
            val bodyStr = response.body?.string().orEmpty()
            val root = gson.fromJson(bodyStr, JsonObject::class.java)
            val arr = root.getAsJsonArray("rollcalls") ?: root.getAsJsonArray("data") ?: return@withContext null
            if (arr.size() == 0) return@withContext null
            val last = arr.get(arr.size() - 1)
            gson.fromJson(last, RollcallRecord::class.java)
        }
    }

    suspend fun getNumberCode(cookie: String, rollcallId: Long): RollcallDetail = withContext(Dispatchers.IO) {
        val url = "$baseUrl/api/rollcall/$rollcallId/student_rollcalls"
        val request = buildRequest(url, cookie).get().build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return@withContext RollcallDetail(null, null, null)
            val bodyStr = response.body?.string().orEmpty()
            val root = gson.fromJson(bodyStr, JsonObject::class.java)
            val code = root.get("number_code")?.takeIf { !it.isJsonNull }?.asString
                ?: root.getAsJsonObject("data")?.get("number_code")?.takeIf { !it.isJsonNull }?.asString
            val status = root.get("status")?.takeIf { !it.isJsonNull }?.asString
                ?: root.getAsJsonObject("data")?.get("status")?.takeIf { !it.isJsonNull }?.asString
            val endTime = root.get("end_time")?.takeIf { !it.isJsonNull }?.asString
                ?: root.getAsJsonObject("data")?.get("end_time")?.takeIf { !it.isJsonNull }?.asString
            RollcallDetail(code, status, endTime)
        }
    }

    suspend fun submitNumberCode(cookie: String, rollcallId: Long, numberCode: String): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        val url = "$baseUrl/api/rollcall/$rollcallId/answer_number_rollcall"
        val payload = JsonObject().apply {
            addProperty("deviceId", UUID.randomUUID().toString())
            addProperty("numberCode", numberCode)
        }
        val request = buildRequest(url, cookie)
            .put(payload.toString().toRequestBody(jsonMedia))
            .build()

        client.newCall(request).execute().use { response ->
            val ok = response.isSuccessful
            val body = response.body?.string().orEmpty()
            Pair(ok, body)
        }
    }

    suspend fun findActiveRadar(cookie: String, rollcallId: Long): Boolean = withContext(Dispatchers.IO) {
        val url = "$baseUrl/api/radar/rollcalls"
        val request = buildRequest(url, cookie).get().build()
        try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext false
                val body = response.body?.string().orEmpty()
                val root = gson.fromJson(body, JsonObject::class.java)
                val list = root.getAsJsonArray("rollcalls") ?: return@withContext false
                val target = rollcallId.toString()
                for (item in list) {
                    if (!item.isJsonObject) continue
                    val obj = item.asJsonObject
                    val rid = obj.get("rollcall_id")?.asString ?: obj.get("id")?.asString
                    if (rid == target) return@withContext true
                }
                false
            }
        } catch (e: Exception) {
            false
        }
    }

    suspend fun radarPut(cookie: String, rollcallId: Long, lat: Double, lng: Double, deviceId: String): Pair<Int, Double?> = withContext(Dispatchers.IO) {
        val url = "$baseUrl/api/rollcall/$rollcallId/answer"
        val payload = JsonObject().apply {
            addProperty("accuracy", 35)
            addProperty("altitude", 0)
            add("altitudeAccuracy", null)
            addProperty("deviceId", deviceId)
            add("heading", null)
            addProperty("latitude", lat)
            addProperty("longitude", lng)
            add("speed", null)
        }
        val request = buildRequest(url, cookie)
            .put(payload.toString().toRequestBody(jsonMedia))
            .build()

        try {
            client.newCall(request).execute().use { response ->
                val code = response.code
                val body = response.body?.string().orEmpty()
                var dist: Double? = null
                try {
                    val root = gson.fromJson(body, JsonObject::class.java)
                    for (k in listOf("distance", "dist", "distance_m", "distanceMeters")) {
                        if (root.has(k) && !root.get(k).isJsonNull) {
                            dist = root.get(k).asDouble
                            break
                        }
                    }
                } catch (e: Exception) {
                }
                Pair(code, dist)
            }
        } catch (e: Exception) {
            Pair(0, null)
        }
    }
}
