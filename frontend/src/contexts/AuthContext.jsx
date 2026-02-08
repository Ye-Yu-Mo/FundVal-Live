import React, { createContext, useContext, useState, useEffect } from 'react';
import { getAuthMode, login as apiLogin, logout as apiLogout, getMe } from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [isMultiUserMode, setIsMultiUserMode] = useState(false);
  const [loading, setLoading] = useState(true);

  // 检查系统模式和认证状态
  const checkAuth = async () => {
    try {
      // 1. 获取系统模式
      const modeData = await getAuthMode();
      setIsMultiUserMode(modeData.multi_user_mode);

      // 2. 如果是多用户模式，检查登录状态
      if (modeData.multi_user_mode) {
        try {
          const user = await getMe();
          setCurrentUser(user);
        } catch (error) {
          // 未登录或 session 过期
          setCurrentUser(null);
        }
      } else {
        // 单用户模式，不需要登录
        setCurrentUser(null);
      }
    } catch (error) {
      console.error('Failed to check auth:', error);
    } finally {
      setLoading(false);
    }
  };

  // 登录
  const login = async (username, password) => {
    const user = await apiLogin(username, password);
    setCurrentUser(user);
    return user;
  };

  // 登出
  const logout = async () => {
    await apiLogout();
    setCurrentUser(null);
  };

  // 初始化时检查认证状态
  useEffect(() => {
    checkAuth();
  }, []);

  const value = {
    currentUser,
    isAdmin: currentUser?.is_admin || false,
    isMultiUserMode,
    loading,
    login,
    logout,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
