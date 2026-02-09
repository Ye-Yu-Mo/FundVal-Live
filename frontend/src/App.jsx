import React, { useState, useEffect } from 'react';
import {
  Search,
  ChevronLeft,
  Wallet,
  LayoutGrid,
  Settings as SettingsIcon,
  Users,
  LogOut,
  UserCog
} from 'lucide-react';
import { FundList } from './pages/FundList';
import { FundDetail } from './pages/FundDetail';
import Account from './pages/Account';
import Settings from './pages/Settings';
import Login from './pages/Login';
import UserManagement from './pages/UserManagement';
import { SubscribeModal } from './components/SubscribeModal';
import { AccountModal } from './components/AccountModal';
import { searchFunds, getFundDetail, getAccountPositions, subscribeFund, getAccounts, getPreferences, updatePreferences } from './services/api';
import { useAuth } from './contexts/AuthContext';
import packageJson from '../../package.json';

const APP_VERSION = packageJson.version;

export default function App() {
  const { currentUser, isMultiUserMode, loading: authLoading, logout } = useAuth();

  // 路由守卫：多用户模式下未登录显示登录页
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  if (isMultiUserMode && !currentUser) {
    return <Login />;
  }

  return <AppContent currentUser={currentUser} isMultiUserMode={isMultiUserMode} isAdmin={currentUser?.is_admin || false} logout={logout} />;
}

function AppContent({ currentUser, isMultiUserMode, isAdmin, logout }) {
  // --- State ---
  const [currentView, setCurrentView] = useState('list'); // 'list' | 'detail' | 'account' | 'settings' | 'users'
  const [currentAccount, setCurrentAccount] = useState(currentUser?.default_account_id || 1);
  const [accounts, setAccounts] = useState([]);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [watchlist, setWatchlist] = useState([]);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);

  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedFund, setSelectedFund] = useState(null);
  const [detailFundId, setDetailFundId] = useState(null);
  const [accountCodes, setAccountCodes] = useState(new Set());

  // Load preferences from backend on mount
  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const prefs = await getPreferences();

        // Parse watchlist
        const watchlistData = JSON.parse(prefs.watchlist || '[]');

        // If backend has no data, try to migrate from localStorage
        if (watchlistData.length === 0) {
          const savedWatchlist = localStorage.getItem('fundval_watchlist');
          if (savedWatchlist) {
            try {
              const parsed = JSON.parse(savedWatchlist);
              const seen = new Set();
              const deduped = parsed.filter(fund => {
                if (seen.has(fund.id)) return false;
                seen.add(fund.id);
                return true;
              });
              setWatchlist(deduped);

              // Migrate to backend
              await updatePreferences({ watchlist: savedWatchlist });
              console.log('Migrated watchlist from localStorage to backend');
            } catch (parseError) {
              console.error('Failed to parse localStorage watchlist', parseError);
            }
          } else {
            setWatchlist([]);
          }
        } else {
          const seen = new Set();
          const deduped = watchlistData.filter(fund => {
            if (seen.has(fund.id)) return false;
            seen.add(fund.id);
            return true;
          });
          setWatchlist(deduped);
        }

        // Set current account
        // 优先级：preferences.currentAccount > currentUser.default_account_id > 1
        if (prefs.currentAccount && prefs.currentAccount !== 1) {
          setCurrentAccount(prefs.currentAccount);
        } else if (currentUser?.default_account_id) {
          setCurrentAccount(currentUser.default_account_id);
        } else {
          // 尝试从 localStorage 迁移
          const savedAccount = localStorage.getItem('fundval_current_account');
          if (savedAccount) {
            const accountId = parseInt(savedAccount);
            setCurrentAccount(accountId);
            await updatePreferences({ currentAccount: accountId });
            console.log('Migrated current account from localStorage to backend');
          } else {
            setCurrentAccount(1);
          }
        }

        setPreferencesLoaded(true);
      } catch (e) {
        console.error('Failed to load preferences from backend', e);
        // Fallback to localStorage if API completely fails
        try {
          const savedWatchlist = localStorage.getItem('fundval_watchlist');
          const savedAccount = localStorage.getItem('fundval_current_account');

          if (savedWatchlist) {
            const parsed = JSON.parse(savedWatchlist);
            const seen = new Set();
            const deduped = parsed.filter(fund => {
              if (seen.has(fund.id)) return false;
              seen.add(fund.id);
              return true;
            });
            setWatchlist(deduped);
          }

          if (savedAccount) {
            setCurrentAccount(parseInt(savedAccount));
          } else if (currentUser?.default_account_id) {
            setCurrentAccount(currentUser.default_account_id);
          }
        } catch (migrationError) {
          console.error('Migration from localStorage failed', migrationError);
        }

        setPreferencesLoaded(true);
      }
    };

    loadPreferences();
  }, [currentUser?.id]); // 依赖 currentUser.id，确保用户切换时重新加载

  // Sync watchlist to backend whenever it changes
  useEffect(() => {
    if (!preferencesLoaded) return;

    const syncWatchlist = async () => {
      try {
        await updatePreferences({ watchlist: JSON.stringify(watchlist) });
      } catch (e) {
        console.error('Failed to sync watchlist to backend', e);
      }
    };

    syncWatchlist();
  }, [watchlist, preferencesLoaded]);

  // Sync current account to backend whenever it changes
  useEffect(() => {
    if (!preferencesLoaded) return;

    const syncAccount = async () => {
      try {
        await updatePreferences({ currentAccount });
      } catch (e) {
        console.error('Failed to sync current account to backend', e);
      }
    };

    syncAccount();
  }, [currentAccount, preferencesLoaded]);

  // Load accounts
  const loadAccounts = async () => {
    const accs = await getAccounts();
    setAccounts(accs);

    // 如果当前账户不在账户列表中，设置为用户的默认账户或第一个账户
    if (accs.length > 0) {
      const accountIds = accs.map(acc => acc.id);
      if (!accountIds.includes(currentAccount) && currentAccount !== 0) {
        // 优先使用用户的默认账户
        const defaultAccountId = currentUser?.default_account_id;
        if (defaultAccountId && accountIds.includes(defaultAccountId)) {
          setCurrentAccount(defaultAccountId);
        } else {
          setCurrentAccount(accs[0].id);
        }
      }
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  // Fetch account codes to prevent duplicates
  const fetchAccountCodes = async () => {
    try {
        const data = await getAccountPositions(currentAccount);
        setAccountCodes(new Set((data.positions || []).map(p => p.code)));
    } catch (e) {
        console.error("Failed to fetch account codes", e);
    }
  };

  useEffect(() => {
    fetchAccountCodes();
  }, [currentView, currentAccount]); // Refresh when switching views or accounts
  
  // --- Data Fetching ---
  
  // Polling for updates
  useEffect(() => {
    if (watchlist.length === 0) return;

    const tick = async () => {
        try {
            const updatedList = await Promise.all(watchlist.map(async (fund) => {
                try {
                    const detail = await getFundDetail(fund.id);
                    return { ...fund, ...detail };
                } catch (e) {
                    console.error(e);
                    return fund;
                }
            }));
            setWatchlist(updatedList); 
        } catch (e) {
             console.error("Polling error", e);
        }
    };

    const interval = setInterval(tick, 15000);
    return () => clearInterval(interval);
  }, [watchlist]); 


  // --- Handlers ---

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery) return;

    setLoading(true);

    try {
        const results = await searchFunds(searchQuery);
        if (results && results.length > 0) {
           const fundMeta = results[0];

           // Fetch initial detail
           try {
             const detail = await getFundDetail(fundMeta.id);
             const newFund = { ...fundMeta, ...detail, trusted: true };

             setWatchlist(prev => {
               // 检查是否已存在
               if (prev.find(f => f.id === newFund.id)) {
                 return prev; // 已存在，不添加
               }
               return [...prev, newFund];
             });
             setSearchQuery('');
           } catch(e) {
             alert(`无法获取基金 ${fundMeta.name} 的详情数据`);
           }
        } else {
            alert('未找到相关基金');
        }
    } catch (err) {
        alert('查询失败，请重试');
    } finally {
        setLoading(false);
    }
  };

  const removeFund = (id) => {
    setWatchlist(prev => prev.filter(f => f.id !== id));
  };

  const notifyPositionChange = (code, type = 'add') => {
      if (type === 'add') {
          // Update local account codes set
          setAccountCodes(prev => {
              const next = new Set(prev);
              next.add(code);
              return next;
          });
      } else if (type === 'remove') {
          setAccountCodes(prev => {
              const next = new Set(prev);
              next.delete(code);
              return next;
          });
      }
  };

  const openSubscribeModal = (fund) => {
    setSelectedFund(fund);
    setModalOpen(true);
  };

  const handleCardClick = async (fundId) => {
    // 检查基金是否在 watchlist 中
    const existingFund = watchlist.find(f => f.id === fundId);

    if (!existingFund) {
      // 如果不在 watchlist，先加载基金详情
      try {
        const detail = await getFundDetail(fundId);
        const newFund = { ...detail, trusted: true };
        // 临时添加到 watchlist，添加前检查避免重复
        setWatchlist(prev => {
          // 再次检查是否已存在（防止竞态条件）
          if (prev.find(f => f.id === newFund.id)) {
            return prev; // 已存在，不添加
          }
          return [...prev, newFund];
        });
        setDetailFundId(fundId);
      } catch (e) {
        alert('无法加载基金详情');
        return;
      }
    } else {
      setDetailFundId(fundId);
    }

    setCurrentView('detail');
    window.scrollTo(0, 0);
  };

  const handleBack = () => {
    setCurrentView('list');
    setDetailFundId(null);
  };

  const handleSubscribeSubmit = async (fund, formData) => {
    try {
        await subscribeFund(fund.id, formData);
        alert(`已更新 ${fund.name} 的订阅设置：\n发送至：${formData.email}\n阈值：涨>${formData.thresholdUp}% 或 跌<${formData.thresholdDown}%`);
        setModalOpen(false);
    } catch (e) {
        alert('订阅设置保存失败，请检查网络或后端配置');
    }
  };

  const [syncLoading, setSyncLoading] = useState(false);

  const handleSyncWatchlist = async (positions) => {
      if (!positions || positions.length === 0) return;
      if (syncLoading) return; // Prevent duplicate clicks

      const existingIds = new Set(watchlist.map(f => f.id));
      const newFunds = positions.filter(p => !existingIds.has(p.code));

      if (newFunds.length === 0) {
          alert('所有持仓已在关注列表中');
          return;
      }

      setSyncLoading(true);
      try {
          const addedFunds = await Promise.all(
              newFunds.map(async (pos) => {
                  try {
                      const detail = await getFundDetail(pos.code);
                      // 确保返回的数据有 id 字段
                      if (!detail.id) {
                          console.error(`Fund ${pos.code} has no id field`, detail);
                          return null;
                      }
                      return { ...detail, trusted: true };
                  } catch (e) {
                      console.error(`Failed to sync ${pos.code}`, e);
                      return null;
                  }
              })
          );

          const validFunds = addedFunds.filter(f => f !== null);

          if (validFunds.length > 0) {
              console.log('Adding funds to watchlist:', validFunds.map(f => ({ id: f.id, name: f.name })));
              setWatchlist(prev => {
                  // 过滤掉已存在的基金，避免重复
                  const existingIds = new Set(prev.map(f => f.id));
                  const newFunds = validFunds.filter(f => !existingIds.has(f.id));

                  if (newFunds.length === 0) {
                      console.log('All funds already in watchlist');
                      return prev;
                  }

                  const updated = [...prev, ...newFunds];
                  console.log('Updated watchlist length:', updated.length);
                  return updated;
              });
              alert(`成功同步 ${validFunds.length} 个基金到关注列表`);
          } else {
              alert('同步失败：无法获取基金详情');
          }
      } catch (e) {
          console.error('Sync error:', e);
          alert('同步失败');
      } finally {
          setSyncLoading(false);
      }
  };

  const currentDetailFund = detailFundId ? watchlist.find(f => f.id === detailFundId) : null;
  const currentDetailIndex = detailFundId ? watchlist.findIndex(f => f.id === detailFundId) : -1;

  // Navigate between funds in detail view
  const navigateFund = (direction) => {
    if (currentDetailIndex === -1) return;

    const newIndex = direction === 'prev' ? currentDetailIndex - 1 : currentDetailIndex + 1;
    if (newIndex >= 0 && newIndex < watchlist.length) {
      handleCardClick(watchlist[newIndex].id);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans selection:bg-blue-100">
      
      {/* 1. Header Area */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            
            {/* Logo / Back Button */}
            <div className="flex items-center gap-2">
              {currentView === 'detail' ? (
                <button 
                  onClick={handleBack}
                  className="mr-2 p-1.5 -ml-2 rounded-full hover:bg-slate-100 text-slate-600 transition-colors"
                >
                  <ChevronLeft className="w-6 h-6" />
                </button>
              ) : (
                <div className="flex gap-2">
                   <button
                      onClick={() => setCurrentView('list')}
                      className={`p-2 rounded-lg transition-colors ${currentView === 'list' ? 'bg-blue-100 text-blue-700' : 'hover:bg-slate-100 text-slate-500'}`}
                   >
                      <LayoutGrid className="w-6 h-6" />
                   </button>
                   <button
                      onClick={() => setCurrentView('account')}
                      className={`p-2 rounded-lg transition-colors ${currentView === 'account' ? 'bg-blue-100 text-blue-700' : 'hover:bg-slate-100 text-slate-500'}`}
                   >
                      <Wallet className="w-6 h-6" />
                   </button>
                   {/* 管理员：显示用户管理按钮 */}
                   {isMultiUserMode && isAdmin && (
                     <button
                        onClick={() => setCurrentView('users')}
                        className={`p-2 rounded-lg transition-colors ${currentView === 'users' ? 'bg-blue-100 text-blue-700' : 'hover:bg-slate-100 text-slate-500'}`}
                        title="用户管理"
                     >
                        <UserCog className="w-6 h-6" />
                     </button>
                   )}
                   <button
                      onClick={() => setCurrentView('settings')}
                      className={`p-2 rounded-lg transition-colors ${currentView === 'settings' ? 'bg-blue-100 text-blue-700' : 'hover:bg-slate-100 text-slate-500'}`}
                   >
                      <SettingsIcon className="w-6 h-6" />
                   </button>
                </div>
              )}

              {/* Account Selector */}
              {currentView === 'account' && accounts.length > 0 && (
                <div className="flex items-center gap-2 ml-4">
                  <select
                    value={currentAccount}
                    onChange={(e) => setCurrentAccount(Number(e.target.value))}
                    className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value={0}>全部账户</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => setAccountModalOpen(true)}
                    className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="管理账户"
                  >
                    <Users className="w-5 h-5" />
                  </button>
                </div>
              )}

              <div>
                <h1 className="text-lg font-bold text-slate-800 leading-tight">
                  {currentView === 'detail' ? '基金详情' : (currentView === 'account' ? '我的账户' : (currentView === 'settings' ? '设置' : 'FundVal Live'))}
                </h1>
                <p className="text-xs text-slate-400">
                  {currentView === 'detail' ? '盘中实时估值分析' : '盘中估值参考工具'}
                </p>
              </div>
            </div>

            {/* Search Bar (Only in List View) */}
            {currentView === 'list' && (
              <form onSubmit={handleSearch} className="relative flex-1 max-w-md">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                  <input
                    type="text"
                    placeholder="输入基金代码 (如: 005827)" 
                    className="w-full pl-10 pr-4 py-2 bg-slate-100 border-none rounded-full text-sm focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all outline-none"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <button 
                    type="submit"
                    disabled={loading || !searchQuery}
                    className="absolute right-1 top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? '查询中...' : '添加'}
                  </button>
                </div>
              </form>
            )}

            {/* User / Status */}
            <div className="hidden md:flex items-center gap-4 text-xs text-slate-500">
              {/* 多用户模式：显示用户信息和登出按钮 */}
              {isMultiUserMode && currentUser && (
                <>
                  <span className="flex items-center gap-1.5 text-slate-700">
                    <Users className="w-4 h-4" />
                    {currentUser.username}
                    {currentUser.is_admin && (
                      <span className="ml-1 px-1.5 py-0.5 bg-indigo-100 text-indigo-700 text-xs rounded">管理员</span>
                    )}
                  </span>
                  <button
                    onClick={logout}
                    className="flex items-center gap-1.5 hover:text-red-600 transition-colors"
                    title="登出"
                  >
                    <LogOut className="w-4 h-4" />
                    登出
                  </button>
                </>
              )}

              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                API 正常
              </span>
              <a
                href="https://github.com/Ye-Yu-Mo/FundVal-Live"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 hover:text-blue-600 transition-colors"
                title="GitHub 仓库"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                </svg>
                GitHub
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* 2. Main Content Area */}
      <main className="max-w-4xl mx-auto px-4 py-6">
        
        {currentView === 'list' && (
          <FundList 
            watchlist={watchlist}
            setWatchlist={setWatchlist}
            onSelectFund={handleCardClick}
            onRemove={removeFund}
            onSubscribe={openSubscribeModal}
          />
        )}

        {currentView === 'account' && (
           <Account
                currentAccount={currentAccount}
                isActive={currentView === 'account'}
                onSelectFund={handleCardClick}
                onPositionChange={notifyPositionChange}
                onSyncWatchlist={handleSyncWatchlist}
                syncLoading={syncLoading}
           />
        )}

        {currentView === 'settings' && (
          <Settings />
        )}

        {currentView === 'users' && (
          <UserManagement />
        )}

        {currentView === 'detail' && (
          <FundDetail
            fund={currentDetailFund}
            onSubscribe={openSubscribeModal}
            accountId={currentAccount}
            onNavigate={navigateFund}
            hasPrev={currentDetailIndex > 0}
            hasNext={currentDetailIndex < watchlist.length - 1}
            currentIndex={currentDetailIndex + 1}
            totalCount={watchlist.length}
          />
        )}
      </main>

      {/* 3. Subscription Modal (Global) */}
      {modalOpen && selectedFund && (
        <SubscribeModal 
            fund={selectedFund} 
            onClose={() => setModalOpen(false)}
            onSubmit={handleSubscribeSubmit}
        />
      )}

      {/* 4. Footer */}
      <footer className="max-w-4xl mx-auto px-4 py-8 text-center text-slate-400 text-xs">
        <p className="mb-2">数据仅供参考，不构成投资建议。</p>
        <p className="mb-3">
          Data Source: AkShare Public API · Status: <span className="text-green-600">Operational</span>
        </p>
        <div className="flex items-center justify-center gap-4 text-slate-500">
          <a
            href="https://github.com/Ye-Yu-Mo/FundVal-Live"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-600 transition-colors flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
            </svg>
            GitHub
          </a>
          <span>·</span>
          <a
            href="https://github.com/Ye-Yu-Mo/FundVal-Live/releases"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-600 transition-colors"
          >
            v{APP_VERSION}
          </a>
          <span>·</span>
          <a
            href="https://github.com/Ye-Yu-Mo/FundVal-Live/blob/main/LICENSE"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-600 transition-colors"
          >
            AGPL-3.0
          </a>
          <span>·</span>
          <a
            href="https://github.com/Ye-Yu-Mo/FundVal-Live/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-blue-600 transition-colors"
          >
            反馈问题
          </a>
        </div>
      </footer>

      {/* Account Management Modal */}
      {accountModalOpen && (
        <AccountModal
          accounts={accounts}
          currentAccount={currentAccount}
          onClose={() => setAccountModalOpen(false)}
          onRefresh={loadAccounts}
          onSwitch={setCurrentAccount}
        />
      )}

    </div>
  );
}