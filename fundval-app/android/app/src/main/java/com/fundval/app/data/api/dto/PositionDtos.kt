package com.fundval.app.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class PositionDto(
    val id: String,
    val account: String,
    @SerialName("account_name") val accountName: String? = null,
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String? = null,
    @SerialName("fund_type") val fundType: String? = null,
    val fund: PositionFundDto? = null,
    @SerialName("holding_share") val holdingShare: String? = null,
    @SerialName("holding_cost") val holdingCost: String? = null,
    @SerialName("holding_nav") val holdingNav: String? = null,
    val pnl: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null
)

@Serializable
data class PositionFundDto(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String? = null,
    @SerialName("fund_type") val fundType: String? = null,
    @SerialName("latest_nav") val latestNav: String? = null,
    @SerialName("latest_nav_date") val latestNavDate: String? = null,
    @SerialName("estimate_nav") val estimateNav: String? = null,
    @SerialName("estimate_growth") val estimateGrowth: String? = null,
    @SerialName("estimate_time") val estimateTime: String? = null
)

@Serializable
data class PositionOperationDto(
    val id: String,
    val account: String,
    @SerialName("account_name") val accountName: String? = null,
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String? = null,
    @SerialName("operation_type") val operationType: String, // BUY or SELL
    @SerialName("operation_date") val operationDate: String,
    @SerialName("before_15") val before15: Boolean = true,
    val amount: String,
    val share: String,
    val nav: String,
    @SerialName("created_at") val createdAt: String? = null
)

@Serializable
data class CreateOperationRequest(
    val account: String,
    @SerialName("fund_code") val fundCode: String,
    @SerialName("operation_type") val operationType: String,
    @SerialName("operation_date") val operationDate: String,
    @SerialName("before_15") val before15: Boolean = true,
    val amount: String,
    val share: String,
    val nav: String
)

@Serializable
data class QueryNavRequest(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("operation_date") val operationDate: String,
    @SerialName("before_15") val before15: Boolean = true
)

@Serializable
data class QueryNavResponse(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String? = null,
    val nav: String? = null,
    @SerialName("nav_date") val navDate: String? = null,
    val source: String? = null
)

@Serializable
data class BatchDeleteRequest(
    @SerialName("operation_ids") val operationIds: List<String>
)

@Serializable
data class BatchDeleteResponse(
    @SerialName("deleted_count") val deletedCount: Int,
    val message: String? = null
)

@Serializable
data class PositionHistoryItem(
    val date: String,
    val value: Double,
    val cost: Double
)

@Serializable
data class UserSummaryDto(
    @SerialName("account_count") val accountCount: Int,
    @SerialName("position_count") val positionCount: Int,
    @SerialName("total_cost") val totalCost: String? = null,
    @SerialName("total_value") val totalValue: String? = null,
    @SerialName("total_pnl") val totalPnl: String? = null
)
