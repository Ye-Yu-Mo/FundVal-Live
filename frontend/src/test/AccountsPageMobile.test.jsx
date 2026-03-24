import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AccountsPage from '../pages/AccountsPage';

vi.mock('../api', () => ({
  accountsAPI: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    getSummary: vi.fn(),
  },
}));

vi.mock('../contexts/PreferenceContext', () => ({
  usePreference: () => ({ preferredSource: 'eastmoney' }),
}));

const mockAccounts = [
  {
    id: 1,
    name: '主账户',
    parent: null,
    is_default: true,
    holding_cost: 10000,
    holding_value: 11000,
    pnl: 1000,
    pnl_rate: 10,
    children: [
      {
        id: 2,
        name: '子账户A',
        parent: 1,
        is_default: false,
        holding_cost: 5000,
        holding_value: 5500,
        pnl: 500,
        pnl_rate: 10,
      },
    ],
  },
];

vi.mock('../contexts/AccountContext', () => ({
  useAccounts: () => ({
    accounts: mockAccounts,
    loading: false,
    loadAccounts: vi.fn(),
    createAccount: vi.fn(),
    updateAccount: vi.fn(),
    deleteAccount: vi.fn(),
  }),
}));

let mockScreens = { md: true };
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    Grid: { useBreakpoint: () => mockScreens },
  };
});

describe('AccountsPage 桌面端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
  });

  it('不渲染父账户卡片', async () => {
    render(<BrowserRouter><AccountsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.queryAllByTestId('parent-account-card')).toHaveLength(0);
    });
  });

  it('不渲染子账户卡片', async () => {
    render(<BrowserRouter><AccountsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.queryAllByTestId('child-account-card')).toHaveLength(0);
    });
  });
});

describe('AccountsPage 移动端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: false };
  });

  it('显示父账户卡片', async () => {
    render(<BrowserRouter><AccountsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('全部账户汇总')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('全部账户汇总'));
    await waitFor(() => {
      expect(screen.getAllByTestId('parent-account-card').length).toBeGreaterThan(0);
    }, { timeout: 3000 });
  });

  it('显示子账户卡片', async () => {
    render(<BrowserRouter><AccountsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getAllByTestId('child-account-card').length).toBeGreaterThan(0);
    }, { timeout: 3000 });
  });
});

describe('AccountsPage 通用行为', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
  });

  it('渲染页面标题', async () => {
    render(<BrowserRouter><AccountsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('账户管理')).toBeInTheDocument();
    });
  });
});
