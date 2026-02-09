import React, { useEffect, useState, useCallback } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

export const IntradayChart = ({ fundId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDate, setSelectedDate] = useState(''); // Empty = today
  const [displayMode, setDisplayMode] = useState('nav'); // 'nav' | 'rate'

  const fetchIntraday = useCallback(async (date = '') => {
    setLoading(true);
    setError(null);
    try {
      const url = date
        ? `/api/fund/${fundId}/intraday?date=${date}`
        : `/api/fund/${fundId}/intraday`;
      const response = await fetch(url, {
        credentials: 'include',
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`Intraday API error: ${response.status} ${response.statusText}`, errorText);
        throw new Error(`API 错误 (${response.status})`);
      }

      const json = await response.json();
      console.log('Intraday data loaded:', {
        date: json.date,
        prevNav: json.prevNav,
        snapshotsCount: json.snapshots?.length || 0,
        lastCollectedAt: json.lastCollectedAt
      });
      setData(json);
    } catch (e) {
      console.error("Failed to load intraday data", e);
      setError(e.message || '加载失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [fundId]);

  useEffect(() => {
    if (!fundId) return;
    fetchIntraday(selectedDate);
  }, [fundId, selectedDate]);

  if (loading) return <div className="h-64 flex items-center justify-center text-slate-400">加载分时数据中...</div>;
  if (error) return <div className="h-64 flex items-center justify-center text-red-400">加载失败: {error}</div>;
  if (!data || !data.snapshots || data.snapshots.length === 0) {
    return <div className="h-64 flex items-center justify-center text-slate-400">暂无分时数据（仅持仓基金在交易时间采集）</div>;
  }

  const chartData = data.snapshots.map(s => ({
    time: s.time,
    estimate: s.estimate,
    estRate: data.prevNav ? parseFloat(((s.estimate - data.prevNav) / data.prevNav * 100).toFixed(2)) : 0
  }));

  const lastEstimate = chartData[chartData.length - 1]?.estimate || 0;
  const lastRate = chartData[chartData.length - 1]?.estRate || 0;

  const lineColor = displayMode === 'nav'
    ? (!data.prevNav ? '#94a3b8' : lastEstimate >= data.prevNav ? '#ef4444' : '#22c55e')
    : (lastRate >= 0 ? '#ef4444' : '#22c55e');

  return (
    <div className="w-full">
      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <div className="text-sm text-slate-600">
          <span>日期: {data.date}</span>
          {data.prevNav && <span className="ml-4">前一日净值: {data.prevNav.toFixed(4)}</span>}
          {data.lastCollectedAt && <span className="ml-4">最后更新: {data.lastCollectedAt}</span>}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1 p-1 bg-slate-100 rounded-lg">
            <button
              onClick={() => setDisplayMode('nav')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                displayMode === 'nav'
                  ? 'bg-white text-slate-700 font-medium shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              净值
            </button>
            <button
              onClick={() => setDisplayMode('rate')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                displayMode === 'rate'
                  ? 'bg-white text-slate-700 font-medium shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              涨跌幅
            </button>
          </div>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            max={new Date().toISOString().split('T')[0]}
            className="px-3 py-1 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              tickLine={false}
              axisLine={false}
              minTickGap={20}
            />
            <YAxis
              domain={['auto', 'auto']}
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              tickLine={false}
              axisLine={false}
              width={50}
              tickFormatter={(value) => displayMode === 'rate' ? `${value}%` : value}
            />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              itemStyle={{ color: '#1e293b', fontSize: '12px', fontWeight: 'bold' }}
              labelStyle={{ color: '#64748b', fontSize: '10px', marginBottom: '4px' }}
              formatter={(value, name, props) => {
                if (displayMode === 'nav' && name === 'estimate') {
                  const rate = props.payload.estRate;
                  return [
                    <span key="estimate">
                      {value} <span style={{ color: '#64748b', fontSize: '10px' }}>({rate}%)</span>
                    </span>,
                    '估值'
                  ];
                }
                if (displayMode === 'rate' && name === 'estRate') {
                  return [`${value}%`, '涨跌幅'];
                }
                return [value, name];
              }}
            />
            {displayMode === 'nav' && data.prevNav ? (
              <ReferenceLine
                y={data.prevNav}
                stroke="#94a3b8"
                strokeDasharray="3 3"
                label={{ value: '前日净值', position: 'right', fontSize: 10, fill: '#94a3b8' }}
              />
            ) : displayMode === 'rate' ? (
              <ReferenceLine
                y={0}
                stroke="#94a3b8"
                strokeDasharray="3 3"
                label={{ value: '0%', position: 'right', fontSize: 10, fill: '#94a3b8' }}
              />
            ) : null}
            <Line
              type="monotone"
              dataKey={displayMode === 'nav' ? 'estimate' : 'estRate'}
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              animationDuration={500}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 text-xs text-slate-500 text-center">
        数据采集频率可在设置中配置 ·  仅在系统开启时运行（交易日 09:35-15:05）
      </div>
    </div>
  );
};
