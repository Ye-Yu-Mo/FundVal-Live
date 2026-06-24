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

data class LoginFormState(
    val serverUrl: String = "http://185.239.224.208:21345/api",
    val username: String = "",
    val password: String = ""
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val authRepository: AuthRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<LoginUiState>(LoginUiState.Idle)
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    private val _formState = MutableStateFlow(LoginFormState())
    val formState: StateFlow<LoginFormState> = _formState.asStateFlow()

    fun onUsernameChange(username: String) {
        _formState.update { it.copy(username = username) }
    }

    fun onPasswordChange(password: String) {
        _formState.update { it.copy(password = password) }
    }

    fun login() {
        val form = _formState.value
        if (form.username.isBlank() || form.password.isBlank()) {
            _uiState.value = LoginUiState.Error("请输入用户名和密码")
            return
        }

        viewModelScope.launch {
            _uiState.value = LoginUiState.Loading

            authRepository.login(form.username, form.password)
                .onSuccess {
                    _uiState.value = LoginUiState.Success
                }
                .onFailure { e ->
                    val message = when {
                        e.message?.contains("401") == true -> "用户名或密码错误"
                        e.message?.contains("Unable to resolve host") == true -> "无法连接服务器，请检查地址"
                        e.message?.contains("timeout") == true -> "连接超时，请检查网络"
                        else -> e.message ?: "登录失败"
                    }
                    _uiState.value = LoginUiState.Error(message)
                }
        }
    }
}
