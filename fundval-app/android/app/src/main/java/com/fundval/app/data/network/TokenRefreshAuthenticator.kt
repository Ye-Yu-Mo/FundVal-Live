package com.fundval.app.data.network

import com.fundval.app.data.local.TokenManager
import com.fundval.app.data.api.AuthApi
import com.fundval.app.data.api.dto.RefreshRequest
import com.fundval.app.data.api.dto.RefreshResponse
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

class TokenRefreshAuthenticator(
    private val tokenManager: TokenManager,
    private val authApi: AuthApi
) : Authenticator {

    private val mutex = Mutex()

    override fun authenticate(route: Route?, response: Response): Request? {
        // Only retry once — if the refreshed token also gets 401, give up
        if (response.request.header("Authorization")?.startsWith("Bearer ") == true) {
            val currentToken = response.request.header("Authorization")!!.removePrefix("Bearer ")
            return runBlocking {
                val storedToken = tokenManager.accessToken.first()
                // If the token in the failed request is different from stored,
                // someone else already refreshed. Retry with stored token.
                if (currentToken != storedToken && storedToken != null) {
                    response.request.newBuilder()
                        .header("Authorization", "Bearer $storedToken")
                        .build()
                } else {
                    // Try to refresh
                    mutex.withLock {
                        val refreshed = tryRefresh()
                        if (refreshed != null) {
                            response.request.newBuilder()
                                .header("Authorization", "Bearer $refreshed")
                                .build()
                        } else {
                            null // Refresh failed, let the call fail with 401
                        }
                    }
                }
            }
        }
        return null
    }

    private suspend fun tryRefresh(): String? {
        return try {
            val refreshToken = tokenManager.refreshToken.first() ?: return null
            val result: RefreshResponse = authApi.refreshToken(RefreshRequest(refreshToken))
            tokenManager.saveTokens(result.accessToken, refreshToken)
            result.accessToken
        } catch (e: Exception) {
            null
        }
    }
}
