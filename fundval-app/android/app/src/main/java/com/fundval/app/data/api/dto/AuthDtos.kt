package com.fundval.app.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginRequest(
    val username: String,
    val password: String
)

@Serializable
data class LoginResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    val user: UserBrief
)

@Serializable
data class RefreshRequest(
    @SerialName("refresh_token") val refreshToken: String
)

@Serializable
data class RefreshResponse(
    @SerialName("access_token") val accessToken: String
)

@Serializable
data class UserBrief(
    val id: String,
    val username: String,
    val role: String? = null
)

@Serializable
data class UserInfo(
    val id: String,
    val username: String,
    val email: String? = null,
    val role: String? = null,
    @SerialName("created_at") val createdAt: String? = null
)

@Serializable
data class RegisterRequest(
    val username: String,
    val password: String,
    @SerialName("password_confirm") val passwordConfirm: String
)

@Serializable
data class RegisterResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    val user: UserBrief
)

@Serializable
data class ChangePasswordRequest(
    @SerialName("old_password") val oldPassword: String,
    @SerialName("new_password") val newPassword: String
)

@Serializable
data class MessageResponse(
    val message: String
)

@Serializable
data class HealthResponse(
    val status: String,
    val database: String,
    @SerialName("system_initialized") val systemInitialized: Boolean
)

@Serializable
data class ErrorResponse(
    val error: String? = null,
    val detail: String? = null
)
