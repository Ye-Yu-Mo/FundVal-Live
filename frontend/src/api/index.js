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

// 基金管理
export const fundsAPI = {
  list: (params) => api.get('/funds/', { params }),
  get: (code) => api.get(`/funds/${code}/`),
  search: (keyword) => api.get('/funds/', { params: { search: keyword } }),
  getEstimate: (code, source) => api.get(`/funds/${code}/estimate/`, { params: { source } }),
  getAccuracy: (code) => api.get(`/funds/${code}/accuracy/`),
  batchEstimate: (fundCodes) => api.post('/funds/batch_estimate/', { fund_codes: fundCodes }),
  batchUpdateNav: (fundCodes) => api.post('/funds/batch_update_nav/', { fund_codes: fundCodes }),
  queryNav: (fundCode, operationDate, before15) => api.post('/funds/query_nav/', {
    fund_code: fundCode,
    operation_date: operationDate,
    before_15: before15
  }),
};

// 账户管理
export const accountsAPI = {
  list: () => api.get('/accounts/'),
  create: (data) => api.post('/accounts/', data),
  update: (id, data) => api.put(`/accounts/${id}/`, data),
  delete: (id) => api.delete(`/accounts/${id}/`),
};

// 持仓管理
export const positionsAPI = {
  list: (accountId) => api.get('/positions/', { params: { account_id: accountId } }),
  createOperation: (data) => api.post('/positions/operations/', data),
  listOperations: (params) => api.get('/positions/operations/', { params }),
  deleteOperation: (id) => api.delete(`/positions/operations/${id}/`),
};

// 自选列表
export const watchlistsAPI = {
  list: () => api.get('/watchlists/'),
  create: (data) => api.post('/watchlists/', data),
  get: (id) => api.get(`/watchlists/${id}/`),
  delete: (id) => api.delete(`/watchlists/${id}/`),
  addItem: (id, fundId) => api.post(`/watchlists/${id}/items/`, { fund_id: fundId }),
  removeItem: (id, fundId) => api.delete(`/watchlists/${id}/items/${fundId}/`),
  reorder: (id, items) => api.put(`/watchlists/${id}/reorder/`, { items }),
};

