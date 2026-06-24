package com.fundval.app.ui.funds

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.api.dto.FundBrief
import com.fundval.app.data.repository.FundRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class FundListUiState(
    val funds: List<FundBrief> = emptyList(),
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val hasMore: Boolean = true,
    val error: String? = null,
    val searchQuery: String = "",
    val fundType: String? = null,
    val currentPage: Int = 1
)

@HiltViewModel
class FundListViewModel @Inject constructor(
    private val fundRepository: FundRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(FundListUiState())
    val uiState: StateFlow<FundListUiState> = _uiState.asStateFlow()

    private var searchJob: Job? = null

    fun onSearchQueryChange(query: String) {
        _uiState.update { it.copy(searchQuery = query) }
        // Debounce 300ms
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(300)
            refresh()
        }
    }

    fun onFundTypeChange(type: String?) {
        _uiState.update { it.copy(fundType = type) }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.update { it.copy(isRefreshing = true, error = null, currentPage = 1) }
            fundRepository.searchFunds(
                query = _uiState.value.searchQuery.ifBlank { null },
                fundType = _uiState.value.fundType,
                page = 1
            ).onSuccess { result ->
                _uiState.update {
                    it.copy(
                        funds = result.results,
                        isRefreshing = false,
                        isLoading = false,
                        hasMore = result.results.size >= 20,
                        currentPage = 1
                    )
                }
            }.onFailure { e ->
                _uiState.update {
                    it.copy(isRefreshing = false, isLoading = false, error = e.message)
                }
            }
        }
    }

    fun loadMore() {
        val state = _uiState.value
        if (state.isLoading || !state.hasMore) return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            val nextPage = state.currentPage + 1
            fundRepository.searchFunds(
                query = state.searchQuery.ifBlank { null },
                fundType = state.fundType,
                page = nextPage
            ).onSuccess { result ->
                _uiState.update {
                    it.copy(
                        funds = it.funds + result.results,
                        isLoading = false,
                        hasMore = result.results.size >= 20,
                        currentPage = nextPage
                    )
                }
            }.onFailure { e ->
                _uiState.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    init {
        refresh()
    }
}
