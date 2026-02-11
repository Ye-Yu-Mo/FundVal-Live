import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { RefreshCw } from 'lucide-react';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#6366f1', '#14b8a6'];

const RADIAN = Math.PI / 180;
const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index }) => {
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  if (percent < 0.05) return null; // Hide small labels

  return (
    <text x={x} y={y} fill="white" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" className="text-[10px] font-bold">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

const getRateColor = (rate) => {
  if (rate > 0) return 'text-red-500';
  if (rate < 0) return 'text-green-500';
  return 'text-slate-500';
};

export const PortfolioChart = ({ positions, summary, loading, onRefresh }) => {
  if (!positions || positions.length === 0) return null;

  const dataMap = {};

  positions.forEach(p => {
    let type = p.type || "未知";

    // Map to major categories
    if (type.includes("股票") || type.includes("偏股")) {
      type = "股票型";
    } else if (type.includes("混合")) {
      type = "混合型";
    } else if (type.includes("债")) {
      type = "债券型";
    } else if (type.includes("指数")) {
      type = "指数型";
    } else if (type.includes("QDII")) {
      type = "QDII";
    } else if (type.includes("货币")) {
      type = "货币型";
    } else if (type.includes("FOF")) {
      type = "FOF";
    } else if (type.includes("REITs") || type.includes("Reits")) {
      type = "REITs";
    } else if (!type || type === "未知") {
      type = "其他";
    }

    if (!dataMap[type]) dataMap[type] = 0;
    dataMap[type] += p.market_value || p.est_market_value;
  });

  const data = Object.keys(dataMap).map(key => ({
    name: key,
    value: dataMap[key]
  })).sort((a, b) => b.value - a.value);

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider">资产概览</h3>
        <button
          onClick={onRefresh}
          className="p-2 bg-slate-50 border border-slate-200 rounded-full hover:bg-slate-100 transition-colors text-slate-500 hover:text-blue-600"
          title="刷新数据"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>
      <div className="flex flex-col md:flex-row gap-6">
        {/* 左侧：统计数据（小屏无最小宽度） */}
        <div className="flex flex-col gap-4 min-w-0 md:min-w-[240px]">
          <div className="flex flex-col gap-1">
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">预估总资产</div>
            <div className="text-2xl font-bold text-slate-800">
              ¥{(summary?.total_market_value || 0).toLocaleString()}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">成本总额</div>
            <div className="text-2xl font-bold text-slate-600">
              ¥{(summary?.total_cost || 0).toLocaleString()}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">预估总盈亏</div>
            <div className={`text-2xl font-bold ${getRateColor(summary?.total_income || 0)}`}>
              {(summary?.total_income || 0) > 0 ? '+' : ''}¥{(summary?.total_income || 0).toLocaleString()}
            </div>
            <div className={`text-sm font-medium ${getRateColor(summary?.total_income || 0)}`}>
              {(summary?.total_return_rate || 0) > 0 ? '+' : ''}{(summary?.total_return_rate || 0).toFixed(2)}%
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <div className="text-xs text-slate-500 font-medium uppercase tracking-wider">当日预估盈亏</div>
            <div className={`text-2xl font-bold ${getRateColor(summary?.total_day_income || 0)}`}>
              {(summary?.total_day_income || 0) > 0 ? '+' : ''}¥{(summary?.total_day_income || 0).toLocaleString()}
            </div>
          </div>
        </div>

        {/* 右侧：饼图（小屏保证高度） */}
        <div className="flex-1 min-h-[260px] md:min-h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={renderCustomizedLabel}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                paddingAngle={2}
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ fontSize: '12px' }}/>
              <Tooltip
                formatter={(value) => `¥${value.toLocaleString()}`}
                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
