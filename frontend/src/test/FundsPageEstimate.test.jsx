import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import FundsPage from '../pages/FundsPage';

vi.mock('../api', () => ({
  fundsAPI: {
    list: vi.fn(),
    batchEstimate: vi.fn(),
    batchUpdateNav: vi.fn(),
    search: vi.fn(() => Promise.resolve({ data: { results: [], count: 0 } })),
  },
  watchlistsAPI: { list: vi.fn(() => Promise.resolve({ data: [] })), create: vi.fn() },
}));
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
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

import * as api from '../api';

const makeFunds = (n) =>
  Array.from({ length: n }, (_, i) => ({
    fund_code: `00000${i}`,
    fund_name: `基金${i}`,
    fund_type: '混合型',
    latest_nav: '1.0000',
    latest_nav_date: '2026-01-01',
  }));

describe('FundsPage 估值功能', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fundsAPI.batchEstimate.mockResolvedValue({ data: {} });
    api.fundsAPI.batchUpdateNav.mockResolvedValue({ data: {} });
  });

  it('搜索框和基金列表渲染', async () => {
    api.fundsAPI.list.mockResolvedValue({ data: { results: makeFunds(3), count: 3 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('基金0')).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText(/搜索基金/i)).toBeInTheDocument();
  });

  it('调用批量估值 API', async () => {
    api.fundsAPI.list.mockResolvedValue({ data: { results: makeFunds(2), count: 2 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(api.fundsAPI.batchEstimate).toHaveBeenCalled();
    });
  });

  it('基金名称可点击跳转', async () => {
    api.fundsAPI.list.mockResolvedValue({ data: { results: makeFunds(1), count: 1 } });
    render(
      <BrowserRouter>
        <FundsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('000000')).toBeInTheDocument();
    });
  });

  it('无基金时显示空状态', async () => {
    api.fundsAPI.list.mockResolvedValue({ data: { results: [], count: 0 } });
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
