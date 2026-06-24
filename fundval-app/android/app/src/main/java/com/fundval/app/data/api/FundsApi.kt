package com.fundval.app.data.api

import com.fundval.app.data.api.dto.*
import retrofit2.http.*

interface FundsApi {

    @GET("funds/")
    suspend fun list(
        @Query("search") search: String? = null,
        @Query("fund_type") fundType: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): FundListResponse

    @GET("funds/{code}/")
    suspend fun detail(@Path("code") code: String): FundBrief

    @GET("funds/{code}/estimate/")
    suspend fun estimate(
        @Path("code") code: String,
        @Query("source") source: String = "eastmoney"
    ): EstimateResponse

    @POST("funds/batch_estimate/")
    suspend fun batchEstimate(@Body request: BatchEstimateRequest): Map<String, EstimateResponse>

    @GET("funds/{code}/estimate-intraday/")
    suspend fun estimateIntraday(
        @Path("code") code: String,
        @Query("source") source: String = "eastmoney"
    ): IntradayResponse

    @GET("funds/{code}/accuracy/")
    suspend fun accuracy(
        @Path("code") code: String,
        @Query("days") days: Int = 100
    ): Map<String, SourceAccuracy>

    @GET("funds/{code}/market_quote/")
    suspend fun marketQuote(@Path("code") code: String): MarketQuoteResponse

    @GET("funds/{code}/index_holdings/")
    suspend fun indexHoldings(
        @Path("code") code: String,
        @Query("source") source: String = "eastmoney"
    ): IndexHoldingResponse

    @GET("funds/{code}/holdings-realtime/")
    suspend fun holdingsRealtime(@Path("code") code: String): HoldingRealtimeResponse

    @GET("funds/{code}/fund_detail/")
    suspend fun fundDetail(
        @Path("code") code: String,
        @Query("source") source: String = "danjuan"
    ): FundDetailResponse

    @GET("funds/market-indices/")
    suspend fun marketIndices(): MarketIndicesResponse

    @GET("funds/rankings/")
    suspend fun rankings(
        @Query("type") type: String = "gain",
        @Query("category") category: String? = null,
        @Query("page") page: Int = 1
    ): RankingsResponse

    @GET("funds/compare/")
    suspend fun compare(@Query("codes") codes: String): CompareResponse
}
