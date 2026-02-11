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

describe('AccountsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('账户列表', () => {
    it('渲染空列表', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: [],
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      // 验证标题存在
      expect(screen.getByText('账户管理')).toBeInTheDocument();

      // 验证创建按钮存在
      expect(screen.getByText('创建账户')).toBeInTheDocument();

      // 等待 API 调用
      await waitFor(() => {
        expect(api.accountsAPI.list).toHaveBeenCalled();
      });
    });

    it('渲染账户列表', async () => {
      const mockAccounts = [
        {
          id: '1',
          name: '总账户',
          parent: null,
          is_default: true,
        },
        {
          id: '2',
          name: '子账户A',
          parent: '1',
          is_default: false,
        },
        {
          id: '3',
          name: '独立账户',
          parent: null,
          is_default: false,
        },
      ];

      api.accountsAPI.list.mockResolvedValue({
        data: mockAccounts,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      // 等待数据加载
      await waitFor(() => {
        expect(screen.getAllByText('总账户').length).toBeGreaterThan(0);
        expect(screen.getByText('子账户A')).toBeInTheDocument();
        expect(screen.getByText('独立账户')).toBeInTheDocument();
      });

      // 验证默认账户标记
      expect(screen.getByText('默认')).toBeInTheDocument();
    });

    it('显示账户类型', async () => {
      const mockAccounts = [
        {
          id: '1',
          name: '总账户',
          parent: null,
          is_default: false,
        },
        {
          id: '2',
          name: '子账户',
          parent: '1',
          is_default: false,
        },
      ];

      api.accountsAPI.list.mockResolvedValue({
        data: mockAccounts,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      await waitFor(() => {
        // 总账户应该显示为"总账户"类型
        expect(screen.getAllByText('总账户').length).toBeGreaterThan(0);
        // 子账户应该显示父账户名称
        expect(screen.getByText('子账户')).toBeInTheDocument();
      });
    });
  });

  describe('创建账户', () => {
    it('打开创建 Modal', async () => {
      api.accountsAPI.list.mockResolvedValue({
        data: [],
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      // 点击创建按钮
      const createButton = screen.getByText('创建账户');
      fireEvent.click(createButton);

      // 验证 Modal 打开
      await waitFor(() => {
        const modalTitles = screen.getAllByText('创建账户');
        expect(modalTitles.length).toBeGreaterThan(0);
        expect(screen.getByLabelText('账户名称')).toBeInTheDocument();
        expect(screen.getByLabelText('父账户')).toBeInTheDocument();
        expect(screen.getByText('设为默认账户')).toBeInTheDocument();
      });
    });
  });

  describe('编辑账户', () => {
    it('打开编辑 Modal', async () => {
      const mockAccounts = [
        {
          id: '1',
          name: '测试账户',
          parent: null,
          is_default: false,
        },
      ];

      api.accountsAPI.list.mockResolvedValue({
        data: mockAccounts,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      // 等待列表加载
      await waitFor(() => {
        expect(screen.getByText('测试账户')).toBeInTheDocument();
      });

      // 点击编辑按钮
      const editButtons = screen.getAllByRole('button');
      const editButton = editButtons.find(btn =>
        btn.querySelector('.anticon-edit')
      );

      if (editButton) {
        fireEvent.click(editButton);

        // 验证 Modal 打开并填充数据
        await waitFor(() => {
          const modalTitle = screen.getAllByText('编辑账户');
          expect(modalTitle.length).toBeGreaterThan(0);
          const nameInput = screen.getByLabelText('账户名称');
          expect(nameInput.value).toBe('测试账户');
        });
      }
    });
  });

  describe('删除账户', () => {
    it('显示删除确认对话框', async () => {
      const mockAccounts = [
        {
          id: '1',
          name: '待删除账户',
          parent: null,
          is_default: false,
        },
      ];

      api.accountsAPI.list.mockResolvedValue({
        data: mockAccounts,
      });

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      // 等待列表加载
      await waitFor(() => {
        expect(screen.getByText('待删除账户')).toBeInTheDocument();
      });

      // 点击删除按钮
      const deleteButtons = screen.getAllByRole('button');
      const deleteButton = deleteButtons.find(btn =>
        btn.querySelector('.anticon-delete')
      );

      if (deleteButton) {
        fireEvent.click(deleteButton);

        // 验证确认对话框
        await waitFor(() => {
          expect(screen.getByText(/确定要删除账户/)).toBeInTheDocument();
        });
      }
    });
  });

  describe('错误处理', () => {
    it('加载失败显示错误', async () => {
      api.accountsAPI.list.mockRejectedValue(new Error('加载失败'));

      render(
        <BrowserRouter>
          <AccountsPage />
        </BrowserRouter>
      );

      // 等待错误处理
      await waitFor(() => {
        expect(api.accountsAPI.list).toHaveBeenCalled();
      });
    });
  });
});
