package com.fundval.app.data.repository

import com.fundval.app.data.api.PositionsApi
import com.fundval.app.data.api.dto.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PositionRepository @Inject constructor(
    private val api: PositionsApi
) {
    suspend fun listPositions(accountId: String? = null): Result<List<PositionDto>> =
        runCatching { api.list(accountId = accountId) }

    suspend fun listOperations(account: String? = null, fundCode: String? = null): Result<List<PositionOperationDto>> =
        runCatching { api.listOperations(account = account, fundCode = fundCode) }

    suspend fun createOperation(request: CreateOperationRequest): Result<PositionOperationDto> =
        runCatching { api.createOperation(request) }

    suspend fun deleteOperation(id: String): Result<Unit> = runCatching { api.deleteOperation(id) }

    suspend fun batchDelete(ids: List<String>): Result<BatchDeleteResponse> =
        runCatching { api.batchDelete(BatchDeleteRequest(ids)) }

    suspend fun clearPosition(id: String): Result<Unit> = runCatching { api.clearPosition(id) }

    suspend fun queryNav(fundCode: String, date: String, before15: Boolean): Result<QueryNavResponse> =
        runCatching { api.queryNav(QueryNavRequest(fundCode, date, before15)) }

    suspend fun getHistory(accountId: String, days: Int = 30): Result<List<PositionHistoryItem>> =
        runCatching { api.history(accountId = accountId, days = days) }

    suspend fun getUserSummary(): Result<UserSummaryDto> = runCatching { api.userSummary() }
}
