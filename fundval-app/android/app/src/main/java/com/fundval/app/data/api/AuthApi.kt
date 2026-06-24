package com.fundval.app.data.api

import com.fundval.app.data.api.dto.*
import retrofit2.http.*

interface AuthApi {

    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @POST("auth/refresh")
    suspend fun refreshToken(@Body request: RefreshRequest): RefreshResponse

    @GET("auth/me")
    suspend fun getCurrentUser(): UserInfo

    @PUT("auth/password")
    suspend fun changePassword(@Body request: ChangePasswordRequest): MessageResponse

    @POST("users/register/")
    suspend fun register(@Body request: RegisterRequest): RegisterResponse

    @GET("health/")
    suspend fun healthCheck(): HealthResponse
}
