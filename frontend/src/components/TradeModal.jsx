import React, { useState, useEffect, useRef } from 'react';
import { X, History, Search } from 'lucide-react';
import { getTransactions, searchFunds } from '../services/api';
import { getDefaultTradeDate, buildTradeTime } from '../utils/date';

/**
 * 新增/修改持仓 Modal
 */
export function PositionModal({ isOpen, onClose, onSubmit, editingPos, submitting, onOpenAdd, onOpenReduce, currentAccount }) {
  const [formData, setFormData] = useState({ code: '', cost: '', shares: '' });
  const [showTransactions, setShowTransactions] = useState(false);
  const [inputMode, setInputMode] = useState('manual'); // 'manual' | 'profit'
  const [profitData, setProfitData] = useState({ invest: '', profit: '', currentNav: '' });
  const [fetchingNav, setFetchingNav] = useState(false);

  // Fund search states
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchTimeoutRef = useRef(null);
  const searchInputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      if (editingPos) {
        setFormData({ code: editingPos.code, cost: editingPos.cost, shares: editingPos.shares });
        setSearchQuery('');
      } else {
        setFormData({ code: '', cost: '', shares: '' });
        setSearchQuery('');
      }
      setShowTransactions(false);
      setInputMode('manual');
      setProfitData({ invest: '', profit: '', currentNav: '' });
      setSearchResults([]);
      setShowSearchResults(false);
    }
  }, [isOpen, editingPos]);

  // Search funds when query changes
  useEffect(() => {
    if (!searchQuery || editingPos) {
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    searchTimeoutRef.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const results = await searchFunds(searchQuery);
        setSearchResults(results);
        setShowSearchResults(true);
      } catch (error) {
        console.error('Search failed:', error);
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery, editingPos]);

  const handleSelectFund = (fund) => {
    setFormData({ ...formData, code: fund.id });
    setSearchQuery(`${fund.id} ${fund.name}`);
    setShowSearchResults(false);
  };

  // Fetch current NAV when code changes in profit mode
  useEffect(() => {
    if (inputMode === 'profit' && formData.code && formData.code.length === 6) {
      fetchCurrentNav(formData.code);
    }
  }, [formData.code, inputMode]);

  const fetchCurrentNav = async (code) => {
    setFetchingNav(true);
    try {
      const response = await fetch(`/api/fund/${code}`);
      if (response.ok) {
        const data = await response.json();
        const nav = data.estimate || data.nav || '';
        setProfitData(prev => ({ ...prev, currentNav: nav }));
      }
    } catch (e) {
      console.error('Failed to fetch NAV', e);
    } finally {
      setFetchingNav(false);
    }
  };

  // Calculate shares and cost from profit data
  const calculateFromProfit = () => {
    const invest = parseFloat(profitData.invest);
    const profit = parseFloat(profitData.profit);
    const nav = parseFloat(profitData.currentNav);

    if (!invest || !nav) return null;

    const currentValue = invest + (profit || 0);
    const shares = currentValue / nav;
    const cost = invest / shares;

    return { shares: shares.toFixed(4), cost: cost.toFixed(4) };
  };

  const calculated = inputMode === 'profit' ? calculateFromProfit() : null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputMode === 'profit' && calculated) {
      onSubmit({ ...formData, shares: calculated.shares, cost: calculated.cost });
    } else {
      onSubmit(formData);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm max-h-[90vh] overflow-hidden animate-in fade-in zoom-in duration-200 flex flex-col">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
          <h3 className="font-bold text-slate-800">
            {editingPos ? '修改持仓' : '新增持仓'}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto flex-1">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">基金代码或名称</label>
              <div className="relative">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={editingPos ? formData.code : searchQuery}
                    onChange={(e) => {
                      if (!editingPos) {
                        setSearchQuery(e.target.value);
                        setFormData({ ...formData, code: '' });
                      }
                    }}
                    disabled={!!editingPos}
                    placeholder="输入代码或名称搜索，如: 005827 或 易方达蓝筹"
                    className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none disabled:opacity-60"
                    required={!!editingPos}
                  />
                </div>
                {showSearchResults && searchResults.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {searchResults.map((fund) => (
                      <button
                        key={fund.id}
                        type="button"
                        onClick={() => handleSelectFund(fund)}
                        className="w-full px-3 py-2 text-left hover:bg-slate-50 border-b border-slate-100 last:border-b-0 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-slate-800 truncate">{fund.name}</div>
                            <div className="text-xs text-slate-500 font-mono">{fund.id}</div>
                          </div>
                          <div className="text-xs text-slate-400 shrink-0">{fund.type}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
                {showSearchResults && searchResults.length === 0 && !searchLoading && searchQuery && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-sm text-slate-500 text-center">
                    未找到匹配的基金
                  </div>
                )}
              </div>
              {!editingPos && formData.code && (
                <div className="mt-1 text-xs text-emerald-600">
                  ✓ 已选择: {formData.code}
                </div>
              )}
            </div>

            {!editingPos && (
              <div className="flex gap-2 p-1 bg-slate-100 rounded-lg">
                <button
                  type="button"
                  onClick={() => setInputMode('manual')}
                  className={`flex-1 px-3 py-1.5 text-xs rounded-md transition-colors ${
                    inputMode === 'manual'
                      ? 'bg-white text-slate-700 font-medium shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  手动输入
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode('profit')}
                  className={`flex-1 px-3 py-1.5 text-xs rounded-md transition-colors ${
                    inputMode === 'profit'
                      ? 'bg-white text-slate-700 font-medium shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  金额+收益
                </button>
              </div>
            )}

            {inputMode === 'manual' ? (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">持有份额</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.shares}
                    onChange={(e) => setFormData({ ...formData, shares: e.target.value })}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">持仓成本(单价)</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={formData.cost}
                    onChange={(e) => setFormData({ ...formData, cost: e.target.value })}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                    required
                  />
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">总投入金额</label>
                    <input
                      type="number"
                      step="0.01"
                      value={profitData.invest}
                      onChange={(e) => setProfitData({ ...profitData, invest: e.target.value })}
                      placeholder="10000"
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">当前收益</label>
                    <input
                      type="number"
                      step="0.01"
                      value={profitData.profit}
                      onChange={(e) => setProfitData({ ...profitData, profit: e.target.value })}
                      placeholder="500 或 -200"
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    当前净值 {fetchingNav && <span className="text-xs text-blue-500">(获取中...)</span>}
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={profitData.currentNav}
                    onChange={(e) => setProfitData({ ...profitData, currentNav: e.target.value })}
                    placeholder="自动获取或手动输入"
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                    required
                  />
                </div>
                {calculated && (
                  <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg text-sm space-y-1">
                    <div className="font-medium text-blue-900">计算结果：</div>
                    <div className="text-slate-700">持有份额: <span className="font-mono font-bold">{calculated.shares}</span></div>
                    <div className="text-slate-700">持仓成本: <span className="font-mono font-bold">{calculated.cost}</span></div>
                  </div>
                )}
              </>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={submitting || (inputMode === 'profit' && !calculated)}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg transition-colors shadow-sm active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? '保存中...' : '保存'}
              </button>
            </div>
          </form>

          {editingPos && (
            <div className="mt-6 pt-4 border-t border-slate-100 space-y-4">
              <div className="flex gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => { onClose(); onOpenAdd && onOpenAdd(editingPos); }}
                  className="flex-1 min-w-0 text-sm py-2 rounded-lg bg-emerald-50 text-emerald-600 hover:bg-emerald-100 font-medium"
                >
                  加仓
                </button>
                <button
                  type="button"
                  onClick={() => { onClose(); onOpenReduce && onOpenReduce(editingPos); }}
                  className="flex-1 min-w-0 text-sm py-2 rounded-lg bg-amber-50 text-amber-600 hover:bg-amber-100 font-medium"
                >
                  减仓
                </button>
              </div>
              <button
                type="button"
                onClick={() => setShowTransactions(!showTransactions)}
                className="w-full text-sm py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-medium flex items-center justify-center gap-1"
              >
                <History className="w-4 h-4" />
                操作记录
              </button>
              {showTransactions && (
                <TransactionsView code={editingPos.code} currentAccount={currentAccount} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * 加仓 Modal
 */
export function AddPositionModal({ isOpen, onClose, onSubmit, position, submitting }) {
  const [amount, setAmount] = useState('');
  const [tradeDate, setTradeDate] = useState(() => getDefaultTradeDate());
  const [tradeCutoff, setTradeCutoff] = useState('before');

  useEffect(() => {
    if (isOpen) {
      setAmount('');
      setTradeDate(getDefaultTradeDate());
      setTradeCutoff('before');
    }
  }, [isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const tradeTime = buildTradeTime(tradeDate, tradeCutoff);
    await onSubmit(position.code, amount, tradeTime);
    onClose();
  };

  if (!isOpen || !position) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
          <h3 className="font-bold text-slate-800">加仓 · {position.name}</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">加仓金额（元）</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">交易日期与时段</label>
            <div className="flex gap-2 items-stretch">
              <input
                type="date"
                value={tradeDate}
                onChange={(e) => setTradeDate(e.target.value)}
                className="flex-1 min-w-0 px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
              />
              <select
                value={tradeCutoff}
                onChange={(e) => setTradeCutoff(e.target.value)}
                className="shrink-0 w-[88px] px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm cursor-pointer"
              >
                <option value="before">三点前</option>
                <option value="after">三点后</option>
              </select>
            </div>
          </div>
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? '提交中...' : '确认加仓'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * 减仓 Modal
 */
export function ReducePositionModal({ isOpen, onClose, onSubmit, position, submitting }) {
  const [shares, setShares] = useState('');
  const [tradeDate, setTradeDate] = useState(() => getDefaultTradeDate());
  const [tradeCutoff, setTradeCutoff] = useState('before');

  useEffect(() => {
    if (isOpen) {
      setShares('');
      setTradeDate(getDefaultTradeDate());
      setTradeCutoff('before');
    }
  }, [isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const tradeTime = buildTradeTime(tradeDate, tradeCutoff);
    await onSubmit(position.code, shares, position.shares, tradeTime);
    onClose();
  };

  if (!isOpen || !position) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
          <h3 className="font-bold text-slate-800">减仓 · {position.name}</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">减仓份额</label>
            <input
              type="number"
              step="0.0001"
              min="0.0001"
              max={position.shares ?? undefined}
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder={`当前持仓 ${position.shares != null ? position.shares.toLocaleString() : '--'}`}
              className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">交易日期与时段</label>
            <div className="flex gap-2 items-stretch">
              <input
                type="date"
                value={tradeDate}
                onChange={(e) => setTradeDate(e.target.value)}
                className="flex-1 min-w-0 px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
              />
              <select
                value={tradeCutoff}
                onChange={(e) => setTradeCutoff(e.target.value)}
                className="shrink-0 w-[88px] px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm cursor-pointer"
              >
                <option value="before">三点前</option>
                <option value="after">三点后</option>
              </select>
            </div>
          </div>
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-amber-600 hover:bg-amber-700 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? '提交中...' : '确认减仓'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * 操作记录视图
 */
function TransactionsView({ code, currentAccount }) {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 10;

  useEffect(() => {
    setLoading(true);
    getTransactions(currentAccount, code, 200)
      .then(setTransactions)
      .catch(() => setTransactions([]))
      .finally(() => setLoading(false));
  }, [code, currentAccount]);

  if (loading) {
    return <div className="text-xs text-slate-400 py-4 text-center">加载中...</div>;
  }

  if (transactions.length === 0) {
    return <div className="text-xs text-slate-400 py-4 text-center">暂无加仓/减仓记录</div>;
  }

  const paginatedTransactions = transactions.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="mt-4 rounded-lg border border-slate-100 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-500">日期</th>
              <th className="px-3 py-2 text-left font-medium text-slate-500">类型</th>
              <th className="px-3 py-2 text-left font-medium text-slate-500">状态</th>
              <th className="px-3 py-2 text-right font-medium text-slate-500">金额</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {paginatedTransactions.map((t) => {
              const isPending = !t.applied_at || !t.confirm_nav;
              return (
                <tr key={t.id} className={isPending ? 'bg-amber-50/30' : ''}>
                  <td className="px-3 py-2 text-slate-600">
                    {(t.created_at || '').slice(0, 10)}
                  </td>
                  <td className="px-3 py-2">
                    <span className={t.op_type === 'add' ? 'text-emerald-600' : 'text-amber-600'}>
                      {t.op_type === 'add' ? '加仓' : '减仓'}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {isPending ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700 border border-amber-200">
                        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        待确认
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-emerald-100 text-emerald-700 border border-emerald-200">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        已确认
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    {t.op_type === 'add'
                      ? (t.amount_cny != null ? `¥${Number(t.amount_cny).toFixed(2)}` : '--')
                      : (t.amount_cny != null ? `¥${Number(t.amount_cny).toFixed(2)}` : (t.shares_redeemed != null ? `${Number(t.shares_redeemed).toLocaleString()} 份` : '--'))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-t border-slate-100 text-xs text-slate-500">
        <span>
          第 {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, transactions.length)} 条，共 {transactions.length} 条
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            上一页
          </button>
          <button
            type="button"
            disabled={page * PAGE_SIZE >= transactions.length}
            onClick={() => setPage((p) => p + 1)}
            className="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}
