import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import * as api from '../api';

// Mock API
vi.mock('../api', () => ({
  login: vi.fn(),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('LoginPage', () => {
  it('渲染登录表单', () => {
    render(
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Fundval')).toBeInTheDocument();
    expect(screen.getByText('基金估值与资产管理系统')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /登/ })).toBeInTheDocument();
  });

  it('提交空表单显示验证错误', async () => {
    render(
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>
    );

    const submitButton = screen.getByRole('button', { name: /登/ });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('请输入用户名')).toBeInTheDocument();
      expect(screen.getByText('请输入密码')).toBeInTheDocument();
    });
  });

  it('登录成功跳转到 dashboard', async () => {
    api.login.mockResolvedValue({
      data: {
        access_token: 'test_token',
        refresh_token: 'test_refresh',
        user: {
          username: 'testuser',
          role: 'user',
        },
      },
    });

    render(
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>
    );

    const usernameInput = screen.getByPlaceholderText('用户名');
    const passwordInput = screen.getByPlaceholderText('密码');
    const submitButton = screen.getByRole('button', { name: /登/ });

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'testpass' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('testuser', 'testpass');
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });
});
