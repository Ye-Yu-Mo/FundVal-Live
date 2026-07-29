package com.fundval.app.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.api.dto.UserInfo
import com.fundval.app.data.api.dto.UserSummaryDto
import com.fundval.app.data.repository.AuthRepository
import com.fundval.app.data.repository.PositionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ProfileUiState(
    val user: UserInfo? = null,
    val summary: UserSummaryDto? = null,
    val isLoading: Boolean = true,
    val showLogoutConfirm: Boolean = false
)

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val positionRepository: PositionRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ProfileUiState())
    val uiState: StateFlow<ProfileUiState> = _uiState.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            authRepository.getCurrentUser()
                .onSuccess { user -> _uiState.update { it.copy(user = user) } }
            positionRepository.getUserSummary()
                .onSuccess { summary -> _uiState.update { it.copy(summary = summary) } }
            _uiState.update { it.copy(isLoading = false) }
        }
    }

    fun showLogoutConfirm() {
        _uiState.update { it.copy(showLogoutConfirm = true) }
    }

    fun hideLogoutConfirm() {
        _uiState.update { it.copy(showLogoutConfirm = false) }
    }

    fun logout() {
        viewModelScope.launch {
            authRepository.logout()
        }
    }
}
