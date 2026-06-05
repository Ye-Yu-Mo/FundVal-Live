import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { accountsAPI } from '../api';

const AccountContext = createContext(null);

export const AccountProvider = ({ children }) => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedAccountId, setSelectedAccountId] = useState(null);

  // 加载账户列表
  const loadAccounts = useCallback(
    async (force = false) => {
      // 如果已有数据且不是强制刷新，直接返回
      if (accounts.length > 0 && !force) {
        return accounts;
      }

      setLoading(true);
      setError(null);
      try {
        const response = await accountsAPI.list();
        const data = response.data;
        setAccounts(data);

        // 如果没有选中账户，自动选择默认账户或第一个账户
        if (!selectedAccountId && data.length > 0) {
          const defaultAccount = data.find((acc) => acc.is_default);
          setSelectedAccountId(defaultAccount?.id || data[0].id);
        }

        return data;
      } catch (err) {
        setError(err.message || '加载账户失败');
      } finally {
        setLoading(false);
      }
    },
    [accounts.length, selectedAccountId]
  );

  // 创建账户
  const createAccount = useCallback(async (accountData) => {
    try {
      const response = await accountsAPI.create(accountData);
      const newAccount = response.data;
      setAccounts((prev) => [...prev, newAccount]);
      return newAccount;
    } catch (err) {
      setError(err.message || '创建账户失败');
      throw err;
    }
  }, []);

  // 更新账户
  const updateAccount = useCallback(async (id, accountData) => {
    try {
      const response = await accountsAPI.update(id, accountData);
      const updatedAccount = response.data;
      setAccounts((prev) => prev.map((acc) => (acc.id === id ? updatedAccount : acc)));
      return updatedAccount;
    } catch (err) {
      setError(err.message || '更新账户失败');
      throw err;
    }
  }, []);

  // 删除账户
  const deleteAccount = useCallback(
    async (id) => {
      try {
        await accountsAPI.delete(id);
        setAccounts((prev) => prev.filter((acc) => acc.id !== id));

        // 如果删除的是当前选中的账户，清除选中状态
        if (selectedAccountId === id) {
          setSelectedAccountId(null);
        }
      } catch (err) {
        setError(err.message || '删除账户失败');
        throw err;
      }
    },
    [selectedAccountId]
  );

  // 获取选中的账户
  const selectedAccount = accounts.find((acc) => acc.id === selectedAccountId);

  // 获取子账户列表
  const getChildAccounts = useCallback(
    (parentId) => {
      return accounts.filter((acc) => acc.parent === parentId);
    },
    [accounts]
  );

  // 获取父账户列表
  const getParentAccounts = useCallback(() => {
    return accounts.filter((acc) => !acc.parent);
  }, [accounts]);

  const value = {
    accounts,
    loading,
    error,
    selectedAccountId,
    selectedAccount,
    setSelectedAccountId,
    loadAccounts,
    createAccount,
    updateAccount,
    deleteAccount,
    getChildAccounts,
    getParentAccounts,
  };

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
};

export const useAccounts = () => {
  const context = useContext(AccountContext);
  if (!context) {
    throw new Error('useAccounts must be used within an AccountProvider');
  }
  return context;
};
