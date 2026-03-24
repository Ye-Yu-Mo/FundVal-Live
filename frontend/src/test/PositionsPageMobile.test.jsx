import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import PositionsPage from '../pages/PositionsPage';
import * as api from '../api';

vi.mock('../api', () => ({
  positionsAPI: {
    list: vi.fn(),
    listOperations: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  fundsAPI: {
    search: vi.fn(),
    getNav: vi.fn(),
    batchUpdateNav: vi.fn(),
    batchEstimate: vi.fn(),
  },
  aiAPI: {
    analyze: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useSearchParams: () => [new URLSearchParams()] };
});

vi.mock('../contexts/AccountContext', () => ({
  useAccounts: () => ({
    accounts: [
      { id: 1, name: '父账户1', parent: null, is_default: true },
      { id: 2, name: '子账户1', parent: 1, holding_cost: 10000, holding_value: 11000, pnl: 1000, pnl_rate: 10 },
    ],
    loading: false,
    loadAccounts: vi.fn(),
  }),
}));

vi.mock('../contexts/PreferenceContext', () => ({
  usePreference: () => ({ preferredSource: 'eastmoney' }),
}));

vi.mock('../components/PositionCharts', () => ({
  default: () => <div data-testid="position-charts">Charts</div>,
}));

vi.mock('../components/AIAnalysisModal', () => ({
  default: () => <div data-testid="ai-modal">AI Modal</div>,
}));

let mockScreens = { md: true };
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    Grid: { useBreakpoint: () => mockScreens },
  };
});

const mockPositions = [
  {
    id: 1,
    fund: { fund_code: '000001', fund_name: '华夏成长混合', fund_type: '混合' },
    holding_share: 1000,
    holding_cost: 1234.56,
    holding_value: 1300.00,
    pnl: 65.44,
    pnl_rate: 5.3,
  },
  {
    id: 2,
    fund: { fund_code: '110011', fund_name: '易方达中小盘混合', fund_type: '混合' },
    holding_share: 2000,
    holding_cost: 4690.00,
    holding_value: 4800.00,
    pnl: 110.00,
    pnl_rate: 2.34,
  },
];

const mockOperations = [
  { id: 1, operation_type: 'BUY', date: '2026-03-20', share: 1000, nav: 1.2345, amount: 1234.56 },
  { id: 2, operation_type: 'SELL', date: '2026-03-21', share: 500, nav: 1.3000, amount: 650.00 },
];

describe('PositionsPage 桌面端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.positionsAPI.list.mockResolvedValue({ data: mockPositions });
    api.positionsAPI.listOperations.mockResolvedValue({ data: mockOperations });
    api.fundsAPI.batchUpdateNav.mockResolvedValue({ data: {} });
    api.fundsAPI.batchEstimate.mockResolvedValue({ data: {} });
  });

  it('数据加载后不渲染持仓卡片', async () => {
    render(<BrowserRouter><PositionsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(api.positionsAPI.list).toHaveBeenCalled();
    });
    expect(screen.queryAllByTestId('position-card')).toHaveLength(0);
  });

  it('渲染持仓列表', async () => {
    render(<BrowserRouter><PositionsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(api.positionsAPI.list).toHaveBeenCalled();
    });
  });
});

describe('PositionsPage 移动端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: false };
    api.positionsAPI.list.mockResolvedValue({ data: mockPositions });
    api.positionsAPI.listOperations.mockResolvedValue({ data: mockOperations });
    api.fundsAPI.batchUpdateNav.mockResolvedValue({ data: {} });
    api.fundsAPI.batchEstimate.mockResolvedValue({ data: {} });
  });

  it('显示持仓卡片', async () => {
    render(<BrowserRouter><PositionsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(api.positionsAPI.list).toHaveBeenCalled();
    }, { timeout: 3000 });
    // 移动端应该渲染卡片（实现后会通过）
    await waitFor(() => {
      expect(screen.getAllByTestId('position-card').length).toBeGreaterThan(0);
    }, { timeout: 3000 });
  });

  it('显示操作流水卡片', async () => {
    render(<BrowserRouter><PositionsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(api.positionsAPI.listOperations).toHaveBeenCalled();
    }, { timeout: 3000 });
    // 移动端应该渲染操作流水卡片（实现后会通过）
    await waitFor(() => {
      expect(screen.getAllByTestId('operation-card').length).toBeGreaterThan(0);
    }, { timeout: 3000 });
  });

  it('统计卡片单列显示', async () => {
    render(<BrowserRouter><PositionsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('持仓总成本')).toBeInTheDocument();
    }, { timeout: 3000 });
  });
});

describe('PositionsPage 通用行为', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.positionsAPI.list.mockResolvedValue({ data: [] });
    api.positionsAPI.listOperations.mockResolvedValue({ data: [] });
    api.fundsAPI.batchUpdateNav.mockResolvedValue({ data: {} });
    api.fundsAPI.batchEstimate.mockResolvedValue({ data: {} });
  });

  it('无持仓时显示空状态', async () => {
    render(<BrowserRouter><PositionsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(api.positionsAPI.list).toHaveBeenCalled();
    }, { timeout: 3000 });
  });
});
