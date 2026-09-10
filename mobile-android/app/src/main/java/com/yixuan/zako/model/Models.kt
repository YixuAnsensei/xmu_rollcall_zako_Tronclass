package com.yixuan.zako.model

import com.google.gson.annotations.SerializedName

data class Course(
    val id: Long,
    val name: String?,
    @SerializedName("display_name") val displayName: String?
) {
    val title: String
        get() = displayName?.takeIf { it.isNotBlank() } ?: name ?: "未知课程"
}

data class SemesterInfo(
    val semesterId: String,
    val academicYearId: String
)

data class RollcallRecord(
    val id: Long?,
    @SerializedName("rollcall_id") val rollcallId: Long?,
    @SerializedName("rollcall_time") val rollcallTime: String?,
    @SerializedName("created_at") val createdAt: String?,
    val status: String?,
    @SerializedName("is_radar") val isRadar: Boolean? = false,
    val type: String? = null
) {
    val effectiveId: Long
        get() = rollcallId ?: id ?: 0L

    val timeString: String
        get() = rollcallTime ?: createdAt ?: "未知时间"
}

data class RollcallDetail(
    @SerializedName("number_code") val numberCode: String?,
    val status: String?,
    @SerializedName("end_time") val endTime: String?
)

data class Campus(
    val name: String,
    val lat: Double,
    val lng: Double
)

data class RadarResult(
    val success: Boolean,
    val campus: String?,
    val position: Pair<Double, Double>?,
    val message: String
)
