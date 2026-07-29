package com.fundval.app.data.api

import com.fundval.app.data.api.dto.*
import retrofit2.http.*

interface PositionsApi {

    @GET("positions/")
    suspend fun list(
        @Query("account_id") accountId: String? = null,
        @Query("fund_code") fundCode: String? = null
    ): List<PositionDto>

    @GET("positions/{id}/")
    suspend fun detail(@Path("id") id: String): PositionDto

    @POST("positions/operations/")
    suspend fun createOperation(@Body request: CreateOperationRequest): PositionOperationDto

    @GET("positions/operations/")
    suspend fun listOperations(
        @Query("account") account: String? = null,
        @Query("fund_code") fundCode: String? = null
    ): List<PositionOperationDto>

    @DELETE("positions/operations/{id}/")
    suspend fun deleteOperation(@Path("id") id: String)

    @POST("positions/operations/batch_delete/")
    suspend fun batchDelete(@Body request: BatchDeleteRequest): BatchDeleteResponse

    @DELETE("positions/{id}/clear/")
    suspend fun clearPosition(@Path("id") id: String)

    @POST("funds/query_nav/")
    suspend fun queryNav(@Body request: QueryNavRequest): QueryNavResponse

    @GET("positions/history/")
    suspend fun history(
        @Query("account_id") accountId: String,
        @Query("days") days: Int = 30
    ): List<PositionHistoryItem>

    @GET("users/me/summary/")
    suspend fun userSummary(): UserSummaryDto
}
