import React, { useState, useEffect } from 'react';
import { Save, AlertCircle, CheckCircle2, Users, Key } from 'lucide-react';
import { getPrompts, createPrompt, updatePrompt, deletePrompt, exportData, importData } from '../services/api';
import { enableMultiUser } from '../api/admin';
import { changePassword } from '../api/auth';
import { useAuth } from '../contexts/AuthContext';
import { PromptModal } from '../components/PromptModal';
import { ExportModal } from '../components/ExportModal';
import { ImportModal } from '../components/ImportModal';
import { AISettings } from './Settings/AISettings';
import { EmailSettings } from './Settings/EmailSettings';
import { PromptManagement } from './Settings/PromptManagement';
import { DataManagement } from './Settings/DataManagement';

export default function Settings() {
  const { isMultiUserMode, checkAuth } = useAuth();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const [settings, setSettings] = useState({
    OPENAI_API_KEY: '',
    OPENAI_API_BASE: '',
    AI_MODEL_NAME: '',
    SMTP_HOST: '',
    SMTP_PORT: '',
    SMTP_USER: '',
    SMTP_PASSWORD: '',
    EMAIL_FROM: '',
    INTRADAY_COLLECT_INTERVAL: '5'
  });

  const [errors, setErrors] = useState({});

  // AI Prompts state
  const [prompts, setPrompts] = useState([]);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState(null);

  // Import/Export state
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);

  // Multi-user mode state
  const [enableMultiUserModalOpen, setEnableMultiUserModalOpen] = useState(false);

  // Change password state
  const [changePasswordModalOpen, setChangePasswordModalOpen] = useState(false);

  useEffect(() => {
    loadSettings();
    loadPrompts();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/settings');
      if (!response.ok) throw new Error('Failed to load settings');
      const data = await response.json();

      setSettings(data.settings || {});
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    const newErrors = {};

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (settings.SMTP_USER && !emailRegex.test(settings.SMTP_USER)) {
      newErrors.SMTP_USER = '邮箱格式不正确';
    }
    if (settings.EMAIL_FROM && !emailRegex.test(settings.EMAIL_FROM)) {
      newErrors.EMAIL_FROM = '邮箱格式不正确';
    }

    // Port validation
    const port = parseInt(settings.SMTP_PORT);
    if (settings.SMTP_PORT && (isNaN(port) || port < 1 || port > 65535)) {
      newErrors.SMTP_PORT = '端口必须在 1-65535 之间';
    }

    // Interval validation
    const interval = parseInt(settings.INTRADAY_COLLECT_INTERVAL);
    if (settings.INTRADAY_COLLECT_INTERVAL && (isNaN(interval) || interval < 1 || interval > 60)) {
      newErrors.INTRADAY_COLLECT_INTERVAL = '采集间隔必须在 1-60 分钟之间';
    }

    // URL validation
    if (settings.OPENAI_API_BASE) {
      try {
        new URL(settings.OPENAI_API_BASE);
      } catch {
        newErrors.OPENAI_API_BASE = 'URL 格式不正确';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) {
      setMessage({ type: 'error', text: '请修正表单错误' });
      return;
    }

    setSaving(true);
    setMessage({ type: '', text: '' });

    try {
      // 过滤掉掩码字段
      const filteredSettings = Object.fromEntries(
        Object.entries(settings).filter(([key, value]) => value !== '***')
      );

      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: filteredSettings })
      });

      if (!response.ok) {
        const errorData = await response.json();

        // 如果后端返回字段级错误
        if (errorData.detail && errorData.detail.errors) {
          setErrors(errorData.detail.errors);
          setMessage({ type: 'error', text: '请修正表单错误' });
        } else {
          setMessage({ type: 'error', text: '保存失败' });
        }
        return;
      }

      setMessage({ type: 'success', text: '设置已保存' });
    } catch (error) {
      setMessage({ type: 'error', text: '网络错误' });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  // AI Prompts functions
  const loadPrompts = async () => {
    setPromptsLoading(true);
    try {
      const data = await getPrompts();
      setPrompts(data);
    } catch (error) {
      console.error('Load prompts failed', error);
    } finally {
      setPromptsLoading(false);
    }
  };

  const handleCreatePrompt = () => {
    setEditingPrompt(null);
    setPromptModalOpen(true);
  };

  const handleEditPrompt = (prompt) => {
    setEditingPrompt(prompt);
    setPromptModalOpen(true);
  };

  const handleSavePrompt = async (data) => {
    try {
      if (editingPrompt) {
        await updatePrompt(editingPrompt.id, data);
        setMessage({ type: 'success', text: '模板已更新' });
      } else {
        await createPrompt(data);
        setMessage({ type: 'success', text: '模板已创建' });
      }
      await loadPrompts();
    } catch (error) {
      throw error;
    }
  };

  const handleDeletePrompt = async (id) => {
    if (!confirm('确定要删除这个提示词模板吗？')) return;

    try {
      await deletePrompt(id);
      setMessage({ type: 'success', text: '模板已删除' });
      await loadPrompts();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || '删除失败';
      setMessage({ type: 'error', text: errorMsg });
    }
  };

  const handleSetDefault = async (prompt) => {
    try {
      // Pass complete prompt data to satisfy backend validation
      await updatePrompt(prompt.id, {
        name: prompt.name,
        system_prompt: prompt.system_prompt,
        user_prompt: prompt.user_prompt,
        is_default: true
      });
      setMessage({ type: 'success', text: '已设为默认模板' });
      await loadPrompts();
    } catch (error) {
      setMessage({ type: 'error', text: '设置失败' });
    }
  };

  const handleImportSuccess = () => {
    setMessage({ type: 'success', text: '数据导入成功' });
    // 重新加载数据
    loadSettings();
    loadPrompts();
  };

  const handleExport = async (modules) => {
    try {
      await exportData(modules);
    } catch (error) {
      throw error;
    }
  };

  const handleImport = async (data, modules, mode) => {
    try {
      const response = await importData(data, modules, mode);
      handleImportSuccess();
      return response;
    } catch (error) {
      throw error;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">加载设置中...</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">设置</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save className="w-4 h-4" />
          {saving ? '保存中...' : '保存更改'}
        </button>
      </div>

      {message.text && (
        <div className={`flex items-center gap-2 p-4 rounded-lg ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5" />
          ) : (
            <AlertCircle className="w-5 h-5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* AI Configuration */}
      <AISettings settings={settings} errors={errors} onChange={handleChange} />

      {/* Email Configuration */}
      <EmailSettings settings={settings} errors={errors} onChange={handleChange} />

      {/* AI Prompts Management */}
      <PromptManagement
        prompts={prompts}
        loading={promptsLoading}
        onCreatePrompt={handleCreatePrompt}
        onEditPrompt={handleEditPrompt}
        onDeletePrompt={handleDeletePrompt}
        onSetDefault={handleSetDefault}
      />

      {/* Data Import/Export */}
      <DataManagement
        onExport={() => setExportModalOpen(true)}
        onImport={() => setImportModalOpen(true)}
      />

      {/* Account Security - Only show in multi-user mode */}
      {isMultiUserMode && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">账户安全</h2>
          <div className="space-y-4">
            <div className="flex items-start justify-between p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Key className="w-5 h-5 text-blue-600" />
                  <h3 className="font-medium text-gray-900">修改密码</h3>
                </div>
                <p className="text-sm text-gray-600">
                  定期修改密码可以提高账户安全性
                </p>
              </div>
              <button
                onClick={() => setChangePasswordModalOpen(true)}
                className="ml-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
              >
                修改密码
              </button>
            </div>
          </div>
        </div>
      )}

      {/* System Management - Only show in single-user mode */}
      {!isMultiUserMode && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">系统管理</h2>
          <div className="space-y-4">
            <div className="flex items-start justify-between p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Users className="w-5 h-5 text-amber-600" />
                  <h3 className="font-medium text-gray-900">开启多用户模式</h3>
                </div>
                <p className="text-sm text-gray-600 mb-2">
                  当前为单用户模式。开启多用户模式后，您可以：
                </p>
                <ul className="text-sm text-gray-600 list-disc list-inside space-y-1 mb-3">
                  <li>创建多个用户账户</li>
                  <li>为每个用户分配独立的数据和权限</li>
                  <li>设置管理员和普通用户角色</li>
                </ul>
                <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded">
                  <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-800">
                    <strong>警告：</strong>此操作不可逆。开启后无法返回单用户模式。
                  </p>
                </div>
              </div>
              <button
                onClick={() => setEnableMultiUserModalOpen(true)}
                className="ml-4 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors whitespace-nowrap"
              >
                开启多用户模式
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Prompt Modal */}
      <PromptModal
        isOpen={promptModalOpen}
        onClose={() => setPromptModalOpen(false)}
        onSave={handleSavePrompt}
        prompt={editingPrompt}
      />

      {/* Export Modal */}
      <ExportModal
        isOpen={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        onExport={handleExport}
      />

      {/* Import Modal */}
      <ImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImport={handleImport}
      />

      {/* Change Password Modal */}
      <ChangePasswordModal
        isOpen={changePasswordModalOpen}
        onClose={() => setChangePasswordModalOpen(false)}
        onSuccess={() => setMessage({ type: 'success', text: '密码修改成功' })}
      />

      {/* Enable Multi-User Mode Modal */}
      <EnableMultiUserModal
        isOpen={enableMultiUserModalOpen}
        onClose={() => setEnableMultiUserModalOpen(false)}
      />
    </div>
  );
}

// Change Password Modal Component
function ChangePasswordModal({ isOpen, onClose, onSuccess }) {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // 重置状态当 Modal 关闭时
  useEffect(() => {
    if (!isOpen) {
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setError('');
    }
  }, [isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!oldPassword || !newPassword || !confirmPassword) {
      setError('所有字段都不能为空');
      return;
    }

    if (newPassword.length < 6) {
      setError('新密码长度至少为 6 位');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      return;
    }

    if (oldPassword === newPassword) {
      setError('新密码不能与旧密码相同');
      return;
    }

    try {
      setLoading(true);
      await changePassword(oldPassword, newPassword);

      onSuccess();
      onClose();
    } catch (err) {
      setError(err.message || '修改密码失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">修改密码</h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              当前密码
            </label>
            <input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请输入当前密码"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              新密码
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请输入新密码（至少 6 位）"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              确认新密码
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="请再次输入新密码"
              required
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '修改中...' : '确认修改'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Enable Multi-User Mode Modal Component
function EnableMultiUserModal({ isOpen, onClose }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // 重置状态当 Modal 关闭时
  useEffect(() => {
    if (!isOpen) {
      setUsername('');
      setPassword('');
      setError('');
    }
  }, [isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!username || !password) {
      setError('用户名和密码不能为空');
      return;
    }

    if (password.length < 6) {
      setError('密码长度至少为 6 位');
      return;
    }

    try {
      setLoading(true);
      await enableMultiUser(username, password);

      // 成功后直接刷新页面，跳转到登录页
      window.location.reload();
    } catch (err) {
      setError(err.message || '开启多用户模式失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">开启多用户模式</h2>

        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-red-800">
              <p className="font-semibold mb-1">警告：此操作不可逆</p>
              <ul className="list-disc list-inside space-y-1">
                <li>开启后无法返回单用户模式</li>
                <li>所有现有数据将归属于管理员账户</li>
                <li>后续需要登录才能访问系统</li>
              </ul>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              管理员用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="请输入管理员用户名"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              管理员密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="请输入密码（至少 6 位）"
              required
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '开启中...' : '确认开启'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
