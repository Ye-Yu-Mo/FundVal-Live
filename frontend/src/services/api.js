import axios from 'axios';

const API_BASE_URL = 'http://localhost:21345/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
});

export const searchFunds = async (query) => {
  try {
    const response = await api.get('/search', { params: { q: query } });
    return response.data;
  } catch (error) {
    console.error("Search failed", error);
    return [];
  }
};

export const getFundDetail = async (fundId) => {
  try {
    const response = await api.get(`/fund/${fundId}`);
    return response.data;
  } catch (error) {
    console.error(`Get fund ${fundId} failed`, error);
    throw error;
  }
};

export const getFundHistory = async (fundId, limit = 30) => {
    try {
        const response = await api.get(`/fund/${fundId}/history`, { params: { limit } });
        return response.data;
    } catch (error) {
        console.error("Get history failed", error);
        return [];
    }
};

export const subscribeFund = async (fundId, data) => {
    return api.post(`/fund/${fundId}/subscribe`, data);
};

export const getAccountPositions = async () => {
    try {
        const response = await api.get('/account/positions');
        return response.data;
    } catch (error) {
        console.error("Get positions failed", error);
        throw error;
    }
};

export const updatePosition = async (data) => {
    return api.post('/account/positions', data);
};

export const deletePosition = async (code) => {
    return api.delete(`/account/positions/${code}`);
};

export const addPositionTrade = async (code, data) => {
    const response = await api.post(`/account/positions/${code}/add`, data);
    return response.data;
};

export const reducePositionTrade = async (code, data) => {
    const response = await api.post(`/account/positions/${code}/reduce`, data);
    return response.data;
};

export const getTransactions = async (code = null, limit = 100) => {
    const params = { limit };
    if (code) params.code = code;
    const response = await api.get('/account/transactions', { params });
    return response.data.transactions || [];
};
