import api from './axios';
import axios from 'axios';

// 系统管理
export const healthCheck = () => api.get('/health/');

// Bootstrap 初始化（不带 token）
export const verifyBootstrapKey = (key) =>
  axios.post('/api/admin/bootstrap/verify', { bootstrap_key: key });

export const initializeSystem = (data) =>
  axios.post('/api/admin/bootstrap/initialize', data);

// 认证（不带 token）
export const login = (username, password) =>
  axios.post('/api/auth/login', { username, password });

export const refreshToken = (refreshToken) =>
  axios.post('/api/auth/refresh', { refresh_token: refreshToken });

export const getCurrentUser = () => api.get('/auth/me');

export const changePassword = (oldPassword, newPassword) =>
  api.put('/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  });
