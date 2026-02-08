/**
 * 认证相关 API
 */

const API_BASE = '/api';

/**
 * 获取系统模式
 */
export async function getAuthMode() {
  const response = await fetch(`${API_BASE}/auth/mode`);
  if (!response.ok) {
    throw new Error('Failed to get auth mode');
  }
  return response.json();
}

/**
 * 登录
 */
export async function login(username, password) {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
    credentials: 'include', // 重要：携带 cookie
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  return response.json();
}

/**
 * 登出
 */
export async function logout() {
  const response = await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Logout failed');
  }

  return response.json();
}

/**
 * 获取当前用户信息
 */
export async function getMe() {
  const response = await fetch(`${API_BASE}/auth/me`, {
    credentials: 'include',
  });

  if (!response.ok) {
    if (response.status === 401) {
      return null; // 未登录
    }
    throw new Error('Failed to get user info');
  }

  return response.json();
}

/**
 * 修改密码
 */
export async function changePassword(oldPassword, newPassword) {
  const response = await fetch(`${API_BASE}/auth/change-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
    }),
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to change password');
  }

  return response.json();
}
