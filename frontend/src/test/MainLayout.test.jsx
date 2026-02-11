import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import MainLayout from '../layouts/MainLayout';
import * as auth from '../utils/auth';

// Mock auth utils
vi.mock('../utils/auth', () => ({
  getUser: vi.fn(),
  logout: vi.fn(),
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

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('MainLayout', () => {
  it('渲染侧边栏菜单', () => {
    auth.getUser.mockReturnValue({ username: 'testuser', role: 'user' });

    render(
      <BrowserRouter>
        <MainLayout>
          <div>Content</div>
        </MainLayout>
      </BrowserRouter>
    );

    expect(screen.getByText('基金估值与资产管理系统')).toBeInTheDocument();
    expect(screen.getByText('基金列表')).toBeInTheDocument();
    expect(screen.getByText('账户管理')).toBeInTheDocument();
    expect(screen.getByText('持仓查询')).toBeInTheDocument();
    expect(screen.getByText('自选列表')).toBeInTheDocument();
  });

  it('渲染用户信息', () => {
    auth.getUser.mockReturnValue({ username: 'testuser', role: 'user' });

    render(
      <BrowserRouter>
        <MainLayout>
          <div>Content</div>
        </MainLayout>
      </BrowserRouter>
    );

    expect(screen.getByText('testuser')).toBeInTheDocument();
  });

  it('渲染用户下拉菜单', () => {
    auth.getUser.mockReturnValue({ username: 'testuser', role: 'user' });

    render(
      <BrowserRouter>
        <MainLayout>
          <div>Content</div>
        </MainLayout>
      </BrowserRouter>
    );

    // 验证用户名显示
    expect(screen.getByText('testuser')).toBeInTheDocument();
  });

  it('渲染子组件内容', () => {
    auth.getUser.mockReturnValue({ username: 'testuser', role: 'user' });

    render(
      <BrowserRouter>
        <MainLayout>
          <div>Test Content</div>
        </MainLayout>
      </BrowserRouter>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });
});
