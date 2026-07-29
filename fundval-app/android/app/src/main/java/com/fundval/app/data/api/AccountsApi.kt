package com.fundval.app.data.api

import com.fundval.app.data.api.dto.*
import retrofit2.http.*

interface AccountsApi {

    @GET("accounts/")
    suspend fun list(): List<AccountDto>

    @POST("accounts/")
    suspend fun create(@Body request: CreateAccountRequest): AccountDto

    @GET("accounts/{id}/")
    suspend fun detail(@Path("id") id: String): AccountDto

    @PUT("accounts/{id}/")
    suspend fun update(@Path("id") id: String, @Body request: UpdateAccountRequest): AccountDto

    @DELETE("accounts/{id}/")
    suspend fun delete(@Path("id") id: String)

    @GET("accounts/{id}/delete_info/")
    suspend fun deleteInfo(@Path("id") id: String): DeleteInfoResponse

    @GET("accounts/{id}/positions/")
    suspend fun positions(@Path("id") id: String): List<PositionDto>
}
