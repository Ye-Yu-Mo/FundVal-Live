import React, { useEffect, useState } from 'react';
import { User, Bell, BarChart3, ChevronLeft, ChevronRight, TrendingUp } from 'lucide-react';
import { StatCard } from '../components/StatCard';
import { AiAnalysis } from '../components/AiAnalysis';
import { HoldingsTable } from '../components/HoldingsTable';
import { HistoryChart } from '../components/HistoryChart';
import { IntradayChart } from '../components/IntradayChart';
import { IndicatorsCard } from '../components/IndicatorsCard';

export const FundDetail = ({ fund, onSubscribe, accountId, onNavigate, hasPrev, hasNext, currentIndex, totalCount }) => {
  const [chartType, setChartType] = useState('history'); // 'history' | 'intraday'
  const [showBacktest, setShowBacktest] = useState(false);
  const [backtestData, setBacktestData] = useState(null);
  const [backtestLoading, setBacktestLoading] = useState(false);

  const handleBacktest = async () => {
    if (backtestLoading) return;

    setBacktestLoading(true);
    try {
      const response = await fetch(`/api/fund/${fund.id}/backtest?days=20`);
      if (response.ok) {
        const data = await response.json();
        setBacktestData(data);
        setShowBacktest(true);
      } else {
        alert('回测失败，请稍后重试');
      }
    } catch (error) {
      console.error('Backtest error:', error);
      alert('回测失败，请稍后重试');
    } finally {
      setBacktestLoading(false);
    }
  };

  if (!fund) return null;

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">

      {/* 1. Detail Header Card */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
        {/* Navigation arrows */}
        {onNavigate && totalCount > 1 && (
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-slate-100">
            <button
              onClick={() => onNavigate('prev')}
              disabled={!hasPrev}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-100 text-slate-600"
              title="上一个基金"
            >
              <ChevronLeft className="w-4 h-4" />
              上一个
            </button>
            <span className="text-xs text-slate-400">
              {currentIndex} / {totalCount}
            </span>
            <button
              onClick={() => onNavigate('next')}
              disabled={!hasNext}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-100 text-slate-600"
              title="下一个基金"
            >
              下一个
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="flex flex-col md:flex-row justify-between md:items-start gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-bold">{fund.type || '基金'}</span>
              <span className="text-slate-400 text-xs font-mono">{fund.id}</span>
            </div>
            <h2 className="text-2xl font-bold text-slate-800">{fund.name}</h2>
            <div className="flex items-center gap-4 mt-2 text-sm text-slate-500">
              <span className="flex items-center gap-1"><User className="w-4 h-4" /> 基金经理: {fund.manager || '--'}</span>
            </div>
          </div>
          <div className="text-right hidden md:block">
            <p className="text-xs text-slate-400 mb-1">更新时间</p>
            <p className="font-mono text-slate-600">{fund.time}</p>
            {fund.source === 'ml_estimate' && (
              <div className="mt-2 flex flex-col items-end gap-2">
                <span className="inline-block px-2 py-1 bg-purple-50 text-purple-600 rounded text-xs font-medium">
                  算法估值
                </span>
                <p className="text-xs text-slate-400 italic">
                  {fund.method === 'weighted_ma' && '加权移动平均'}
                  {fund.method === 'simple_ma' && '简单移动平均'}
                </p>
                <button
                  onClick={handleBacktest}
                  disabled={backtestLoading}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-purple-600 hover:bg-purple-50 rounded transition-colors disabled:opacity-50"
                  title="查看回测准确率"
                >
                  <TrendingUp className="w-3 h-3" />
                  {backtestLoading ? '计算中...' : '准确率'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Main Stats */}
        <div className="grid grid-cols-3 gap-6 py-6 border-t border-b border-slate-50">
          <div className="col-span-3 md:col-span-1">
            <StatCard
              label="实时估算涨跌"
              value={fund.estRate}
              isRate={true}
              highlight={true}
              large={true}
            />
          </div>
          <StatCard label="实时估值" value={fund.estimate ? fund.estimate.toFixed(4) : '--'} large={true} />
          <StatCard label="昨日单位净值" value={fund.nav ? fund.nav.toFixed(4) : '--'} large={true} />
        </div>

        {/* Chart Section with Tab Switcher */}
        <div className="py-4 border-b border-slate-50 mb-4">
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setChartType('history')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                chartType === 'history'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              历史走势
            </button>
            <button
              onClick={() => setChartType('intraday')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                chartType === 'intraday'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              今日分时
            </button>
          </div>

          {chartType === 'history' ? (
            <HistoryChart fundId={fund.id} accountId={accountId} />
          ) : (
            <IntradayChart fundId={fund.id} />
          )}
        </div>

        {/* Actions */}
        <div className="mt-6 flex gap-3">
          <button
            onClick={(e) => onSubscribe(fund)}
            className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-medium transition-colors flex justify-center items-center gap-2"
          >
            <Bell className="w-4 h-4" /> 订阅提醒
          </button>
        </div>
      </div>

      {/* 2. New Indicators Card */}
      <IndicatorsCard indicators={fund.indicators} />

      {/* 3. AI Analysis Section */}
      <AiAnalysis fund={fund} />

      {/* 4. Holdings */}
      <HoldingsTable holdings={fund.holdings} />

      {/* Backtest Modal */}
      {showBacktest && backtestData && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => setShowBacktest(false)}
        >
          <div
            className="bg-white rounded-xl shadow-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h3 className="font-bold text-lg text-slate-800">算法回测结果</h3>
              <button
                onClick={() => setShowBacktest(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="text-sm text-slate-600 mb-1">平均误差率</div>
                <div className="text-3xl font-bold text-purple-600">
                  {backtestData.avg_error_rate}%
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  基于近 {backtestData.test_days} 天历史数据回测
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="text-xs text-slate-500 mb-1">方向准确率</div>
                  <div className="text-xl font-bold text-slate-700">
                    {backtestData.direction_accuracy}%
                  </div>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="text-xs text-slate-500 mb-1">中位数误差</div>
                  <div className="text-xl font-bold text-slate-700">
                    {backtestData.median_error_rate}%
                  </div>
                </div>
              </div>

              <div className="border-t border-slate-200 pt-3">
                <div className="text-sm font-medium text-slate-700 mb-2">误差分布</div>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600">误差 ≤ 0.5%</span>
                    <span className="font-medium text-emerald-600">
                      {backtestData.error_distribution.within_0_5}%
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600">误差 ≤ 1.0%</span>
                    <span className="font-medium text-emerald-600">
                      {backtestData.error_distribution.within_1_0}%
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600">误差 ≤ 2.0%</span>
                    <span className="font-medium text-blue-600">
                      {backtestData.error_distribution.within_2_0}%
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-600">误差 &gt; 2.0%</span>
                    <span className="font-medium text-orange-600">
                      {backtestData.error_distribution.above_2_0}%
                    </span>
                  </div>
                </div>
              </div>

              <div className="text-xs text-slate-400 text-center pt-2">
                算法使用加权移动平均，近期数据权重更大
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
