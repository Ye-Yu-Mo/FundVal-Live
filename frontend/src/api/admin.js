/**
 * 管理员相关 API
 */

const API_BASE = '/api';

/**
 * 获取所有用户列表
 */
export async function getUsers() {
  const response = await fetch(`${API_BASE}/auth/admin/users`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get users');
  }

  return response.json();
}

/**
 * 创建用户
 */
export async function createUser(username, password, isAdmin = false) {
  const response = await fetch(`${API_BASE}/auth/admin/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username,
      password,
      is_admin: isAdmin,
    }),
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create user');
  }

  return response.json();
}

/**
 * 删除用户
 */
export async function deleteUser(userId) {
  const response = await fetch(`${API_BASE}/auth/admin/users/${userId}`, {
    method: 'DELETE',
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete user');
  }

  return response.json();
}

/**
 * 获取注册开关状态
 */
export async function getAllowRegistration() {
  const response = await fetch(`${API_BASE}/auth/admin/settings/allow-registration`, {
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get registration setting');
  }

  return response.json();
}

/**
 * 设置注册开关
 */
export async function setAllowRegistration(allow) {
  const response = await fetch(`${API_BASE}/auth/admin/settings/allow-registration`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ allow }),
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update registration setting');
  }

  return response.json();
}

/**
 * 开启多用户模式
 */
export async function enableMultiUser(adminUsername, adminPassword) {
  const response = await fetch(`${API_BASE}/auth/admin/enable-multi-user`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      admin_username: adminUsername,
      admin_password: adminPassword,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to enable multi-user mode');
  }

  return response.json();
}
