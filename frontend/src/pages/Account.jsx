import React, { useState, useEffect, useRef } from 'react';
import { Plus, X, Edit2, Trash2, RefreshCw, ArrowUpDown, ChevronDown, TrendingUp, TrendingDown, History } from 'lucide-react';
import { getAccountPositions, updatePosition, deletePosition, addPositionTrade, reducePositionTrade, getTransactions } from '../services/api';
import { getRateColor } from '../components/StatCard';
import { PortfolioChart } from '../components/PortfolioChart';

function formatDateYMD(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function getDefaultTradeDate() {
  return formatDateYMD(new Date());
}
function buildTradeTime(dateStr, cutoff) {
  const time = cutoff === 'after' ? '15:01:00' : '14:59:00';
  return `${dateStr}T${time}`;
}

const SORT_OPTIONS = [
  { label: '预估总值（从高到低）', key: 'est_market_value', direction: 'desc' },
  { label: '预估总值（从低到高）', key: 'est_market_value', direction: 'asc' },
  { label: '持有收益（从高到低）', key: 'accumulated_income', direction: 'desc' },
  { label: '持有收益（从低到高）', key: 'accumulated_income', direction: 'asc' },
  { label: '持有收益率（从高到低）', key: 'accumulated_return_rate', direction: 'desc' },
  { label: '持有收益率（从低到高）', key: 'accumulated_return_rate', direction: 'asc' },
  { label: '当日预估（从高到低）', key: 'day_income', direction: 'desc' },
  { label: '当日预估（从低到高）', key: 'day_income', direction: 'asc' },
  { label: '当日预估收益率（从高到低）', key: 'est_rate', direction: 'desc' },
  { label: '当日预估收益率（从低到高）', key: 'est_rate', direction: 'asc' },
];

const Account = ({ onSelectFund, onPositionChange, onSyncWatchlist, syncLoading }) => {
  const [data, setData] = useState({ summary: {}, positions: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPos, setEditingPos] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [sortDropdownOpen, setSortDropdownOpen] = useState(false);
  const [sortOption, setSortOption] = useState(() => {
    // 从 localStorage 读取上次的排序选项
    const saved = localStorage.getItem('account_sort_option');
    return saved ? JSON.parse(saved) : SORT_OPTIONS[0];
  });

  const sortDropdownRef = useRef(null);

  // Form State
  const [formData, setFormData] = useState({ code: '', cost: '', shares: '' });

  // 加仓/减仓
  const [addModalPos, setAddModalPos] = useState(null);
  const [addAmount, setAddAmount] = useState('');
  const [addTradeDate, setAddTradeDate] = useState(() => getDefaultTradeDate());
  const [addTradeCutoff, setAddTradeCutoff] = useState('before');
  const [addSubmitting, setAddSubmitting] = useState(false);
  const [reduceModalPos, setReduceModalPos] = useState(null);
  const [reduceShares, setReduceShares] = useState('');
  const [reduceTradeDate, setReduceTradeDate] = useState(() => getDefaultTradeDate());
  const [reduceTradeCutoff, setReduceTradeCutoff] = useState('before');
  const [reduceSubmitting, setReduceSubmitting] = useState(false);

  // 修改弹窗内该基金的操作记录
  const [modalTransactions, setModalTransactions] = useState([]);
  const [modalTransactionsLoading, setModalTransactionsLoading] = useState(false);
  const [modalTransactionsOpen, setModalTransactionsOpen] = useState(false);
  const [modalTransactionsPage, setModalTransactionsPage] = useState(1);
  const MODAL_TX_PAGE_SIZE = 10;

  const fetchData = async (retryCount = 0) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAccountPositions();
      setData(res);
    } catch (e) {
      console.error(e);

      // Retry logic: retry up to 2 times with exponential backoff
      if (retryCount < 2) {
        const delay = Math.pow(2, retryCount) * 1000; // 1s, 2s
        console.log(`Retrying in ${delay}ms... (attempt ${retryCount + 1}/2)`);
        setTimeout(() => fetchData(retryCount + 1), delay);
      } else {
        setError('加载账户数据失败，请检查后端服务是否启动');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Delay initial fetch to give backend time to start
    const timer = setTimeout(() => fetchData(), 500);
    return () => clearTimeout(timer);
  }, []);

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (sortDropdownRef.current && !sortDropdownRef.current.contains(event.target)) {
        setSortDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleOpenModal = (pos = null) => {
    if (pos) {
      setEditingPos(pos);
      setFormData({ code: pos.code, cost: pos.cost, shares: pos.shares });
    } else {
      setEditingPos(null);
      setFormData({ code: '', cost: '', shares: '' });
    }
    setModalOpen(true);
  };

  const handleSync = () => {
    const { positions } = data;
    if (!positions || positions.length === 0) return;
    if (confirm(`确定将 ${positions.length} 个持仓基金同步到关注列表吗？`)) {
        onSyncWatchlist && onSyncWatchlist(positions);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.code || !formData.cost || !formData.shares) return;
    if (submitting) return; // Prevent duplicate submission

    setSubmitting(true);
    try {
      await updatePosition({
        code: formData.code,
        cost: parseFloat(formData.cost),
        shares: parseFloat(formData.shares)
      });
      setModalOpen(false);
      onPositionChange && onPositionChange(formData.code, 'add');
      fetchData();
    } catch (e) {
      alert('保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (code) => {
    if (!confirm(`确定删除 ${code} 吗？`)) return;
    try {
      await deletePosition(code);
      onPositionChange && onPositionChange(code, 'remove');
      fetchData();
    } catch (e) {
      alert('删除失败');
    }
  };

  const handleSortChange = (option) => {
    setSortOption(option);
    localStorage.setItem('account_sort_option', JSON.stringify(option));
    setSortDropdownOpen(false);
  };

  const handleOpenAddModal = (pos) => {
    setAddModalPos(pos);
    setAddAmount('');
    setAddTradeDate(getDefaultTradeDate());
    setAddTradeCutoff('before');
  };
  const handleOpenReduceModal = (pos) => {
    setReduceModalPos(pos);
    setReduceShares('');
    setReduceTradeDate(getDefaultTradeDate());
    setReduceTradeCutoff('before');
  };

  const handleAddSubmit = async (e) => {
    e.preventDefault();
    if (!addModalPos || !addAmount || parseFloat(addAmount) <= 0) return;
    if (addSubmitting) return;
    setAddSubmitting(true);
    try {
      const payload = { amount: parseFloat(addAmount), trade_time: buildTradeTime(addTradeDate, addTradeCutoff) };
      const result = await addPositionTrade(addModalPos.code, payload);
      setAddModalPos(null);
      if (result.pending) alert(result.message || '已记录，待净值公布后自动更新持仓');
      else alert(`加仓成功，确认净值 ${result.confirm_nav}，获得份额 ${result.shares_added}`);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || '加仓失败');
    } finally {
      setAddSubmitting(false);
    }
  };

  const handleReduceSubmit = async (e) => {
    e.preventDefault();
    if (!reduceModalPos || !reduceShares || parseFloat(reduceShares) <= 0) return;
    if (reduceSubmitting) return;
    const sh = parseFloat(reduceShares);
    if (reduceModalPos.shares != null && sh > reduceModalPos.shares) {
      alert(`减仓份额不能大于当前持仓 ${reduceModalPos.shares}`);
      return;
    }
    setReduceSubmitting(true);
    try {
      const payload = { shares: sh, trade_time: buildTradeTime(reduceTradeDate, reduceTradeCutoff) };
      const result = await reducePositionTrade(reduceModalPos.code, payload);
      setReduceModalPos(null);
      if (result.pending) alert(result.message || '已记录，待净值公布后自动更新持仓');
      else alert(`减仓成功，确认净值 ${result.confirm_nav}，到账金额约 ${result.amount_cny}`);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || '减仓失败');
    } finally {
      setReduceSubmitting(false);
    }
  };

  // 打开修改弹窗时拉取该基金操作记录
  useEffect(() => {
    if (!modalOpen || !editingPos) return;
    setModalTransactionsLoading(true);
    setModalTransactionsOpen(false);
    setModalTransactionsPage(1);
    getTransactions(editingPos.code, 200)
      .then(setModalTransactions)
      .catch(() => setModalTransactions([]))
      .finally(() => setModalTransactionsLoading(false));
  }, [modalOpen, editingPos?.code]);

  const { summary, positions } = data;

  // 排序逻辑
  const sortedPositions = [...positions].sort((a, b) => {
    const aValue = a[sortOption.key] || 0;
    const bValue = b[sortOption.key] || 0;
    return sortOption.direction === 'desc' ? bValue - aValue : aValue - bValue;
  });

  return (
    <div className="space-y-6">
      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-red-600">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium text-red-800">{error}</p>
            </div>
          </div>
          <button
            onClick={() => fetchData()}
            className="text-sm font-medium text-red-600 hover:text-red-700 underline"
          >
            重试
          </button>
        </div>
      )}

      {/* 1. Portfolio Overview with Summary */}
      <div className="w-full">
        <PortfolioChart positions={positions} summary={summary} loading={loading} onRefresh={fetchData} />
      </div>

      {/* 2. Actions */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-slate-800">持仓明细</h2>
        <div className="flex gap-2">
            {/* 排序下拉菜单 */}
            <div className="relative" ref={sortDropdownRef}>
              <button
                onClick={() => setSortDropdownOpen(!sortDropdownOpen)}
                className="flex items-center gap-2 bg-white border border-slate-200 text-slate-600 hover:text-blue-600 hover:border-blue-200 px-4 py-2 rounded-lg transition-colors text-sm font-medium"
              >
                <ArrowUpDown className="w-4 h-4" />
                排序
                <ChevronDown className={`w-3 h-3 transition-transform ${sortDropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {sortDropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white border border-slate-200 rounded-lg shadow-lg z-50 py-1">
                  {SORT_OPTIONS.map((option, index) => (
                    <button
                      key={index}
                      onClick={() => handleSortChange(option)}
                      className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                        sortOption.label === option.label
                          ? 'bg-blue-50 text-blue-600 font-medium'
                          : 'text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              onClick={handleSync}
              disabled={syncLoading}
              className="flex items-center gap-2 bg-white border border-slate-200 text-slate-600 hover:text-blue-600 hover:border-blue-200 px-4 py-2 rounded-lg transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              title="将持仓基金添加到关注列表"
            >
              <RefreshCw className={`w-4 h-4 ${syncLoading ? 'animate-spin' : ''}`} />
              {syncLoading ? '同步中...' : '同步关注'}
            </button>
            <button
              onClick={() => handleOpenModal()}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              记一笔
            </button>
        </div>
      </div>

      {/* 3. Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        <div>
          <table className="w-full text-base text-left border-collapse">
            <thead className="bg-slate-50 text-slate-500 font-medium text-xs uppercase tracking-wider sticky top-[73px] z-30 shadow-sm">
              <tr>
                <th className="px-4 py-3 text-left border-b border-slate-100 bg-slate-50 rounded-tl-xl">基金</th>
                <th className="px-4 py-3 text-right border-b border-slate-100 bg-slate-50">净值 | 估值</th>
                <th className="px-4 py-3 text-right border-b border-slate-100 bg-slate-50">份额 | 成本</th>
                <th className="px-4 py-3 text-right border-b border-slate-100 bg-slate-50">持有收益</th>
                <th className="px-4 py-3 text-right border-b border-slate-100 bg-slate-50">当日预估</th>
                <th className="px-4 py-3 text-right border-b border-slate-100 bg-slate-50">预估总值</th>
                <th className="px-4 py-3 text-center border-b border-slate-100 bg-slate-50 rounded-tr-xl">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-base">
              {sortedPositions.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-4 py-8 text-center text-slate-400">
                    暂无持仓，快去记一笔吧
                  </td>
                </tr>
              ) : sortedPositions.map((pos) => (
                <tr key={pos.code} className="hover:bg-slate-50 transition-colors">
                  <td 
                    className="px-4 py-3 cursor-pointer group max-w-[180px]"
                    onClick={() => onSelectFund && onSelectFund(pos.code)}
                  >
                    <div className="font-medium text-slate-800 group-hover:text-blue-600 transition-colors truncate" title={pos.name}>{pos.name}</div>
                    <div className="text-xs text-slate-400 font-mono">{pos.code}</div>
                  </td>
                  
                  {/* Price Column */}
                  <td className="px-4 py-3 text-right font-mono">
                    <div className="text-slate-500 text-xs" title="昨日净值">{pos.nav.toFixed(4)}</div>
                    <div className={`font-medium ${getRateColor(pos.est_rate)}`} title="实时估值">
                        {pos.estimate > 0 ? pos.estimate.toFixed(4) : '--'}
                    </div>
                  </td>

                  {/* Position Column */}
                  <td className="px-4 py-3 text-right font-mono text-slate-600">
                    <div>{pos.shares.toLocaleString()}</div>
                    <div className="text-xs text-slate-400">{pos.cost.toFixed(4)}</div>
                  </td>

                  {/* Accumulated Income (Historical) */}
                  <td className="px-4 py-3 text-right font-mono">
                    <div className={`font-medium ${getRateColor(pos.accumulated_income)}`}>
                        {pos.accumulated_income > 0 ? '+' : ''}{pos.accumulated_income}
                    </div>
                    <div className={`text-xs ${getRateColor(pos.accumulated_return_rate)}`}>
                        {pos.accumulated_return_rate > 0 ? '+' : ''}{pos.accumulated_return_rate}%
                    </div>
                  </td>

                  {/* Intraday Income (Real-time) */}
                  <td className="px-4 py-3 text-right font-mono">
                    <div className={`font-medium ${!pos.is_est_valid ? 'text-slate-300' : getRateColor(pos.day_income)}`}>
                        {pos.is_est_valid ? (pos.day_income > 0 ? '+' : '') + pos.day_income : '--'}
                    </div>
                    <div className={`text-xs ${!pos.is_est_valid ? 'text-slate-300' : getRateColor(pos.est_rate)}`}>
                        {pos.is_est_valid ? (pos.est_rate > 0 ? '+' : '') + pos.est_rate + '%' : '--'}
                    </div>
                  </td>

                  {/* Total Projected */}
                  <td className="px-4 py-3 text-right font-mono">
                     <div className="text-slate-800 font-medium">{pos.est_market_value.toLocaleString()}</div>
                     <div className={`text-xs ${getRateColor(pos.total_income)}`}>
                        {pos.total_income > 0 ? '+' : ''}{pos.total_income}
                     </div>
                  </td>

                  <td className="px-4 py-3">
                    <div className="flex justify-center gap-2">
                      <button 
                        onClick={() => handleOpenModal(pos)}
                        className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                        title="修改持仓"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={() => handleDelete(pos.code)}
                        className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal：新增/修改持仓 */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm max-h-[90vh] overflow-hidden animate-in fade-in zoom-in duration-200 flex flex-col">
            <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 shrink-0">
              <h3 className="font-bold text-slate-800">
                {editingPos ? '修改持仓' : '新增持仓'}
              </h3>
              <button 
                onClick={() => setModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">基金代码</label>
                  <input 
                    type="text" 
                    value={formData.code}
                    onChange={(e) => setFormData({...formData, code: e.target.value})}
                    disabled={!!editingPos}
                    placeholder="如: 005827"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono disabled:opacity-60"
                    required
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">持有份额</label>
                    <input 
                      type="number" 
                      step="0.01"
                      value={formData.shares}
                      onChange={(e) => setFormData({...formData, shares: e.target.value})}
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
                      onChange={(e) => setFormData({...formData, cost: e.target.value})}
                      className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                      required
                    />
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg transition-colors shadow-sm active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitting ? '保存中...' : '保存'}
                  </button>
                </div>
              </form>

              {/* 仅修改时显示：加仓、减仓、操作记录 */}
              {editingPos && (
                <div className="mt-6 pt-4 border-t border-slate-100 space-y-4">
                  <div className="flex gap-2 flex-wrap">
                    <button
                      type="button"
                      onClick={() => { setModalOpen(false); setAddModalPos(editingPos); }}
                      className="flex-1 min-w-0 text-sm py-2 rounded-lg bg-emerald-50 text-emerald-600 hover:bg-emerald-100 font-medium"
                    >
                      加仓
                    </button>
                    <button
                      type="button"
                      onClick={() => { setModalOpen(false); setReduceModalPos(editingPos); }}
                      className="flex-1 min-w-0 text-sm py-2 rounded-lg bg-amber-50 text-amber-600 hover:bg-amber-100 font-medium"
                    >
                      减仓
                    </button>
                    <button
                      type="button"
                      onClick={() => setModalTransactionsOpen((v) => !v)}
                      className="flex-1 min-w-0 text-sm py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-medium flex items-center justify-center gap-1"
                    >
                      <History className="w-4 h-4" />
                      操作记录
                      {modalTransactions.length > 0 && (
                        <span className="text-slate-400">({modalTransactions.length})</span>
                      )}
                    </button>
                  </div>
                  {modalTransactionsOpen && (
                    <div className="rounded-lg border border-slate-100 overflow-hidden">
                      {modalTransactionsLoading ? (
                        <div className="text-xs text-slate-400 py-4 text-center">加载中...</div>
                      ) : modalTransactions.length === 0 ? (
                        <div className="text-xs text-slate-400 py-4 text-center">暂无加仓/减仓记录</div>
                      ) : (
                        <>
                          <div className="overflow-x-auto">
                            <table className="w-full border-collapse text-xs">
                              <thead className="bg-slate-50">
                                <tr>
                                  <th className="px-3 py-2 text-left font-medium text-slate-500">日期</th>
                                  <th className="px-3 py-2 text-left font-medium text-slate-500">类型</th>
                                  <th className="px-3 py-2 text-right font-medium text-slate-500">金额</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-50">
                                {modalTransactions
                                  .slice((modalTransactionsPage - 1) * MODAL_TX_PAGE_SIZE, modalTransactionsPage * MODAL_TX_PAGE_SIZE)
                                  .map((t) => (
                                    <tr key={t.id}>
                                      <td className="px-3 py-2 text-slate-600">
                                        {(t.created_at || '').slice(0, 10)}
                                      </td>
                                      <td className="px-3 py-2">
                                        <span className={t.op_type === 'add' ? 'text-emerald-600' : 'text-amber-600'}>
                                          {t.op_type === 'add' ? '加仓' : '减仓'}
                                        </span>
                                      </td>
                                      <td className="px-3 py-2 text-right font-mono">
                                        {t.op_type === 'add'
                                          ? (t.amount_cny != null ? `¥${Number(t.amount_cny).toFixed(2)}` : '--')
                                          : (t.amount_cny != null ? `¥${Number(t.amount_cny).toFixed(2)}` : (t.shares_redeemed != null ? `${Number(t.shares_redeemed).toLocaleString()} 份` : '--'))}
                                      </td>
                                    </tr>
                                  ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-t border-slate-100 text-xs text-slate-500">
                            <span>
                              第 {(modalTransactionsPage - 1) * MODAL_TX_PAGE_SIZE + 1}-{Math.min(modalTransactionsPage * MODAL_TX_PAGE_SIZE, modalTransactions.length)} 条，共 {modalTransactions.length} 条
                            </span>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                disabled={modalTransactionsPage <= 1}
                                onClick={() => setModalTransactionsPage((p) => p - 1)}
                                className="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
                              >
                                上一页
                              </button>
                              <button
                                type="button"
                                disabled={modalTransactionsPage * MODAL_TX_PAGE_SIZE >= modalTransactions.length}
                                onClick={() => setModalTransactionsPage((p) => p + 1)}
                                className="px-2 py-1 rounded hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
                              >
                                下一页
                              </button>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 加仓 Modal */}
      {addModalPos && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h3 className="font-bold text-slate-800">加仓 · {addModalPos.name}</h3>
              <button type="button" onClick={() => setAddModalPos(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleAddSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">加仓金额（元）</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={addAmount}
                  onChange={(e) => setAddAmount(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">交易日期与时段</label>
                <div className="flex gap-2 items-stretch">
                  <input
                    type="date"
                    value={addTradeDate}
                    onChange={(e) => setAddTradeDate(e.target.value)}
                    className="flex-1 min-w-0 px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm appearance-none [&::-webkit-calendar-picker-indicator]:opacity-100 [&::-webkit-calendar-picker-indicator]:cursor-pointer"
                  />
                  <select
                    value={addTradeCutoff}
                    onChange={(e) => setAddTradeCutoff(e.target.value)}
                    className="shrink-0 w-[88px] px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm appearance-none cursor-pointer bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%236b7280%22%20d%3D%22M6%208L1%203h10z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[right_0.5rem_center] bg-no-repeat pr-7"
                  >
                    <option value="before">三点前</option>
                    <option value="after">三点后</option>
                  </select>
                </div>
              </div>
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={addSubmitting}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {addSubmitting ? '提交中...' : '确认加仓'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 减仓 Modal */}
      {reduceModalPos && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h3 className="font-bold text-slate-800">减仓 · {reduceModalPos.name}</h3>
              <button type="button" onClick={() => setReduceModalPos(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleReduceSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">减仓份额</label>
                <input
                  type="number"
                  step="0.0001"
                  min="0.0001"
                  max={reduceModalPos.shares ?? undefined}
                  value={reduceShares}
                  onChange={(e) => setReduceShares(e.target.value)}
                  placeholder={`当前持仓 ${reduceModalPos.shares != null ? reduceModalPos.shares.toLocaleString() : '--'}`}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">交易日期与时段</label>
                <div className="flex gap-2 items-stretch">
                  <input
                    type="date"
                    value={reduceTradeDate}
                    onChange={(e) => setReduceTradeDate(e.target.value)}
                    className="flex-1 min-w-0 px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm appearance-none [&::-webkit-calendar-picker-indicator]:opacity-100 [&::-webkit-calendar-picker-indicator]:cursor-pointer"
                  />
                  <select
                    value={reduceTradeCutoff}
                    onChange={(e) => setReduceTradeCutoff(e.target.value)}
                    className="shrink-0 w-[88px] px-3 py-2.5 bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm appearance-none cursor-pointer bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%236b7280%22%20d%3D%22M6%208L1%203h10z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[right_0.5rem_center] bg-no-repeat pr-7"
                  >
                    <option value="before">三点前</option>
                    <option value="after">三点后</option>
                  </select>
                </div>
              </div>
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={reduceSubmitting}
                  className="w-full bg-amber-600 hover:bg-amber-700 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {reduceSubmitting ? '提交中...' : '确认减仓'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};

const SummaryCard = ({ label, value, subValue, isPositive }) => (
  <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
    <div className="text-xs text-slate-500 mb-1">{label}</div>
    <div className={`text-2xl font-mono font-bold ${
      isPositive === undefined ? 'text-slate-900' : 
      isPositive ? 'text-red-500' : 'text-green-500'
    }`}>
      {value}
    </div>
    {subValue && (
      <div className={`text-xs mt-1 font-medium ${
        isPositive ? 'text-red-500' : 'text-green-500'
      }`}>
        {isPositive ? '+' : ''}{subValue}
      </div>
    )}
  </div>
);

export default Account;
