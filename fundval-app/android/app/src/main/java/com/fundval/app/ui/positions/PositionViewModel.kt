package com.fundval.app.ui.positions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.api.dto.CreateOperationRequest
import com.fundval.app.data.api.dto.PositionDto
import com.fundval.app.data.api.dto.PositionOperationDto
import com.fundval.app.data.repository.AccountRepository
import com.fundval.app.data.repository.PositionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PositionUiState(
    val positions: List<PositionDto> = emptyList(),
    val operations: List<PositionOperationDto> = emptyList(),
    val selectedAccountId: String? = null,
    val accountNames: List<Pair<String, String>> = emptyList(), // id -> name
    val isLoading: Boolean = true,
    val error: String? = null,
    val showCreateDialog: Boolean = false,
    val showOperations: Boolean = false
)

@HiltViewModel
class PositionViewModel @Inject constructor(
    private val positionRepository: PositionRepository,
    private val accountRepository: AccountRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(PositionUiState())
    val uiState: StateFlow<PositionUiState> = _uiState.asStateFlow()

    init { load() }

    private fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            // Load account list for dropdown
            accountRepository.list()
                .onSuccess { accounts ->
                    val names = mutableListOf<Pair<String, String>>()
                    accounts.forEach { parent ->
                        names.add(parent.id to parent.name)
                        parent.children?.forEach { child ->
                            names.add(child.id to child.name)
                        }
                    }
                    _uiState.update { it.copy(accountNames = names) }
                }
            loadPositions()
        }
    }

    fun selectAccount(accountId: String?) {
        _uiState.update { it.copy(selectedAccountId = accountId) }
        loadPositions()
    }

    private fun loadPositions() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            positionRepository.listPositions(accountId = _uiState.value.selectedAccountId)
                .onSuccess { positions ->
                    _uiState.update { it.copy(positions = positions, isLoading = false) }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message, isLoading = false) }
                }
        }
    }

    fun loadOperations() {
        viewModelScope.launch {
            _uiState.update { it.copy(showOperations = true) }
            positionRepository.listOperations(account = _uiState.value.selectedAccountId)
                .onSuccess { ops ->
                    _uiState.update { it.copy(operations = ops) }
                }
        }
    }

    fun hideOperations() {
        _uiState.update { it.copy(showOperations = false) }
    }

    fun showCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = true) }
    }

    fun hideCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = false) }
    }

    fun createOperation(request: CreateOperationRequest) {
        viewModelScope.launch {
            positionRepository.createOperation(request)
                .onSuccess {
                    _uiState.update { it.copy(showCreateDialog = false) }
                    loadPositions()
                }
        }
    }

    fun deleteOperation(id: String) {
        viewModelScope.launch {
            positionRepository.deleteOperation(id)
                .onSuccess { loadPositions() }
        }
    }
}
