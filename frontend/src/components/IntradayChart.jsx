import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { RefreshCw } from 'lucide-react';

export const IntradayChart = ({ fundId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(''); // Empty = today

  const fetchIntraday = async (date = '') => {
    setLoading(true);
    try {
      const url = date
        ? `/api/fund/${fundId}/intraday?date=${date}`
        : `/api/fund/${fundId}/intraday`;
      const response = await fetch(url, {
        credentials: 'include', // 携带认证 cookie
      });

      if (!response.ok) {
        console.error(`Intraday API error: ${response.status} ${response.statusText}`);
        const errorText = await response.text();
        console.error('Error response:', errorText);
        setData({ snapshots: [] });
        return;
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
      setData({ snapshots: [] });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!fundId) return;
    fetchIntraday(selectedDate);
  }, [fundId, selectedDate]);

  if (loading) return <div className="h-64 flex items-center justify-center text-slate-400">加载分时数据中...</div>;
  if (!data || !data.snapshots || data.snapshots.length === 0) {
    return <div className="h-64 flex items-center justify-center text-slate-400">暂无分时数据（仅持仓基金在交易时间采集）</div>;
  }

  // Calculate estRate for each snapshot
  const chartData = data.snapshots.map(s => ({
    time: s.time,
    estimate: s.estimate,
    estRate: data.prevNav ? ((s.estimate - data.prevNav) / data.prevNav * 100).toFixed(2) : 0
  }));

  // Determine line color based on comparison with previous day NAV
  const lastEstimate = chartData[chartData.length - 1]?.estimate || 0;
  const lineColor = data.prevNav && lastEstimate >= data.prevNav
    ? '#ef4444'  // Red: above previous day NAV (Chinese market convention)
    : data.prevNav && lastEstimate < data.prevNav
    ? '#22c55e'  // Green: below previous day NAV
    : '#94a3b8'; // Gray: no previous NAV data

  return (
    <div className="w-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm text-slate-600">
          <span>日期: {data.date}</span>
          {data.prevNav && <span className="ml-4">前一日净值: {data.prevNav.toFixed(4)}</span>}
          {data.lastCollectedAt && <span className="ml-4">最后更新: {data.lastCollectedAt}</span>}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            max={new Date().toISOString().split('T')[0]}
            className="px-3 py-1 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={() => fetchIntraday(selectedDate)}
            className="p-2 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            title="刷新"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
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
            />
            <Tooltip
              contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              itemStyle={{ color: '#1e293b', fontSize: '12px', fontWeight: 'bold' }}
              labelStyle={{ color: '#64748b', fontSize: '10px', marginBottom: '4px' }}
              formatter={(value, name) => {
                if (name === 'estimate') return [value, '估值'];
                return [value, name];
              }}
            />
            {data.prevNav && (
              <ReferenceLine
                y={data.prevNav}
                stroke="#94a3b8"
                strokeDasharray="3 3"
                label={{ value: '前日净值', position: 'right', fontSize: 10, fill: '#94a3b8' }}
              />
            )}
            <Line
              type="monotone"
              dataKey="estimate"
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
