package com.fundval.app.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AccountDto(
    val id: String,
    val name: String,
    val parent: String? = null,
    @SerialName("is_default") val isDefault: Boolean = false,
    @SerialName("holding_cost") val holdingCost: String? = null,
    @SerialName("holding_value") val holdingValue: String? = null,
    val pnl: String? = null,
    @SerialName("pnl_rate") val pnlRate: String? = null,
    @SerialName("estimate_value") val estimateValue: String? = null,
    @SerialName("estimate_pnl") val estimatePnl: String? = null,
    @SerialName("estimate_pnl_rate") val estimatePnlRate: String? = null,
    @SerialName("today_pnl") val todayPnl: String? = null,
    @SerialName("today_pnl_rate") val todayPnlRate: String? = null,
    val children: List<AccountDto>? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null
)

@Serializable
data class CreateAccountRequest(
    val name: String,
    val parent: String? = null,
    @SerialName("is_default") val isDefault: Boolean = false
)

@Serializable
data class UpdateAccountRequest(
    val name: String? = null,
    @SerialName("is_default") val isDefault: Boolean? = null
)

@Serializable
data class DeleteInfoResponse(
    @SerialName("can_delete") val canDelete: Boolean,
    @SerialName("is_default") val isDefault: Boolean = false,
    val message: String? = null,
    @SerialName("children_count") val childrenCount: Int? = null,
    @SerialName("positions_count") val positionsCount: Int? = null,
    @SerialName("total_cost") val totalCost: String? = null
)
