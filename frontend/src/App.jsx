import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import LoginPage from './pages/LoginPage';
import InitializePage from './pages/InitializePage';
import MainLayout from './layouts/MainLayout';
import FundsPage from './pages/FundsPage';
import FundDetailPage from './pages/FundDetailPage';
import AccountsPage from './pages/AccountsPage';
import PositionsPage from './pages/PositionsPage';
import WatchlistsPage from './pages/WatchlistsPage';
import { isAuthenticated } from './utils/auth';

function PrivateRoute({ children }) {
  return isAuthenticated() ? children : <Navigate to="/" />;
}

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Routes>
          <Route
            path="/"
            element={
              isAuthenticated() ? (
                <Navigate to="/dashboard/funds" />
              ) : (
                <LoginPage />
              )
            }
          />
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
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
