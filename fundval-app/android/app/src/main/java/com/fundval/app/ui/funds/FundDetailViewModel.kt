package com.fundval.app.ui.funds

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.api.dto.*
import com.fundval.app.data.repository.FundRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.DayOfWeek
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import javax.inject.Inject

data class FundDetailUiState(
    val fundCode: String = "",
    val fund: FundBrief? = null,
    val estimate: EstimateResponse? = null,
    val intraday: List<IntradaySnapshot> = emptyList(),
    val accuracy: Map<String, SourceAccuracy>? = null,
    val marketQuote: MarketQuoteResponse? = null,
    val holdings: List<HoldingRealtime> = emptyList(),
    val isLoading: Boolean = true,
    val error: String? = null
)

@HiltViewModel
class FundDetailViewModel @Inject constructor(
    private val fundRepository: FundRepository,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val fundCode: String = savedStateHandle.get<String>("fundCode") ?: ""

    private val _uiState = MutableStateFlow(FundDetailUiState(fundCode = fundCode))
    val uiState: StateFlow<FundDetailUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null

    init {
        loadAll()
        startPolling()
    }

    private fun loadAll() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }

            // Load basic info
            fundRepository.getFundDetail(fundCode)
                .onSuccess { result -> _uiState.update { it.copy(fund = result) } }

            // Load estimate
            fundRepository.getEstimate(fundCode)
                .onSuccess { result -> _uiState.update { it.copy(estimate = result) } }

            // Load intraday
            fundRepository.getIntraday(fundCode)
                .onSuccess { result ->
                    _uiState.update { it.copy(intraday = result.snapshots ?: emptyList()) }
                }

            // Load accuracy
            fundRepository.getAccuracy(fundCode)
                .onSuccess { result -> _uiState.update { it.copy(accuracy = result) } }

            // Load market quote
            fundRepository.getMarketQuote(fundCode)
                .onSuccess { result -> _uiState.update { it.copy(marketQuote = result) } }

            // Load holdings realtime
            fundRepository.getHoldingsRealtime(fundCode)
                .onSuccess { result ->
                    _uiState.update { it.copy(holdings = result.holdings ?: emptyList()) }
                }

            _uiState.update { it.copy(isLoading = false) }
        }
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                delay(30_000) // 30s
                if (isTradingHours()) {
                    fundRepository.getEstimate(fundCode)
                        .onSuccess { estimate ->
                            _uiState.update { it.copy(estimate = estimate) }
                        }
                }
            }
        }
    }

    private fun isTradingHours(): Boolean {
        val now = ZonedDateTime.now(ZoneId.of("Asia/Shanghai"))
        if (now.dayOfWeek == DayOfWeek.SATURDAY || now.dayOfWeek == DayOfWeek.SUNDAY) return false
        val time = now.toLocalTime()
        return !time.isBefore(LocalTime.of(9, 30)) && !time.isAfter(LocalTime.of(15, 0))
    }

    override fun onCleared() {
        super.onCleared()
        pollingJob?.cancel()
    }
}
