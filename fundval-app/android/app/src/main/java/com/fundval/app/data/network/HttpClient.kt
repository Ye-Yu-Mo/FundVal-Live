package com.fundval.app.data.network

import com.fundval.app.data.local.TokenManager
import com.fundval.app.data.api.AuthApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import java.util.concurrent.TimeUnit

object HttpClient {

    private const val DEFAULT_BASE_URL = "http://185.239.224.208:21345/api/"

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    /**
     * Raw client WITHOUT auth interceptor or authenticator.
     * Used exclusively by TokenRefreshAuthenticator to avoid circular dependency.
     */
    fun createRawClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    /**
     * Raw Retrofit without auth. Only for token refresh calls.
     */
    fun createRawRetrofit(baseUrl: String = DEFAULT_BASE_URL): Retrofit {
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(createRawClient())
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    /**
     * Main authenticated Retrofit.
     * Uses rawAuthApi for token refresh in the authenticator (breaking the cycle).
     */
    fun createRetrofit(
        baseUrl: String = DEFAULT_BASE_URL,
        tokenManager: TokenManager,
        rawAuthApi: AuthApi
    ): Retrofit {
        val authInterceptor = Interceptor { chain ->
            val token = runBlocking { tokenManager.accessToken.first() }
            val request = if (token != null) {
                chain.request().newBuilder()
                    .header("Authorization", "Bearer $token")
                    .build()
            } else {
                chain.request()
            }
            chain.proceed(request)
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(loggingInterceptor)
            .authenticator(TokenRefreshAuthenticator(tokenManager, rawAuthApi))
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }
}
