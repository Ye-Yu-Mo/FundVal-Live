import axios from 'axios';

const API_BASE_URL = '/api';

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

export const getFundHistory = async (fundId, limit = 30, accountId = null) => {
    try {
        const params = { limit };
        if (accountId) {
            params.account_id = accountId;
        }
        const response = await api.get(`/fund/${fundId}/history`, { params });
        return response.data;
    } catch (error) {
        console.error("Get history failed", error);
        return { history: [], transactions: [] };
    }
};

export const subscribeFund = async (fundId, data) => {
    return api.post(`/fund/${fundId}/subscribe`, data);
};

export const getFundCategories = async () => {
    try {
        const response = await api.get('/categories');
        return response.data.categories || [];
    } catch (error) {
        console.error("Get categories failed", error);
        return [];
    }
};

// Account management
export const getAccounts = async () => {
    try {
        const response = await api.get('/accounts');
        return response.data.accounts || [];
    } catch (error) {
        console.error("Get accounts failed", error);
        return [];
    }
};

export const createAccount = async (data) => {
    return api.post('/accounts', data);
};

export const updateAccount = async (accountId, data) => {
    return api.put(`/accounts/${accountId}`, data);
};

export const deleteAccount = async (accountId) => {
    return api.delete(`/accounts/${accountId}`);
};

// Position management (with account_id)
export const getAccountPositions = async (accountId = 1) => {
    try {
        const response = await api.get('/account/positions', { params: { account_id: accountId } });
        return response.data;
    } catch (error) {
        console.error("Get positions failed", error);
        throw error;
    }
};

export const updatePosition = async (data, accountId = 1) => {
    return api.post('/account/positions', data, { params: { account_id: accountId } });
};

export const deletePosition = async (code, accountId = 1) => {
    return api.delete(`/account/positions/${code}`, { params: { account_id: accountId } });
};

export const addPositionTrade = async (code, data, accountId = 1) => {
    const response = await api.post(`/account/positions/${code}/add`, data, { params: { account_id: accountId } });
    return response.data;
};

export const reducePositionTrade = async (code, data, accountId = 1) => {
    const response = await api.post(`/account/positions/${code}/reduce`, data, { params: { account_id: accountId } });
    return response.data;
};

export const getTransactions = async (accountId = 1, code = null, limit = 100) => {
    const params = { account_id: accountId, limit };
    if (code) params.code = code;
    const response = await api.get('/account/transactions', { params });
    return response.data.transactions || [];
};

export const updatePositionsNav = async (accountId = 1) => {
    return api.post('/account/positions/update-nav', null, { params: { account_id: accountId } });
};

// AI Prompts management
export const getPrompts = async () => {
    try {
        const response = await api.get('/ai/prompts');
        return response.data.prompts || [];
    } catch (error) {
        console.error("Get prompts failed", error);
        return [];
    }
};

export const createPrompt = async (data) => {
    return api.post('/ai/prompts', data);
};

export const updatePrompt = async (id, data) => {
    return api.put(`/ai/prompts/${id}`, data);
};

export const deletePrompt = async (id) => {
    return api.delete(`/ai/prompts/${id}`);
};

// Data import/export
export const exportData = async (modules) => {
    try {
        const modulesParam = modules.join(',');
        const response = await api.get(`/data/export?modules=${modulesParam}`, {
            responseType: 'blob'
        });

        // Create download link
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;

        // Extract filename from Content-Disposition header or use default
        const contentDisposition = response.headers['content-disposition'];
        let filename = 'fundval_export.json';
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }

        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);

        return { success: true };
    } catch (error) {
        console.error('Export failed', error);
        throw error;
    }
};

export const importData = async (data, modules, mode) => {
    return api.post('/data/import', { data, modules, mode });
};

// User preferences (watchlist, current account, sort option)
export const getPreferences = async () => {
    try {
        const response = await api.get('/preferences');
        return response.data;
    } catch (error) {
        console.error('Get preferences failed', error);
        return { watchlist: '[]', currentAccount: 1, sortOption: null };
    }
};

export const updatePreferences = async (data) => {
    return api.post('/preferences', data);
};
