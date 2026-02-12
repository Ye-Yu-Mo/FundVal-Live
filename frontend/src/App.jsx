import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import InitializePage from './pages/InitializePage';
import ServerConfigPage from './pages/ServerConfigPage';
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
const isNativeApp = () => {
  return window.__TAURI__ !== undefined || window.Capacitor !== undefined;
};

function App() {
  const [serverConfigured, setServerConfigured] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // 如果是 Web 版本，直接标记为已配置
    if (!isNativeApp()) {
      setServerConfigured(true);
      setChecking(false);
      return;
    }

    // 检查是否已配置服务器
    const savedUrl = localStorage.getItem('apiBaseUrl');
    if (savedUrl) {
      setServerConfigured(true);
    }
    setChecking(false);
  }, []);

  const handleConfigSaved = () => {
    setServerConfigured(true);
  };

  if (checking) {
    return null; // 或者显示加载动画
  }

  // 如果是原生应用且未配置服务器，显示配置页面
  if (isNativeApp() && !serverConfigured) {
    return (
      <ConfigProvider locale={zhCN}>
        <ServerConfigPage onConfigSaved={handleConfigSaved} />
      </ConfigProvider>
    );
  }

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
