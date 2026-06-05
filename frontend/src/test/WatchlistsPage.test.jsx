import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import WatchlistsPage from '../pages/WatchlistsPage';
import * as api from '../api';

// Mock API
vi.mock('../api', () => ({
  watchlistsAPI: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
    addItem: vi.fn(),
    removeItem: vi.fn(),
  },
  fundsAPI: {
    search: vi.fn(),
    batchUpdateNav: vi.fn(),
    batchEstimate: vi.fn(),
  },
}));

// Mock useNavigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

// 可控的 breakpoint mock
let mockScreens = { md: true };
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    Grid: {
      useBreakpoint: () => mockScreens,
    },
  };
});

const mockWatchlistWithItems = [
  {
    id: 1,
    name: '我的自选',
    items: [
      { fund_code: '000001', fund_name: '华夏成长混合' },
      { fund_code: '110011', fund_name: '易方达中小盘混合' },
    ],
  },
];

const mockNavResponse = {
  data: {
    '000001': { latest_nav: '1.2345', latest_nav_date: '2026-03-22' },
    110011: { latest_nav: '2.3456', latest_nav_date: '2026-03-22' },
  },
};

const mockEstimateResponse = {
  data: {
    '000001': { estimate_nav: '1.2400', estimate_growth: '0.45', fund_name: '华夏成长混合' },
    110011: { estimate_nav: '2.3500', estimate_growth: '-0.23', fund_name: '易方达中小盘混合' },
  },
};

describe('WatchlistsPage 桌面端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.watchlistsAPI.list.mockResolvedValue({ data: mockWatchlistWithItems });
    api.fundsAPI.batchUpdateNav.mockResolvedValue(mockNavResponse);
    api.fundsAPI.batchEstimate.mockResolvedValue(mockEstimateResponse);
  });

  it('数据加载后不渲染卡片', async () => {
    render(
      <BrowserRouter>
        <WatchlistsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('华夏成长混合')).toBeInTheDocument();
    });
    expect(screen.queryAllByTestId('fund-card')).toHaveLength(0);
  });

  it('渲染两只基金', async () => {
    render(
      <BrowserRouter>
        <WatchlistsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('华夏成长混合')).toBeInTheDocument();
      expect(screen.getByText('易方达中小盘混合')).toBeInTheDocument();
    });
  });
});

describe('WatchlistsPage 移动端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: false };
    api.watchlistsAPI.list.mockResolvedValue({ data: mockWatchlistWithItems });
    api.fundsAPI.batchUpdateNav.mockResolvedValue(mockNavResponse);
    api.fundsAPI.batchEstimate.mockResolvedValue(mockEstimateResponse);
  });

  it('不显示表格列头', async () => {
    render(
      <BrowserRouter>
        <WatchlistsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('华夏成长混合')).toBeInTheDocument();
    });
    expect(screen.queryByText('最新净值')).not.toBeInTheDocument();
  });

  it('显示基金卡片', async () => {
    render(
      <BrowserRouter>
        <WatchlistsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getAllByTestId('fund-card').length).toBeGreaterThan(0);
    });
  });
});

describe('WatchlistsPage 通用行为', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.watchlistsAPI.list.mockResolvedValue({ data: [] });
  });

  it('无自选列表时显示创建按钮', async () => {
    render(
      <BrowserRouter>
        <WatchlistsPage />
      </BrowserRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('创建第一个自选列表')).toBeInTheDocument();
    });
  });

  it('调用handleDelete时会重新拉取列表', async () => {
    const mockTwoWatchlists = [
      { id: 1, name: '列表A', items: [{ fund_code: '000001', fund_name: '基金A' }] },
      { id: 2, name: '列表B', items: [{ fund_code: '110011', fund_name: '基金B' }] },
    ];
    api.watchlistsAPI.list.mockResolvedValue({ data: mockTwoWatchlists });
    api.watchlistsAPI.delete.mockResolvedValue({});

    render(
      <BrowserRouter>
        <WatchlistsPage />
      </BrowserRouter>
    );

    // 验证初始列表调用
    await waitFor(() => {
      expect(api.watchlistsAPI.list).toHaveBeenCalled();
    });
    const initialCalls = api.watchlistsAPI.list.mock.calls.length;

    // 删除列表的 Popconfirm：找到删除图标并点击
    const deleteIcon = document.querySelector('.anticon-delete');
    fireEvent.click(deleteIcon);

    // 验证 Popconfirm 出现
    await waitFor(() => {
      expect(screen.getByText('确定删除？')).toBeInTheDocument();
    });

    // 点击确定按钮确认删除。antd Popconfirm 的门户渲染在 body 下
    // 选择器：antd v5 Popconfirm 内部结构使用 ant-popconfirm 类
    const okButton =
      document.querySelector('.ant-popconfirm .ant-btn-primary') ||
      document.querySelector('.ant-popover .ant-btn-primary');
    expect(okButton).not.toBeNull();
    fireEvent.click(okButton);

    await waitFor(() => {
      // handleDelete 内部会再次调用 list API 并自动选中剩余列表
      expect(api.watchlistsAPI.list.mock.calls.length).toBeGreaterThan(initialCalls);
    });
  });
});
