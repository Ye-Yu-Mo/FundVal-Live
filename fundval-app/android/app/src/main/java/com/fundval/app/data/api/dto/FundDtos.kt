package com.fundval.app.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ---- Fund List ----
@Serializable
data class FundBrief(
    val id: String,
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String,
    @SerialName("fund_type") val fundType: String? = null,
    @SerialName("latest_nav") val latestNav: String? = null,
    @SerialName("latest_nav_date") val latestNavDate: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null
)

@Serializable
data class FundListResponse(
    val count: Int,
    val results: List<FundBrief>
)

// ---- Estimate ----
@Serializable
data class EstimateResponse(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String? = null,
    @SerialName("estimate_nav") val estimateNav: String? = null,
    @SerialName("estimate_growth") val estimateGrowth: String? = null,
    @SerialName("estimate_time") val estimateTime: String? = null,
    @SerialName("latest_nav") val latestNav: String? = null,
    @SerialName("latest_nav_date") val latestNavDate: String? = null,
    @SerialName("from_cache") val fromCache: Boolean? = null,
    val error: String? = null
)

@Serializable
data class BatchEstimateRequest(
    @SerialName("fund_codes") val fundCodes: List<String>,
    val source: String = "eastmoney"
)

@Serializable
data class BatchEstimateResponse(
    @SerialName("fund_codes") val fundCodes: List<String>? = null
)

// ---- Intraday ----
@Serializable
data class IntradaySnapshot(
    val source: String? = null,
    val timestamp: String? = null,
    @SerialName("estimate_nav") val estimateNav: String? = null,
    @SerialName("estimate_growth") val estimateGrowth: String? = null
)

@Serializable
data class IntradayResponse(
    @SerialName("fund_code") val fundCode: String,
    val snapshots: List<IntradaySnapshot>? = null
)

// ---- Accuracy ----
@Serializable
data class AccuracyRecord(
    val date: String? = null,
    @SerialName("estimate_nav") val estimateNav: String? = null,
    @SerialName("actual_nav") val actualNav: String? = null,
    @SerialName("error_rate") val errorRate: String? = null
)

@Serializable
data class SourceAccuracy(
    val records: List<AccuracyRecord>? = null,
    @SerialName("avg_error_rate") val avgErrorRate: String? = null,
    @SerialName("record_count") val recordCount: Int? = null
)

// ---- Market Quote ----
@Serializable
data class MarketQuoteResponse(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("market_price") val marketPrice: String? = null,
    @SerialName("market_growth") val marketGrowth: String? = null,
    @SerialName("market_time") val marketTime: String? = null,
    val symbol: String? = null
)

// ---- Index Holdings ----
@Serializable
data class IndexHolding(
    @SerialName("stock_code") val stockCode: String,
    @SerialName("stock_name") val stockName: String,
    val weight: String? = null,
    val price: String? = null,
    @SerialName("change_percent") val changePercent: String? = null
)

@Serializable
data class IndexHoldingResponse(
    @SerialName("fund_code") val fundCode: String,
    val holdings: List<IndexHolding>? = null
)

// ---- Holdings Realtime ----
@Serializable
data class HoldingRealtime(
    @SerialName("stock_code") val stockCode: String,
    @SerialName("stock_name") val stockName: String,
    val weight: String? = null,
    val price: String? = null,
    @SerialName("change_percent") val changePercent: String? = null,
    val contribution: String? = null
)

@Serializable
data class HoldingRealtimeResponse(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("total_weight") val totalWeight: String? = null,
    val holdings: List<HoldingRealtime>? = null
)

// ---- Fund Detail (danjuan) ----
@Serializable
data class FundDetailData(
    @SerialName("fund_name") val fundName: String? = null,
    @SerialName("fund_type") val fundType: String? = null,
    @SerialName("risk_level") val riskLevel: String? = null,
    @SerialName("manager_name") val managerName: String? = null,
    @SerialName("company_name") val companyName: String? = null,
    @SerialName("latest_nav") val latestNav: String? = null,
    @SerialName("nav_date") val navDate: String? = null,
    @SerialName("period_returns") val periodReturns: Map<String, String?>? = null,
    @SerialName("peer_ranking") val peerRanking: Map<String, String?>? = null
)

@Serializable
data class FundDetailResponse(
    @SerialName("fund_code") val fundCode: String,
    val source: String? = null,
    val detail: FundDetailData? = null
)

// ---- Market Indices ----
@Serializable
data class MarketIndex(
    val code: String,
    val name: String,
    val price: String? = null,
    @SerialName("change_percent") val changePercent: String? = null
)

@Serializable
data class MarketIndicesResponse(
    val indices: List<MarketIndex>? = null
)

// ---- Rankings ----
@Serializable
data class RankingItem(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String? = null,
    @SerialName("fund_type") val fundType: String? = null,
    @SerialName("latest_nav") val latestNav: String? = null,
    @SerialName("estimate_growth") val estimateGrowth: String? = null,
    @SerialName("pos_count") val posCount: Int? = null,
    @SerialName("avg_error") val avgError: String? = null
)

@Serializable
data class RankingsResponse(
    val count: Int,
    val results: List<RankingItem>
)

// ---- Compare ----
@Serializable
data class CompareFund(
    @SerialName("fund_code") val fundCode: String,
    @SerialName("fund_name") val fundName: String? = null,
    @SerialName("fund_type") val fundType: String? = null,
    @SerialName("latest_nav") val latestNav: String? = null,
    val returns: Map<String, String?>? = null,
    val metrics: CompareMetrics? = null
)

@Serializable
data class CompareMetrics(
    @SerialName("max_drawdown") val maxDrawdown: String? = null,
    val volatility: String? = null,
    val sharpe: String? = null
)

@Serializable
data class CompareResponse(
    val funds: List<CompareFund>? = null
)
