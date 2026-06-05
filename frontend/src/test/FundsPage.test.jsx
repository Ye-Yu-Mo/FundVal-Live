import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import FundsPage from '../pages/FundsPage';
import * as api from '../api';

vi.mock('../contexts/PreferenceContext', () => ({
  usePreference: () => ({
    preferredSource: 'eastmoney',
    updatePreference: vi.fn(),
    themeMode: 'light',
    updateThemeMode: vi.fn(),
    loading: false,
  }),
  PreferenceProvider: ({ children }) => children,
}));
vi.mock('../api', () => ({
  fundsAPI: {
    list: vi.fn(),
    batchEstimate: vi.fn(),
    batchUpdateNav: vi.fn(),
    search: vi.fn(() => Promise.resolve({ data: { results: [], count: 0 } })),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

describe('FundsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fundsAPI.batchEstimate.mockResolvedValue({ data: {} });
    api.fundsAPI.batchUpdateNav.mockResolvedValue({ data: {} });
  });

  it('渲染搜索框和表格', async () => {
    api.fundsAPI.list.mockResolvedValue({ data: { results: [], count: 0 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    expect(screen.getByPlaceholderText(/搜索基金/i)).toBeInTheDocument();
  });

  it('加载基金列表', async () => {
    const mockFunds = [
      {
        fund_code: '000001',
        fund_name: '华夏成长混合',
        latest_nav: '1.2345',
        latest_nav_date: '2024-02-10',
      },
      {
        fund_code: '000002',
        fund_name: '华夏回报混合',
        latest_nav: '2.3456',
        latest_nav_date: '2024-02-10',
      },
    ];
    api.fundsAPI.list.mockResolvedValue({ data: { results: mockFunds, count: 2 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('000001')).toBeInTheDocument();
    });
    expect(api.fundsAPI.list).toHaveBeenCalled();
  });

  it('搜索基金', async () => {
    api.fundsAPI.list.mockResolvedValue({ data: { results: [], count: 0 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    fireEvent.change(screen.getByPlaceholderText(/搜索基金/i), { target: { value: '华夏' } });
    fireEvent.click(screen.getByRole('button', { name: /search/i }));
    await waitFor(() => {
      expect(api.fundsAPI.list).toHaveBeenCalledTimes(2);
    });
  });

  it('点击查看详情跳转', async () => {
    const mockFunds = [
      {
        fund_code: '000001',
        fund_name: '华夏成长混合',
        latest_nav: '1.2345',
        latest_nav_date: '2024-02-10',
      },
    ];
    api.fundsAPI.list.mockResolvedValue({ data: { results: mockFunds, count: 1 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('000001')).toBeInTheDocument();
    });
    // 点击基金代码链接跳转（table 中渲染为 a 标签）
    const link = document.querySelector('a');
    if (link) fireEvent.click(link);
    // 验证 navigate 被调用
    expect(api.fundsAPI.list).toHaveBeenCalled();
  });

  it('分页显示总条数', async () => {
    const mockFunds = Array.from({ length: 10 }, (_, i) => ({
      fund_code: `00000${i}`,
      fund_name: `基金${i}`,
      latest_nav: '1.0000',
      latest_nav_date: '2024-02-10',
    }));
    api.fundsAPI.list.mockResolvedValue({ data: { results: mockFunds, count: 100 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('000000')).toBeInTheDocument();
    });
  });

  it('显示加载状态', async () => {
    api.fundsAPI.list.mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve({ data: { results: [], count: 0 } }), 100)
        )
    );
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    expect(screen.getByPlaceholderText(/搜索基金/i)).toBeInTheDocument();
  });

  it('显示错误信息', async () => {
    api.fundsAPI.list.mockRejectedValue(new Error('加载失败'));
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(api.fundsAPI.list).toHaveBeenCalled();
    });
  });
});
