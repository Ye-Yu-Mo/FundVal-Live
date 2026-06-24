package com.fundval.app.ui.funds

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.api.dto.CompareFund
import com.fundval.app.data.repository.FundRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CompareUiState(
    val selectedCodes: List<String> = emptyList(),
    val funds: List<CompareFund> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class CompareViewModel @Inject constructor(
    private val fundRepository: FundRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(CompareUiState())
    val uiState: StateFlow<CompareUiState> = _uiState.asStateFlow()

    val selectedCodes: List<String> get() = _uiState.value.selectedCodes

    fun addFund(code: String) {
        val codes = _uiState.value.selectedCodes.toMutableList()
        if (codes.size >= 5) return
        if (codes.contains(code)) return
        codes.add(code)
        _uiState.update { it.copy(selectedCodes = codes) }
        if (codes.size >= 2) compare()
    }

    fun removeFund(code: String) {
        val codes = _uiState.value.selectedCodes.toMutableList()
        codes.remove(code)
        _uiState.update { it.copy(selectedCodes = codes) }
        if (codes.size >= 2) compare() else _uiState.update { it.copy(funds = emptyList()) }
    }

    fun compare() {
        val codes = _uiState.value.selectedCodes
        if (codes.size < 2) return

        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            fundRepository.compareFunds(codes)
                .onSuccess { result ->
                    _uiState.update {
                        it.copy(funds = result.funds ?: emptyList(), isLoading = false)
                    }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoading = false, error = e.message) }
                }
        }
    }
}
