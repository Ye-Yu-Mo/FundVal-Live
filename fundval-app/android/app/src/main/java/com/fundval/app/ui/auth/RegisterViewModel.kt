package com.fundval.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fundval.app.data.repository.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class RegisterFormState(
    val username: String = "",
    val password: String = "",
    val passwordConfirm: String = ""
)

@HiltViewModel
class RegisterViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<RegisterUiState>(RegisterUiState.Idle)
    val uiState: StateFlow<RegisterUiState> = _uiState.asStateFlow()

    private val _formState = MutableStateFlow(RegisterFormState())
    val formState: StateFlow<RegisterFormState> = _formState.asStateFlow()

    fun onUsernameChange(username: String) {
        _formState.update { it.copy(username = username) }
    }

    fun onPasswordChange(password: String) {
        _formState.update { it.copy(password = password) }
    }

    fun onPasswordConfirmChange(passwordConfirm: String) {
        _formState.update { it.copy(passwordConfirm = passwordConfirm) }
    }

    fun register() {
        val form = _formState.value

        if (form.username.isBlank() || form.password.isBlank()) {
            _uiState.value = RegisterUiState.Error("请输入用户名和密码")
            return
        }

        if (form.password != form.passwordConfirm) {
            _uiState.value = RegisterUiState.Error("两次密码不一致")
            return
        }

        if (form.password.length < 6) {
            _uiState.value = RegisterUiState.Error("密码长度至少 6 位")
            return
        }

        viewModelScope.launch {
            _uiState.value = RegisterUiState.Loading

            authRepository.register(form.username, form.password, form.passwordConfirm)
                .onSuccess {
                    _uiState.value = RegisterUiState.Success
                }
                .onFailure { e ->
                    val message = when {
                        e.message?.contains("403") == true -> "注册未开放，请联系管理员"
                        e.message?.contains("400") == true -> "注册失败，用户名可能已存在"
                        else -> e.message ?: "注册失败"
                    }
                    _uiState.value = RegisterUiState.Error(message)
                }
        }
    }
}
