package com.fundval.app.data.repository

import com.fundval.app.data.api.FundsApi
import com.fundval.app.data.api.dto.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FundRepository @Inject constructor(
    private val api: FundsApi
) {

    suspend fun searchFunds(
        query: String? = null,
        fundType: String? = null,
        page: Int = 1
    ): Result<FundListResponse> = runCatching {
        api.list(search = query, fundType = fundType, page = page)
    }

    suspend fun getFundDetail(code: String): Result<FundBrief> = runCatching {
        api.detail(code)
    }

    suspend fun getEstimate(code: String, source: String = "eastmoney"): Result<EstimateResponse> =
        runCatching { api.estimate(code, source) }

    suspend fun batchEstimate(codes: List<String>, source: String = "eastmoney"): Result<Map<String, EstimateResponse>> =
        runCatching { api.batchEstimate(BatchEstimateRequest(codes, source)) }

    suspend fun getIntraday(code: String, source: String = "eastmoney"): Result<IntradayResponse> =
        runCatching { api.estimateIntraday(code, source) }

    suspend fun getAccuracy(code: String, days: Int = 100): Result<Map<String, SourceAccuracy>> =
        runCatching { api.accuracy(code, days) }

    suspend fun getMarketQuote(code: String): Result<MarketQuoteResponse> =
        runCatching { api.marketQuote(code) }

    suspend fun getIndexHoldings(code: String): Result<IndexHoldingResponse> =
        runCatching { api.indexHoldings(code) }

    suspend fun getHoldingsRealtime(code: String): Result<HoldingRealtimeResponse> =
        runCatching { api.holdingsRealtime(code) }

    suspend fun getFundDetailData(code: String): Result<FundDetailResponse> =
        runCatching { api.fundDetail(code) }

    suspend fun getMarketIndices(): Result<MarketIndicesResponse> =
        runCatching { api.marketIndices() }

    suspend fun getRankings(
        type: String = "gain",
        category: String? = null,
        page: Int = 1
    ): Result<RankingsResponse> = runCatching { api.rankings(type, category, page) }

    suspend fun compareFunds(codes: List<String>): Result<CompareResponse> =
        runCatching { api.compare(codes.joinToString(",")) }
}
