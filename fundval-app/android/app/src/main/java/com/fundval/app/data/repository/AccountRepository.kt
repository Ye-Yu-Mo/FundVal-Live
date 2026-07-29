package com.fundval.app.data.repository

import com.fundval.app.data.api.AccountsApi
import com.fundval.app.data.api.dto.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AccountRepository @Inject constructor(
    private val api: AccountsApi
) {
    suspend fun list(): Result<List<AccountDto>> = runCatching { api.list() }
    suspend fun create(name: String, parentId: String? = null): Result<AccountDto> =
        runCatching { api.create(CreateAccountRequest(name, parentId)) }
    suspend fun update(id: String, name: String? = null, isDefault: Boolean? = null): Result<AccountDto> =
        runCatching { api.update(id, UpdateAccountRequest(name, isDefault)) }
    suspend fun delete(id: String): Result<Unit> = runCatching { api.delete(id) }
    suspend fun deleteInfo(id: String): Result<DeleteInfoResponse> = runCatching { api.deleteInfo(id) }
    suspend fun getPositions(id: String): Result<List<PositionDto>> = runCatching { api.positions(id) }
}
