package com.yixuan.zako.engine

import com.yixuan.zako.model.Campus
import com.yixuan.zako.model.RadarResult
import com.yixuan.zako.network.TronclassClient
import java.util.UUID
import kotlin.math.*

class RadarEngine(private val client: TronclassClient) {

    private val earthRadius = 6371000.0

    private val campuses = listOf(
        Campus("翔安校区", 24.6060, 118.3100),
        Campus("思明校区", 24.4383, 118.0932),
        Campus("马来西亚校区", 2.8327, 101.7028),
        Campus("漳州校区", 24.3400, 117.9300)
    )

    private fun latlonToXy(lat: Double, lng: Double, lat0: Double, lng0: Double): Pair<Double, Double> {
        val x = Math.toRadians(lng - lng0) * earthRadius * cos(Math.toRadians(lat0))
        val y = Math.toRadians(lat - lat0) * earthRadius
        return Pair(x, y)
    }

    private fun xyToLatlon(x: Double, y: Double, lat0: Double, lng0: Double): Pair<Double, Double> {
        val lat = lat0 + Math.toDegrees(y / earthRadius)
        val lng = lng0 + Math.toDegrees(x / (earthRadius * cos(Math.toRadians(lat0))))
        return Pair(lat, lng)
    }

    private fun circleIntersections(
        x1: Double, y1: Double, d1: Double,
        x2: Double, y2: Double, d2: Double
    ): List<Pair<Double, Double>>? {
        val dist = hypot(x2 - x1, y2 - y1)
        if (dist == 0.0) return null

        if (dist > d1 + d2) {
            if (dist - (d1 + d2) <= 50.0) {
                val r = d1 / (d1 + d2)
                val p = Pair(x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)
                return listOf(p, p)
            }
            return null
        }

        if (dist < abs(d1 - d2)) {
            if (abs(d1 - d2) - dist <= 50.0) {
                val p = if (d1 > d2) {
                    val r = d1 / dist
                    Pair(x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)
                } else {
                    val r = d2 / dist
                    Pair(x2 + (x1 - x2) * r, y2 + (y1 - y2) * r)
                }
                return listOf(p, p)
            }
            return null
        }

        val along = (d1 * d1 - d2 * d2 + dist * dist) / (2.0 * dist)
        var hSq = d1 * d1 - along * along
        if (hSq < 0.0) hSq = 0.0
        val height = sqrt(hSq)

        val mx = x1 + along * (x2 - x1) / dist
        val my = y1 + along * (y2 - y1) / dist
        val ox = -(y2 - y1) * height / dist
        val oy = (x2 - x1) * height / dist

        return listOf(
            Pair(mx + ox, my + oy),
            Pair(mx - ox, my - oy)
        )
    }

    private fun solveTwoPoints(
        lat1: Double, lng1: Double,
        lat2: Double, lng2: Double,
        d1: Double, d2: Double
    ): List<Pair<Double, Double>>? {
        val lat0 = (lat1 + lat2) / 2.0
        val lng0 = (lng1 + lng2) / 2.0
        val (x1, y1) = latlonToXy(lat1, lng1, lat0, lng0)
        val (x2, y2) = latlonToXy(lat2, lng2, lat0, lng0)

        val sols = circleIntersections(x1, y1, d1, x2, y2, d2) ?: return null
        return sols.map { xyToLatlon(it.first, it.second, lat0, lng0) }
    }

    suspend fun executeRadarSign(
        cookie: String,
        rollcallId: Long,
        log: (String) -> Unit
    ): RadarResult {
        log("🛰 开始雷达签到 rollcall_id=$rollcallId")
        val deviceId = UUID.randomUUID().toString()

        var bestCampus: Campus? = null
        var minDistance: Double? = null

        for (c in campuses) {
            val (status, dist) = client.radarPut(cookie, rollcallId, c.lat, c.lng, deviceId)
            if (status == 200) {
                log("🎯 校区探针直接命中：${c.name}")
                return RadarResult(true, c.name, Pair(c.lat, c.lng), "校区中心直接命中")
            }
            log("📡 ${c.name} 探针 distance=${dist ?: "无数据"}")
            if (dist != null && (minDistance == null || dist < minDistance)) {
                minDistance = dist
                bestCampus = c
            }
        }

        if (bestCampus == null) {
            log("❌ 四校区探针均未回传有效距离，雷达签到失败")
            return RadarResult(false, null, null, "四校区探针均未回传距离")
        }

        log("📍 锁定最近校区：${bestCampus.name}")
        val lat0 = bestCampus.lat
        val lng0 = bestCampus.lng
        val dlat = 0.004
        val dlng = 0.004

        val (s1, d1) = client.radarPut(cookie, rollcallId, lat0 + dlat, lng0, deviceId)
        if (s1 == 200) {
            log("🎯 偏移探针1直接命中！")
            return RadarResult(true, bestCampus.name, Pair(lat0 + dlat, lng0), "偏移探针1直接命中")
        }

        val (s2, d2) = client.radarPut(cookie, rollcallId, lat0, lng0 + dlng, deviceId)
        if (s2 == 200) {
            log("🎯 偏移探针2直接命中！")
            return RadarResult(true, bestCampus.name, Pair(lat0, lng0 + dlng), "偏移探针2直接命中")
        }

        if (d1 == null || d2 == null) {
            log("⚠️ 偏移探针未回传有效距离，无法执行三边解算")
            return RadarResult(false, bestCampus.name, null, "偏移探针未回传距离")
        }

        val solutions = solveTwoPoints(lat0 + dlat, lng0, lat0, lng0 + dlng, d1, d2)
        if (solutions.isNullOrEmpty()) {
            log("⚠️ 几何解算失败：两圆无交点")
            return RadarResult(false, bestCampus.name, null, "几何两圆无交点")
        }

        for (candidate in solutions) {
            log(String.format("🧮 探测候选教师坐标 (%.6f, %.6f)", candidate.first, candidate.second))
            val (sCandidate, _) = client.radarPut(cookie, rollcallId, candidate.first, candidate.second, deviceId)
            if (sCandidate == 200) {
                log("✅ 雷达签到成功！已精准定位教师位置喵❤")
                return RadarResult(true, bestCampus.name, candidate, "雷达三角定位解算命中")
            }
        }

        log("❌ 候选坐标均未命中签到范围")
        return RadarResult(false, bestCampus.name, null, "候选坐标未命中")
    }
}
