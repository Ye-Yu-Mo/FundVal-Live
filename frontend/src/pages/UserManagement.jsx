import React, { useState, useEffect } from 'react';
import { Users, Plus, Trash2, AlertCircle, Shield, User as UserIcon } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { getUsers, createUser, deleteUser, getAllowRegistration, setAllowRegistration } from '../api/admin';

export default function UserManagement() {
  const { currentUser, isAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [allowRegistration, setAllowRegistrationState] = useState(false);

  // 权限检查
  if (!isAdmin) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-red-900">权限不足</h3>
            <p className="text-sm text-red-700 mt-1">只有管理员可以访问用户管理页面</p>
          </div>
        </div>
      </div>
    );
  }

  // 加载用户列表
  const loadUsers = async () => {
    const data = await getUsers();
    setUsers(data);
  };

  const loadRegistrationSetting = async () => {
    const data = await getAllowRegistration();
    setAllowRegistrationState(data.allow_registration);
  };

  // 刷新用户列表（带 loading 状态）
  const refreshUsers = async () => {
    try {
      setLoading(true);
      setError('');
      await loadUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      setError('');
      try {
        await Promise.all([
          loadUsers(),
          loadRegistrationSetting()
        ]);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadAll();
  }, []);

  // 切换注册开关
  const handleToggleRegistration = async () => {
    try {
      const newValue = !allowRegistration;
      await setAllowRegistration(newValue);
      setAllowRegistrationState(newValue);
    } catch (err) {
      alert('更新注册设置失败：' + err.message);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <Users className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">用户管理</h1>
              <p className="text-sm text-gray-600">管理系统用户和权限</p>
            </div>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            创建用户
          </button>
        </div>

        {/* 注册开关 */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-900">允许用户注册</h3>
            <p className="text-sm text-gray-600 mt-1">开启后，新用户可以自行注册账户</p>
          </div>
          <button
            onClick={handleToggleRegistration}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              allowRegistration ? 'bg-indigo-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                allowRegistration ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* User List */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">加载中...</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  用户
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  角色
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((user) => (
                <UserRow
                  key={user.id}
                  user={user}
                  currentUserId={currentUser?.id}
                  onDelete={refreshUsers}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            refreshUsers();
          }}
        />
      )}
    </div>
  );
}

// User Row Component
function UserRow({ user, currentUserId, onDelete }) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (user.id === currentUserId) {
      alert('不能删除自己的账户');
      return;
    }

    if (!confirm(`确定要删除用户 "${user.username}" 吗？\n\n此操作将删除该用户的所有数据，且无法恢复。`)) {
      return;
    }

    try {
      setDeleting(true);
      await deleteUser(user.id);
      onDelete();
    } catch (err) {
      alert('删除失败：' + err.message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <tr>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-full ${user.is_admin ? 'bg-indigo-100' : 'bg-gray-100'}`}>
            {user.is_admin ? (
              <Shield className="w-4 h-4 text-indigo-600" />
            ) : (
              <UserIcon className="w-4 h-4 text-gray-600" />
            )}
          </div>
          <div>
            <div className="font-medium text-gray-900">{user.username}</div>
            {user.id === currentUserId && (
              <div className="text-xs text-gray-500">（当前用户）</div>
            )}
          </div>
        </div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        {user.is_admin ? (
          <span className="px-2 py-1 text-xs font-medium bg-indigo-100 text-indigo-700 rounded">
            管理员
          </span>
        ) : (
          <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded">
            普通用户
          </span>
        )}
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right">
        <button
          onClick={handleDelete}
          disabled={deleting || user.id === currentUserId}
          className="inline-flex items-center gap-1 px-3 py-1 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Trash2 className="w-4 h-4" />
          删除
        </button>
      </td>
    </tr>
  );
}

// Create User Modal Component
function CreateUserModal({ onClose, onSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
      await createUser(username, password, isAdmin);
      onSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">创建新用户</h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="请输入用户名"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="请输入密码（至少 6 位）"
              required
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="isAdmin"
              checked={isAdmin}
              onChange={(e) => setIsAdmin(e.target.checked)}
              className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            />
            <label htmlFor="isAdmin" className="text-sm text-gray-700">
              设为管理员
            </label>
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
              className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
