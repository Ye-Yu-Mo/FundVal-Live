package com.fundval.app.di

import android.content.Context
import com.fundval.app.data.api.AuthApi
import com.fundval.app.data.api.FundsApi
import com.fundval.app.data.local.TokenManager
import com.fundval.app.data.network.HttpClient
import com.fundval.app.data.repository.FundRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import retrofit2.Retrofit
import javax.inject.Named
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideTokenManager(@ApplicationContext context: Context): TokenManager {
        return TokenManager(context)
    }

    /**
     * Raw AuthApi WITHOUT auth interceptor — only for token refresh calls.
     * This breaks the circular dependency: Retrofit → AuthApi → Authenticator → AuthApi → Retrofit.
     */
    @Provides
    @Singleton
    @Named("raw")
    fun provideRawAuthApi(): AuthApi {
        val rawRetrofit = HttpClient.createRawRetrofit()
        return rawRetrofit.create(AuthApi::class.java)
    }

    /**
     * Main authenticated Retrofit. Uses raw AuthApi for the token refresh authenticator.
     */
    @Provides
    @Singleton
    fun provideRetrofit(
        tokenManager: TokenManager,
        @Named("raw") rawAuthApi: AuthApi
    ): Retrofit {
        return HttpClient.createRetrofit(
            tokenManager = tokenManager,
            rawAuthApi = rawAuthApi
        )
    }

    /**
     * Main authenticated AuthApi. Goes through the auth interceptor + authenticator.
     */
    @Provides
    @Singleton
    fun provideAuthApi(retrofit: Retrofit): AuthApi {
        return retrofit.create(AuthApi::class.java)
    }

    @Provides
    @Singleton
    fun provideFundsApi(retrofit: Retrofit): FundsApi {
        return retrofit.create(FundsApi::class.java)
    }

    @Provides
    @Singleton
    fun provideFundRepository(api: FundsApi): FundRepository {
        return FundRepository(api)
    }
}
