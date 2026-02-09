import React, { useState, useRef } from 'react';
import { Plus, Edit2, Trash2, RefreshCw, ArrowUpDown, ChevronDown, Download, CheckCircle, Clock } from 'lucide-react';
import { getRateColor } from '../components/StatCard';
import { PortfolioChart } from '../components/PortfolioChart';
import { useAccountData } from '../hooks/useAccountData';
import { usePositions, SORT_OPTIONS } from '../hooks/usePositions';
import { PositionModal, AddPositionModal, ReducePositionModal } from '../components/TradeModal';

const Account = ({ currentAccount = 1, onSelectFund, onPositionChange, onSyncWatchlist, syncLoading, isActive }) => {
  // 数据管理
  const { data, loading, error, refetch } = useAccountData(currentAccount, isActive);

  // 持仓操作管理
  const {
    sortOption,
    setSortOption,
    sortPositions,
    submitting,
    navUpdating,
    syncLoading: positionSyncLoading,
    handleUpdatePosition,
    handleDeletePosition,
    handleAddPosition,
    handleReducePosition,
    handleUpdateNav,
    handleSyncWatchlist
  } = usePositions(currentAccount, onPositionChange, onSyncWatchlist, refetch);

  // UI 状态
  const [sortDropdownOpen, setSortDropdownOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('全部');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPos, setEditingPos] = useState(null);
  const [addModalPos, setAddModalPos] = useState(null);
  const [reduceModalPos, setReduceModalPos] = useState(null);

  const sortDropdownRef = useRef(null);

  // 是否为汇总视图
  const isAggregatedView = currentAccount === 0;

  const { summary, positions } = data;
  const displayPositions = positions || [];

  // 分类筛选
  const CATEGORIES = ['全部', '货币类', '偏债类', '偏股类', '商品类', '未分类'];

  const categoryCounts = CATEGORIES.reduce((acc, cat) => {
    acc[cat] = cat === '全部'
      ? displayPositions.length
      : displayPositions.filter(p => p.category === cat).length;
    return acc;
  }, {});

  const filteredPositions = selectedCategory === '全部'
    ? displayPositions
    : displayPositions.filter(p => p.category === selectedCategory);

  const sortedPositions = sortPositions(filteredPositions);

  // Modal 操作
  const handleOpenModal = (pos = null) => {
    setEditingPos(pos);
    setModalOpen(true);
  };

  const handleSubmitPosition = async (formData) => {
    try {
      await handleUpdatePosition(formData);
      setModalOpen(false);
    } catch (e) {
      alert('保存失败');
    }
  };

  const handleSync = () => {
    handleSyncWatchlist(positions);
  };

  const handleSortChange = (option) => {
    setSortOption(option);
    setSortDropdownOpen(false);
  };

  // 点击外部关闭下拉菜单
  React.useEffect(() => {
    const handleClickOutside = (event) => {
      if (sortDropdownRef.current && !sortDropdownRef.current.contains(event.target)) {
        setSortDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="space-y-6">
      {/* Aggregated View Notice */}
      {isAggregatedView && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            <strong>正在查看全部账户的汇总数据</strong> - 相同基金的持仓已自动合并（份额相加，成本加权平均）。汇总视图仅供查看，不支持修改操作。
          </p>
        </div>
      )}

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
            onClick={() => refetch()}
            className="text-sm font-medium text-red-600 hover:text-red-700 underline"
          >
            重试
          </button>
        </div>
      )}

      {/* Portfolio Overview */}
      {loading && !data.positions.length ? (
        <div className="w-full bg-white rounded-2xl p-6 shadow-sm border border-slate-100 animate-pulse">
          <div className="h-8 bg-slate-200 rounded w-1/3 mb-4"></div>
          <div className="h-32 bg-slate-200 rounded mb-4"></div>
          <div className="grid grid-cols-3 gap-4">
            <div className="h-20 bg-slate-200 rounded"></div>
            <div className="h-20 bg-slate-200 rounded"></div>
            <div className="h-20 bg-slate-200 rounded"></div>
          </div>
        </div>
      ) : (
        <div className="w-full">
          <PortfolioChart positions={positions} summary={summary} loading={loading} onRefresh={refetch} />
        </div>
      )}

      {/* Actions */}
      <div className="space-y-4">
        {/* 第一行：标题 + 操作按钮 */}
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-slate-800">
            {isAggregatedView ? '全部账户持仓汇总' : '持仓明细'}
          </h2>
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
              disabled={syncLoading || positionSyncLoading}
              className="flex items-center gap-2 bg-white border border-slate-200 text-slate-600 hover:text-blue-600 hover:border-blue-200 px-4 py-2 rounded-lg transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              title="将持仓基金添加到关注列表"
            >
              <RefreshCw className={`w-4 h-4 ${(syncLoading || positionSyncLoading) ? 'animate-spin' : ''}`} />
              {(syncLoading || positionSyncLoading) ? '同步中...' : '同步关注'}
            </button>
            <button
              onClick={handleUpdateNav}
              disabled={navUpdating}
              className="flex items-center gap-2 bg-white border border-slate-200 text-slate-600 hover:text-green-600 hover:border-green-200 px-4 py-2 rounded-lg transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              title="手动更新所有持仓基金的净值"
            >
              <Download className={`w-4 h-4 ${navUpdating ? 'animate-spin' : ''}`} />
              {navUpdating ? '更新中...' : '更新净值'}
            </button>
            {!isAggregatedView && (
              <button
                onClick={() => handleOpenModal()}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium"
              >
                <Plus className="w-4 h-4" />
                记一笔
              </button>
            )}
          </div>
        </div>

        {/* 第二行：分类筛选器 */}
        <div className="flex gap-1 bg-slate-50 p-1 rounded-lg w-fit">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-white hover:text-blue-600'
              }`}
            >
              {cat} ({categoryCounts[cat]})
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
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
                    <div className="flex items-center justify-end gap-1">
                      <div className="text-slate-500 text-xs" title="昨日净值">{pos.nav.toFixed(4)}</div>
                      {pos.nav_updated_today ? (
                        <CheckCircle className="w-3 h-3 text-green-500" title="当日净值已更新" />
                      ) : (
                        <Clock className="w-3 h-3 text-slate-300" title="当日净值未更新" />
                      )}
                    </div>
                    <div className={`font-medium ${getRateColor(pos.est_rate)}`} title="实时估值">
                        {pos.estimate > 0 ? pos.estimate.toFixed(4) : '--'}
                    </div>
                  </td>

                  {/* Position Column */}
                  <td className="px-4 py-3 text-right font-mono text-slate-600">
                    <div>{pos.shares.toLocaleString()}</div>
                    <div className="text-xs text-slate-400">{pos.cost.toFixed(4)}</div>
                  </td>

                  {/* Accumulated Income */}
                  <td className="px-4 py-3 text-right font-mono">
                    <div className={`font-medium ${getRateColor(pos.accumulated_income)}`}>
                        {pos.accumulated_income > 0 ? '+' : ''}{pos.accumulated_income.toFixed(2)}
                    </div>
                    <div className={`text-xs ${getRateColor(pos.accumulated_return_rate)}`}>
                        {pos.accumulated_return_rate > 0 ? '+' : ''}{pos.accumulated_return_rate.toFixed(2)}%
                    </div>
                  </td>

                  {/* Intraday Income */}
                  <td className="px-4 py-3 text-right font-mono">
                    <div className={`font-medium ${!pos.is_est_valid ? 'text-slate-300' : getRateColor(pos.day_income)}`}>
                        {pos.is_est_valid ? (pos.day_income > 0 ? '+' : '') + pos.day_income.toFixed(2) : '--'}
                    </div>
                    <div className={`text-xs ${!pos.is_est_valid ? 'text-slate-300' : getRateColor(pos.est_rate)}`}>
                        {pos.is_est_valid ? (pos.est_rate > 0 ? '+' : '') + pos.est_rate.toFixed(2) + '%' : '--'}
                    </div>
                  </td>

                  {/* Total Projected */}
                  <td className="px-4 py-3 text-right font-mono">
                     <div className="text-slate-800 font-medium">{pos.est_market_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                     <div className={`text-xs ${getRateColor(pos.total_income)}`}>
                        {pos.total_income > 0 ? '+' : ''}{pos.total_income.toFixed(2)}
                     </div>
                  </td>

                  <td className="px-4 py-3">
                    <div className="flex justify-center gap-2">
                      {!isAggregatedView && (
                        <>
                          <button
                            onClick={() => handleOpenModal(pos)}
                            className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                            title="修改持仓"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeletePosition(pos.code)}
                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                            title="删除"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      {isAggregatedView && (
                        <span className="text-xs text-slate-400">仅查看</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modals */}
      <PositionModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleSubmitPosition}
        editingPos={editingPos}
        submitting={submitting}
        onOpenAdd={setAddModalPos}
        onOpenReduce={setReduceModalPos}
        currentAccount={currentAccount}
      />

      <AddPositionModal
        isOpen={!!addModalPos}
        onClose={() => setAddModalPos(null)}
        onSubmit={handleAddPosition}
        position={addModalPos}
        submitting={submitting}
      />

      <ReducePositionModal
        isOpen={!!reduceModalPos}
        onClose={() => setReduceModalPos(null)}
        onSubmit={handleReducePosition}
        position={reduceModalPos}
        submitting={submitting}
      />
    </div>
  );
};

export default Account;