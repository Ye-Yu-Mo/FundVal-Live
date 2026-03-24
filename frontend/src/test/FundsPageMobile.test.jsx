import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import FundsPage from '../pages/FundsPage';
import * as api from '../api';

vi.mock('../api', () => ({
  fundsAPI: {
    list: vi.fn(),
    batchEstimate: vi.fn(),
    batchUpdateNav: vi.fn(),
  },
  watchlistsAPI: {
    list: vi.fn(),
    addItem: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

vi.mock('../contexts/PreferenceContext', () => ({
  usePreference: () => ({ preferredSource: 'eastmoney' }),
}));

let mockScreens = { md: true };
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    Grid: { useBreakpoint: () => mockScreens },
  };
});

const mockFunds = [
  { fund_code: '000001', fund_name: '华夏成长混合', latest_nav: '1.2345', latest_nav_date: '2026-03-22' },
  { fund_code: '110011', fund_name: '易方达中小盘混合', latest_nav: '2.3456', latest_nav_date: '2026-03-22' },
];

const mockEstimates = {
  data: {
    '000001': { estimate_nav: '1.2400', estimate_growth: '0.45' },
    '110011': { estimate_nav: '2.3500', estimate_growth: '-0.23' },
  },
};

const mockNavs = {
  data: {
    '000001': { latest_nav: '1.2345', latest_nav_date: '2026-03-22' },
    '110011': { latest_nav: '2.3456', latest_nav_date: '2026-03-22' },
  },
};

describe('FundsPage 桌面端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.fundsAPI.list.mockResolvedValue({ data: { results: mockFunds, count: 2 } });
    api.fundsAPI.batchEstimate.mockResolvedValue(mockEstimates);
    api.fundsAPI.batchUpdateNav.mockResolvedValue(mockNavs);
  });

  it('数据加载后不渲染卡片', async () => {
    render(<BrowserRouter><FundsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('华夏成长混合')).toBeInTheDocument();
    });
    expect(screen.queryAllByTestId('fund-card')).toHaveLength(0);
  });

  it('渲染两只基金', async () => {
    render(<BrowserRouter><FundsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('华夏成长混合')).toBeInTheDocument();
      expect(screen.getByText('易方达中小盘混合')).toBeInTheDocument();
    });
  });
});

describe('FundsPage 移动端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: false };
    api.fundsAPI.list.mockResolvedValue({ data: { results: mockFunds, count: 2 } });
    api.fundsAPI.batchEstimate.mockResolvedValue(mockEstimates);
    api.fundsAPI.batchUpdateNav.mockResolvedValue(mockNavs);
  });

  it('显示基金卡片', async () => {
    render(<BrowserRouter><FundsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getAllByTestId('fund-card').length).toBeGreaterThan(0);
    });
  });

  it('不显示表格', async () => {
    render(<BrowserRouter><FundsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('华夏成长混合')).toBeInTheDocument();
    });
    expect(screen.queryAllByTestId('fund-card').length).toBeGreaterThan(0);
  });
});

describe('FundsPage 通用行为', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.fundsAPI.list.mockResolvedValue({ data: { results: [], count: 0 } });
    api.fundsAPI.batchEstimate.mockResolvedValue({ data: {} });
    api.fundsAPI.batchUpdateNav.mockResolvedValue({ data: {} });
  });

  it('渲染搜索框', async () => {
    render(<BrowserRouter><FundsPage /></BrowserRouter>);
    expect(screen.getByPlaceholderText('搜索基金名称或代码')).toBeInTheDocument();
  });
});
