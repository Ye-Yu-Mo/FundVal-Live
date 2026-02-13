import axios from 'axios';

// 获取 API 基础 URL
const getApiBaseUrl = () => {
  // 优先使用 localStorage 中的配置
  const stored = localStorage.getItem('apiBaseUrl');
  if (stored) return stored;

  // 否则使用当前域名（生产环境）
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }

  // 开发环境 fallback
  return 'http://localhost:8000';
};

const api = axios.create({
  baseURL: `${getApiBaseUrl()}/api`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 token 和动态更新 baseURL
api.interceptors.request.use(
  (config) => {
    // 动态更新 baseURL
    config.baseURL = `${getApiBaseUrl()}/api`;

    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：处理 token 过期
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // 如果是 401 且不是刷新 token 请求，尝试刷新 token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        const apiBaseUrl = getApiBaseUrl();
        const response = await axios.post(`${apiBaseUrl}/api/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);

        // 重试原请求
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        // 刷新失败，清除 token 并跳转登录
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// 创建一个不带认证的 axios 实例，用于登录等公开接口
export const publicApi = axios.create({
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：动态更新 baseURL
publicApi.interceptors.request.use(
  (config) => {
    // 动态更新 baseURL
    config.baseURL = `${getApiBaseUrl()}/api`;
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;
