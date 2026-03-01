import api, { publicApi } from './axios';

// 系统管理
export const healthCheck = () => api.get('/health/');

// Bootstrap 初始化（不带 token）
export const verifyBootstrapKey = (key) =>
  publicApi.post('/admin/bootstrap/verify', { bootstrap_key: key });

export const initializeSystem = (data) =>
  publicApi.post('/admin/bootstrap/initialize', data);

// 认证（不带 token）
export const login = (username, password) =>
  publicApi.post('/auth/login', { username, password });

export const register = (username, password, passwordConfirm) =>
  publicApi.post('/users/register/', { username, password, password_confirm: passwordConfirm });

export const refreshToken = (refreshToken) =>
  publicApi.post('/auth/refresh', { refresh_token: refreshToken });

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
  detail: (fundCode) => api.get(`/funds/${fundCode}/`),
  estimate: (fundCode) => api.get(`/funds/${fundCode}/estimate/`),
  marketQuote: (fundCode) => api.get(`/funds/${fundCode}/market_quote/`),
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
  navHistory: (fundCode, params) => api.get('/nav-history/', {
    params: { fund_code: fundCode, ...params }
  }),
  syncNavHistory: (fundCodes, startDate, endDate) => api.post('/nav-history/sync/', {
    fund_codes: fundCodes,
    start_date: startDate,
    end_date: endDate
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
  listByFund: (fundCode) => api.get('/positions/', { params: { fund_code: fundCode } }),
  createOperation: (data) => api.post('/positions/operations/', data),
  listOperations: (params) => api.get('/positions/operations/', { params }),
  deleteOperation: (id) => api.delete(`/positions/operations/${id}/`),
  getHistory: (accountId, days = 30) => api.get('/positions/history/', {
    params: { account_id: accountId, days }
  }),
};

// 自选列表
export const watchlistsAPI = {
  list: () => api.get('/watchlists/'),
  create: (data) => api.post('/watchlists/', data),
  get: (id) => api.get(`/watchlists/${id}/`),
  delete: (id) => api.delete(`/watchlists/${id}/`),
  addItem: (id, fundCode) => api.post(`/watchlists/${id}/items/`, { fund_code: fundCode }),
  removeItem: (id, fundCode) => api.delete(`/watchlists/${id}/items/${fundCode}/`),
  reorder: (id, items) => api.put(`/watchlists/${id}/reorder/`, { items }),
};

