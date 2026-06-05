import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { usePreference } from './contexts/PreferenceContext';
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
import AdminPage from './pages/AdminPage';
import ComparePage from './pages/ComparePage';
import RankingsPage from './pages/RankingsPage';
import MarketPage from './pages/MarketPage';
import ProfilePage from './pages/ProfilePage';
import { isAuthenticated, getUser } from './utils/auth';
import { AuthProvider } from './contexts/AuthContext';
import { AccountProvider } from './contexts/AccountContext';
import { PreferenceProvider } from './contexts/PreferenceContext';

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

function AppInner() {
  const { themeMode } = usePreference();
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: themeMode === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
      }}
    >
      <Router>
        <Routes>
          <Route
            path="/"
            element={
              isAuthenticated() ? <Navigate to="/dashboard/watchlists" /> : <Navigate to="/login" />
            }
          />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/admin" element={<Navigate to="/dashboard/admin" />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/initialize" element={<InitializePage />} />
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <MainLayout>
                  <Navigate to="/dashboard/watchlists" />
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
          <Route
            path="/dashboard/market"
            element={
              <PrivateRoute>
                <MainLayout>
                  <MarketPage />
                </MainLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/dashboard/profile"
            element={
              <PrivateRoute>
                <MainLayout>
                  <ProfilePage />
                </MainLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/dashboard/rankings"
            element={
              <PrivateRoute>
                <MainLayout>
                  <RankingsPage />
                </MainLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/dashboard/compare"
            element={
              <PrivateRoute>
                <MainLayout>
                  <ComparePage />
                </MainLayout>
              </PrivateRoute>
            }
          />
          <Route
            path="/dashboard/admin"
            element={
              <PrivateRoute>
                <MainLayout>
                  <AdminPage />
                </MainLayout>
              </PrivateRoute>
            }
          />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

function App() {
  return (
    <AuthProvider>
      <AccountProvider>
        <PreferenceProvider>
          <AppInner />
        </PreferenceProvider>
      </AccountProvider>
    </AuthProvider>
  );
}

export default App;
