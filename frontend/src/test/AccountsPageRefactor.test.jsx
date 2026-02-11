import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AccountsPage from '../pages/AccountsPage';
import * as api from '../api';

// Mock API
vi.mock('../api', () => ({
  accountsAPI: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('AccountsPage - 阶段四重构', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockAccountsWithSummary = [
    {
      id: 'parent-1',
      name: '默认父账户',
      parent: null,
      is_default: true,
      holding_cost: '10000.00',
      holding_value: '12000.00',
      pnl: '2000.00',
      pnl_rate: '0.2000',
      estimate_value: '12500.00',
      estimate_pnl: '2500.00',
      estimate_pnl_rate: '0.2500',
      today_pnl: '500.00',
      today_pnl_rate: '0.0417',
      children: [
        {
          id: 'child-1',
          name: '子账户A',
          parent: 'parent-1',
          is_default: false,
          holding_cost: '5000.00',
          holding_value: '6000.00',
          pnl: '1000.00',
          pnl_rate: '0.2000',
          estimate_value: '6250.00',
          estimate_pnl: '1250.00',
          estimate_pnl_rate: '0.2500',
          today_pnl: '250.00',
          today_pnl_rate: '0.0417',
        },
        {
          id: 'child-2',
          name: '子账户B',
          parent: 'parent-1',
          is_default: false,
          holding_cost: '5000.00',
          holding_value: '6000.00',
          pnl: '1000.00',
          pnl_rate: '0.2000',
          estimate_value: '6250.00',
          estimate_pnl: '1250.00',
          estimate_pnl_rate: '0.2500',
          today_pnl: '250.00',
          today_pnl_rate: '0.0417',
        },
      ],
    },
    {
      id: 'parent-2',
      name: '其他父账户',
      parent: null,
      is_default: false,
      holding_cost: '8000.00',
      holding_value: '9000.00',
      pnl: '1000.00',
      pnl_rate: '0.1250',
      estimate_value: '9200.00',
      estimate_pnl: '1200.00',
      estimate_pnl_rate: '0.1500',
      today_pnl: '200.00',
      today_pnl_rate: '0.0222',
      children: [
        {
          id: 'child-3',
          name: '子账户C',
          parent: 'parent-2',
          is_default: false,
          holding_cost: '8000.00',
          holding_value: '9000.00',
          pnl: '1000.00',
          pnl_rate: '0.1250',
          estimate_value: '9200.00',
          estimate_pnl: '1200.00',
          estimate_pnl_rate: '0.1500',
          today_pnl: '200.00',
          today_pnl_rate: '0.0222',
        },
      ],
    },
  ];

  describe('父账户选择器', () => {
    it('显示父账户选择器', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        // 验证父账户选择器存在
        expect(screen.getByTestId('parent-account-selector')).toBeInTheDocument();
      });
    });

    it('默认选中默认父账户', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        const selector = screen.getByTestId('parent-account-selector');
        // 验证默认选中的是默认父账户
        expect(selector).toHaveTextContent('默认父账户');
      });
    });

    it('切换父账户选择器', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('parent-account-selector')).toBeInTheDocument();
      });

      // 点击选择器
      const selector = screen.getByTestId('parent-account-selector');
      fireEvent.mouseDown(selector.querySelector('.ant-select-selector'));

      // 等待下拉菜单出现
      await waitFor(() => {
        expect(screen.getByText('其他父账户')).toBeInTheDocument();
      });

      // 选择其他父账户
      fireEvent.click(screen.getByText('其他父账户'));

      // 验证选择器更新
      await waitFor(() => {
        expect(selector).toHaveTextContent('其他父账户');
      });
    });
  });

  describe('全部账户汇总按钮', () => {
    it('显示全部账户汇总按钮', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('all-accounts-summary-button')).toBeInTheDocument();
      });
    });

    it('点击全部账户汇总按钮', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('all-accounts-summary-button')).toBeInTheDocument();
      });

      // 点击全部账户汇总按钮
      const button = screen.getByTestId('all-accounts-summary-button');
      fireEvent.click(button);

      // 验证显示全部账户汇总
      await waitFor(() => {
        expect(screen.getByTestId('all-accounts-summary')).toBeInTheDocument();
      });
    });
  });

  describe('父账户汇总行', () => {
    it('显示父账户汇总行', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        // 验证父账户汇总行存在
        expect(screen.getByTestId('parent-account-summary')).toBeInTheDocument();
      });
    });

    it('父账户汇总显示正确', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        const summary = screen.getByTestId('parent-account-summary');
        // 验证汇总字段显示
        expect(summary).toHaveTextContent('10000.00'); // holding_cost
        expect(summary).toHaveTextContent('12000.00'); // holding_value
        expect(summary).toHaveTextContent('2000.00'); // pnl
        expect(summary).toHaveTextContent('20.00%'); // pnl_rate
      });
    });
  });

  describe('子账户列表', () => {
    it('显示子账户列表', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        // 验证子账户列表存在
        expect(screen.getByTestId('child-accounts-list')).toBeInTheDocument();
      });
    });

    it('子账户列表显示正确', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        // 验证子账户显示
        expect(screen.getByText('子账户A')).toBeInTheDocument();
        expect(screen.getByText('子账户B')).toBeInTheDocument();
      });
    });

    it('子账户显示汇总字段', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        const childList = screen.getByTestId('child-accounts-list');
        // 验证子账户汇总字段
        expect(childList).toHaveTextContent('5000.00'); // child holding_cost
        expect(childList).toHaveTextContent('6000.00'); // child holding_value
        expect(childList).toHaveTextContent('1000.00'); // child pnl
      });
    });
  });

  describe('切换父账户后更新视图', () => {
    it('切换父账户后更新汇总和子账户列表', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: mockAccountsWithSummary,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      // 等待初始加载
      await waitFor(() => {
        expect(screen.getByText('子账户A')).toBeInTheDocument();
        expect(screen.getByText('子账户B')).toBeInTheDocument();
      });

      // 切换到其他父账户
      const selector = screen.getByTestId('parent-account-selector');
      fireEvent.mouseDown(selector.querySelector('.ant-select-selector'));

      await waitFor(() => {
        expect(screen.getByText('其他父账户')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('其他父账户'));

      // 验证子账户列表更新
      await waitFor(() => {
        expect(screen.getByText('子账户C')).toBeInTheDocument();
        expect(screen.queryByText('子账户A')).not.toBeInTheDocument();
        expect(screen.queryByText('子账户B')).not.toBeInTheDocument();
      });

      // 验证汇总更新
      const summary = screen.getByTestId('parent-account-summary');
      expect(summary).toHaveTextContent('8000.00'); // new holding_cost
      expect(summary).toHaveTextContent('9000.00'); // new holding_value
    });
  });

  describe('无子账户的父账户', () => {
    it('显示空子账户列表', async () => {
      const emptyParent = [
        {
          id: 'parent-empty',
          name: '空父账户',
          parent: null,
          is_default: true,
          holding_cost: '0.00',
          holding_value: '0.00',
          pnl: '0.00',
          pnl_rate: null,
          estimate_value: '0.00',
          estimate_pnl: '0.00',
          estimate_pnl_rate: null,
          today_pnl: '0.00',
          today_pnl_rate: null,
          children: [],
        },
      ];

      api.accountsAPI.list.mockResolvedValue({
        data: emptyParent,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        const childList = screen.getByTestId('child-accounts-list');
        // 验证空列表提示
        expect(childList).toHaveTextContent(/暂无子账户/);
      });
    });
  });
});
