import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import InitializePage from './pages/InitializePage';
import MainLayout from './layouts/MainLayout';
import FundsPage from './pages/FundsPage';
import FundDetailPage from './pages/FundDetailPage';
import AccountsPage from './pages/AccountsPage';
import PositionsPage from './pages/PositionsPage';
import WatchlistsPage from './pages/WatchlistsPage';
import SettingsPage from './pages/SettingsPage';
import { isAuthenticated } from './utils/auth';
import { AuthProvider } from './contexts/AuthContext';
import { AccountProvider } from './contexts/AccountContext';

function PrivateRoute({ children }) {
  return isAuthenticated() ? children : <Navigate to="/" />;
}

// 检查是否在桌面/移动应用中运行
export const isNativeApp = () => {
  // 检查 Tauri API
  if (window.__TAURI__ !== undefined) return true;

  // 检查 Capacitor API
  if (window.Capacitor !== undefined) return true;

  // 检查 Tauri 特有的环境变量
  if (window.__TAURI_INTERNALS__ !== undefined) return true;

  // 检查 user agent 中是否包含 Tauri
  if (navigator.userAgent.includes('Tauri')) return true;

  return false;
};

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <AuthProvider>
        <AccountProvider>
          <Router>
            <Routes>
              <Route
                path="/"
                element={
                  isAuthenticated() ? (
                    <Navigate to="/dashboard/funds" />
                  ) : (
                    <Navigate to="/login" />
                  )
                }
              />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/initialize" element={<InitializePage />} />
              <Route
                path="/dashboard"
                element={
                  <PrivateRoute>
                    <MainLayout>
                      <Navigate to="/dashboard/funds" />
                    </MainLayout>
                  </PrivateRoute>
                }
              />
              <Route
                path="/dashboard/funds"
                element={
                  <PrivateRoute>
                    <MainLayout>
                      <FundsPage />
                    </MainLayout>
                  </PrivateRoute>
                }
              />
              <Route
                path="/dashboard/funds/:code"
                element={
                  <PrivateRoute>
                    <MainLayout>
                      <FundDetailPage />
                    </MainLayout>
                  </PrivateRoute>
                }
              />
              <Route
                path="/dashboard/accounts"
                element={
                  <PrivateRoute>
                    <MainLayout>
                      <AccountsPage />
                    </MainLayout>
                  </PrivateRoute>
                }
              />
              <Route
                path="/dashboard/positions"
                element={
                  <PrivateRoute>
                    <MainLayout>
                      <PositionsPage />
                    </MainLayout>
                  </PrivateRoute>
                }
              />
              <Route
                path="/dashboard/watchlists"
                element={
                  <PrivateRoute>
                    <MainLayout>
                      <WatchlistsPage />
                    </MainLayout>
                  </PrivateRoute>
                }
              />
              <Route
                path="/dashboard/settings"
                element={
                  <PrivateRoute>
                    <MainLayout>
                      <SettingsPage />
                    </MainLayout>
                  </PrivateRoute>
                }
              />
            </Routes>
          </Router>
        </AccountProvider>
      </AuthProvider>
    </ConfigProvider>
  );
}

export default App;
