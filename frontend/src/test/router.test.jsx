import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import MainLayout from '../layouts/MainLayout';
import FundsPage from '../pages/FundsPage';
import * as auth from '../utils/auth';

// Mock auth utils
vi.mock('../utils/auth', () => ({
  getToken: vi.fn(),
  getUser: vi.fn(),
  isAuthenticated: vi.fn(),
}));

// Mock Ant Design Grid
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    Grid: {
      useBreakpoint: () => ({ md: true }), // 默认桌面端
    },
  };
});

function PrivateRoute({ children }) {
  return auth.isAuthenticated() ? children : <Navigate to="/" />;
}

describe('Router', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('未登录访问 /dashboard 跳转到登录页', async () => {
    auth.isAuthenticated.mockReturnValue(false);

    render(
      <MemoryRouter initialEntries={['/dashboard/funds']}>
        <Routes>
          <Route
            path="/"
            element={
              auth.isAuthenticated() ? (
                <Navigate to="/dashboard/funds" />
              ) : (
                <LoginPage />
              )
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
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Fundval')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    });
  });

  it('已登录访问 /dashboard 正常渲染', async () => {
    auth.isAuthenticated.mockReturnValue(true);
    auth.getUser.mockReturnValue({ username: 'testuser', role: 'user' });

    render(
      <MemoryRouter initialEntries={['/dashboard/funds']}>
        <Routes>
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
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('基金估值与资产管理系统')).toBeInTheDocument();
    });
  });

  it('已登录访问 / 跳转到 /dashboard', async () => {
    auth.isAuthenticated.mockReturnValue(true);
    auth.getUser.mockReturnValue({ username: 'testuser', role: 'user' });

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              auth.isAuthenticated() ? (
                <Navigate to="/dashboard/funds" />
              ) : (
                <LoginPage />
              )
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
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('基金估值与资产管理系统')).toBeInTheDocument();
    });
  });

  it('未登录访问 / 显示登录页', async () => {
    auth.isAuthenticated.mockReturnValue(false);

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              auth.isAuthenticated() ? (
                <Navigate to="/dashboard/funds" />
              ) : (
                <LoginPage />
              )
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Fundval')).toBeInTheDocument();
    });
  });
});
