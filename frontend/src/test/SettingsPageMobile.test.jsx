import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import SettingsPage from '../pages/SettingsPage';
import * as api from '../api';

vi.mock('../api', () => ({
  sourceAPI: {
    getStatus: vi.fn(),
    getQRCode: vi.fn(),
    logout: vi.fn(),
  },
  aiAPI: {
    getConfig: vi.fn(),
    updateConfig: vi.fn(),
    listTemplates: vi.fn(),
    createTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
  },
  fundsAPI: {
    search: vi.fn(),
  },
  notificationChannelsAPI: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    test: vi.fn(),
  },
  notificationRulesAPI: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../contexts/PreferenceContext', () => ({
  usePreference: () => ({ preferredSource: 'eastmoney', updatePreference: vi.fn() }),
}));

vi.mock('../App', () => ({
  isNativeApp: () => false,
}));

let mockScreens = { md: true };
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    Grid: { useBreakpoint: () => mockScreens },
  };
});

const mockChannels = [
  { id: 1, name: '微信通知', channel_type: 'wechat', is_active: true },
  { id: 2, name: '邮件通知', channel_type: 'email', is_active: false },
];

const mockRules = [
  { id: 1, name: '涨幅提醒', trigger_type: 'estimate_growth', is_active: true, channel: 1 },
  { id: 2, name: '净值更新', trigger_type: 'nav_update', is_active: false, channel: 2 },
];

describe('SettingsPage 桌面端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.notificationChannelsAPI.list.mockResolvedValue({ data: mockChannels });
    api.notificationRulesAPI.list.mockResolvedValue({ data: mockRules });
    api.aiAPI.getConfig.mockResolvedValue({ data: { api_key: '', model: '' } });
    api.aiAPI.listTemplates.mockResolvedValue({ data: [] });
    api.sourceAPI.getStatus.mockResolvedValue({ data: { logged_in: false } });
  });

  it('数据加载后不渲染渠道卡片', async () => {
    render(<BrowserRouter><SettingsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(api.notificationChannelsAPI.list).toHaveBeenCalled();
    });
    expect(screen.queryAllByTestId('channel-card')).toHaveLength(0);
  });

  it('数据加载后不渲染规则卡片', async () => {
    render(<BrowserRouter><SettingsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(api.notificationRulesAPI.list).toHaveBeenCalled();
    });
    expect(screen.queryAllByTestId('rule-card')).toHaveLength(0);
  });
});

describe('SettingsPage 移动端', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: false };
    api.notificationChannelsAPI.list.mockResolvedValue({ data: mockChannels });
    api.notificationRulesAPI.list.mockResolvedValue({ data: mockRules });
    api.aiAPI.getConfig.mockResolvedValue({ data: { api_key: '', model: '' } });
    api.aiAPI.listTemplates.mockResolvedValue({ data: [] });
    api.sourceAPI.getStatus.mockResolvedValue({ data: { logged_in: false } });
  });

  it('显示渠道卡片', async () => {
    render(<BrowserRouter><SettingsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getAllByTestId('channel-card').length).toBeGreaterThan(0);
    }, { timeout: 3000 });
  });

  it('显示规则卡片', async () => {
    render(<BrowserRouter><SettingsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getAllByTestId('rule-card').length).toBeGreaterThan(0);
    }, { timeout: 3000 });
  });
});

describe('SettingsPage 通用行为', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockScreens = { md: true };
    api.notificationChannelsAPI.list.mockResolvedValue({ data: [] });
    api.notificationRulesAPI.list.mockResolvedValue({ data: [] });
    api.aiAPI.getConfig.mockResolvedValue({ data: { api_key: '', model: '' } });
    api.aiAPI.listTemplates.mockResolvedValue({ data: [] });
    api.sourceAPI.getStatus.mockResolvedValue({ data: { logged_in: false } });
  });

  it('渲染数据源设置', async () => {
    render(<BrowserRouter><SettingsPage /></BrowserRouter>);
    await waitFor(() => {
      expect(screen.getByText('数据源设置')).toBeInTheDocument();
    });
  });
});
