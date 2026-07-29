package com.fundval.app.ui.accounts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.api.dto.AccountDto
import com.fundval.app.data.api.dto.DeleteInfoResponse
import com.fundval.app.data.repository.AccountRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AccountUiState(
    val accounts: List<AccountDto> = emptyList(),
    val expandedParents: Set<String> = emptySet(),
    val isLoading: Boolean = true,
    val error: String? = null,
    val showCreateDialog: Boolean = false,
    val showDeleteInfo: DeleteInfoResponse? = null,
    val deleteTargetId: String? = null
)

@HiltViewModel
class AccountViewModel @Inject constructor(
    private val accountRepository: AccountRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AccountUiState())
    val uiState: StateFlow<AccountUiState> = _uiState.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            accountRepository.list()
                .onSuccess { accounts ->
                    _uiState.update { it.copy(accounts = accounts, isLoading = false) }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(error = e.message, isLoading = false) }
                }
        }
    }

    fun toggleExpand(accountId: String) {
        _uiState.update { state ->
            val expanded = state.expandedParents.toMutableSet()
            if (expanded.contains(accountId)) expanded.remove(accountId) else expanded.add(accountId)
            state.copy(expandedParents = expanded)
        }
    }

    fun showCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = true) }
    }

    fun hideCreateDialog() {
        _uiState.update { it.copy(showCreateDialog = false) }
    }

    fun createAccount(name: String, parentId: String?) {
        viewModelScope.launch {
            accountRepository.create(name, parentId)
                .onSuccess { load() }
            _uiState.update { it.copy(showCreateDialog = false) }
        }
    }

    fun requestDelete(accountId: String) {
        viewModelScope.launch {
            accountRepository.deleteInfo(accountId)
                .onSuccess { info ->
                    _uiState.update { it.copy(showDeleteInfo = info, deleteTargetId = accountId) }
                }
        }
    }

    fun confirmDelete() {
        val id = _uiState.value.deleteTargetId ?: return
        viewModelScope.launch {
            accountRepository.delete(id)
                .onSuccess { load() }
            _uiState.update { it.copy(showDeleteInfo = null, deleteTargetId = null) }
        }
    }

    fun cancelDelete() {
        _uiState.update { it.copy(showDeleteInfo = null, deleteTargetId = null) }
    }
}
