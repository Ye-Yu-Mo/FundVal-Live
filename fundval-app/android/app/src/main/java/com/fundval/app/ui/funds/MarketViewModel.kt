package com.fundval.app.ui.funds

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.api.dto.MarketIndex
import com.fundval.app.data.api.dto.RankingItem
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

data class MarketUiState(
    val indices: List<MarketIndex> = emptyList(),
    val rankings: List<RankingItem> = emptyList(),
    val rankingType: String = "gain",
    val isLoading: Boolean = true,
    val error: String? = null
)

@HiltViewModel
class MarketViewModel @Inject constructor(
    private val fundRepository: FundRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(MarketUiState())
    val uiState: StateFlow<MarketUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null

    init {
        loadIndices()
        loadRankings()
        startPollingIndices()
    }

    fun setRankingType(type: String) {
        _uiState.update { it.copy(rankingType = type) }
        loadRankings()
    }

    private fun loadIndices() {
        viewModelScope.launch {
            fundRepository.getMarketIndices()
                .onSuccess { result ->
                    _uiState.update { it.copy(indices = result.indices ?: emptyList(), isLoading = false) }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message, isLoading = false) }
                }
        }
    }

    private fun loadRankings() {
        viewModelScope.launch {
            fundRepository.getRankings(type = _uiState.value.rankingType)
                .onSuccess { result ->
                    _uiState.update { it.copy(rankings = result.results) }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message) }
                }
        }
    }

    private fun startPollingIndices() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            while (isActive) {
                delay(10_000)
                if (isTradingHours()) {
                    fundRepository.getMarketIndices()
                        .onSuccess { result ->
                            _uiState.update { it.copy(indices = result.indices ?: emptyList()) }
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
