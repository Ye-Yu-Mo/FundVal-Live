import { useState, useEffect } from 'react';
import { Card, Tabs, Radio, Empty, Spin, message, Grid } from 'antd';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { positionsAPI } from '../api';

const { useBreakpoint } = Grid;

const PositionCharts = ({ positions, accountId }) => {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [timeRange, setTimeRange] = useState('30d'); // 30d, 90d, all
  const [historyData, setHistoryData] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);

  // 计算市值：holding_share * latest_nav
  const calculateMarketValue = (position) => {
    const share = parseFloat(position.holding_share || 0);
    const nav = parseFloat(position.fund?.latest_nav || 0);
    return share * nav;
  };

  // 计算账户总市值和总成本
  const totalValue = positions.reduce((sum, p) => sum + calculateMarketValue(p), 0);

  // 获取历史数据
  const fetchHistory = async (accountId, days) => {
    if (!accountId) return;

    setHistoryLoading(true);
    setHistoryError(null);

    try {
      const response = await positionsAPI.getHistory(accountId, days);
      setHistoryData(response.data);
    } catch (error) {
      setHistoryError(error.response?.data?.error || '加载失败');
      message.error('加载历史数据失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  // 监听 accountId 和 timeRange 变化
  useEffect(() => {
    if (accountId) {
      const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 180;
      fetchHistory(accountId, days);
    }
  }, [accountId, timeRange]);

  // 生成趋势数据（使用真实历史数据）
  const trendData = historyData.map(item => ({
    date: new Date(item.date).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }),
    value: item.value,
    cost: item.cost
  }));

  // 仓位分布数据（按基金类型）
  // 将复杂的基金类型映射到简单分类
  const mapFundType = (fundType) => {
    if (!fundType) return '其他';

    const type = fundType.toLowerCase();

    if (type.includes('股票') || type.includes('指数')) {
      return '股票型';
    } else if (type.includes('债券') || type.includes('中短债') || type.includes('固收')) {
      return '债券型';
    } else if (type.includes('混合')) {
      return '混合型';
    } else if (type.includes('货币')) {
      return '货币型';
    } else if (type.includes('qdii') || type.includes('海外')) {
      return 'QDII';
    } else {
      return '其他';
    }
  };

  const typeMap = {};
  positions.forEach(p => {
    const type = mapFundType(p.fund_type);
    const value = calculateMarketValue(p);
    if (!typeMap[type]) {
      typeMap[type] = 0;
    }
    typeMap[type] += value;
  });

  const distributionData = Object.entries(typeMap)
    .filter(([_, value]) => value > 0)
    .map(([name, value]) => ({
      name,
      value: parseFloat(value.toFixed(2)),
      percent: totalValue > 0 ? ((value / totalValue) * 100).toFixed(2) : '0',
    }));

  // 收益排行数据
  const rankingData = positions
    .map(p => ({
      name: p.fund_name.length > 6 ? p.fund_name.substring(0, 6) + '...' : p.fund_name,
      pnl: parseFloat(p.pnl || 0),
    }))
    .sort((a, b) => b.pnl - a.pnl);

  // 饼图颜色
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D'];

  // Y 轴数字格式化
  const formatYAxis = (value) => {
    if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
    return value.toFixed(0);
  };

  // 自定义 Tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          backgroundColor: 'white',
          padding: '10px',
          border: '1px solid #ccc',
          borderRadius: '4px',
        }}>
          <p style={{ margin: 0 }}>{label}</p>
          {payload.map((entry, index) => (
            <p key={index} style={{ margin: '5px 0', color: entry.color }}>
              {entry.name}: ¥{entry.value.toFixed(2)}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  // 饼图 Tooltip
  const PieTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div style={{
          backgroundColor: 'white',
          padding: '10px',
          border: '1px solid #ccc',
          borderRadius: '4px',
        }}>
          <p style={{ margin: 0 }}>{data.name}</p>
          <p style={{ margin: '5px 0' }}>金额: ¥{data.value.toFixed(2)}</p>
          <p style={{ margin: '5px 0' }}>占比: {data.percent}%</p>
        </div>
      );
    }
    return null;
  };

  const items = [
    {
      key: 'trend',
      label: '收益趋势',
      children: (
        <div>
          <Radio.Group
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            style={{ marginBottom: 16 }}
          >
            <Radio.Button value="7d">近7天</Radio.Button>
            <Radio.Button value="30d">近30天</Radio.Button>
            <Radio.Button value="90d">近90天</Radio.Button>
            <Radio.Button value="all">全部</Radio.Button>
          </Radio.Group>
          {historyLoading ? (
            <div style={{ textAlign: 'center', padding: '50px 0' }}>
              <Spin tip="加载中..." />
            </div>
          ) : historyError ? (
            <Empty description={historyError} />
          ) : trendData.length === 0 ? (
            <Empty description="暂无历史数据" />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  interval={isMobile ? 'preserveStartEnd' : 'preserveEnd'}
                  angle={isMobile ? -45 : 0}
                  textAnchor={isMobile ? 'end' : 'middle'}
                  height={isMobile ? 50 : 30}
                />
                <YAxis tickFormatter={formatYAxis} width={50} />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#1890ff"
                  name="账户市值"
                  strokeWidth={2}
                />
                <Line
                  type="monotone"
                  dataKey="cost"
                  stroke="#ff4d4f"
                  name="持仓成本"
                  strokeDasharray="5 5"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      ),
    },
    {
      key: 'distribution',
      label: '仓位分布',
      children: distributionData.length > 0 ? (
        <div style={{ width: '100%', height: 400 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={distributionData}
                cx="50%"
                cy="50%"
                labelLine={!isMobile}
                label={isMobile ? false : (entry) => `${entry.name} ${entry.percent}%`}
                outerRadius={isMobile ? 80 : 120}
                dataKey="value"
                nameKey="name"
              >
                {distributionData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<PieTooltip />} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <Empty description="暂无持仓数据" />
      ),
    },
    {
      key: 'ranking',
      label: '收益排行',
      children: rankingData.length > 0 ? (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={rankingData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis tickFormatter={formatYAxis} width={50} />
            <Tooltip
              formatter={(value) => `¥${value.toFixed(2)}`}
              labelStyle={{ color: '#000' }}
            />
            <Bar dataKey="pnl" name="盈亏">
              {rankingData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? '#ff4d4f' : '#52c41a'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <Empty description="暂无持仓数据" />
      ),
    },
  ];

  if (positions.length === 0) {
    return null;
  }

  return (
    <Card title="数据可视化" style={{ marginBottom: 16 }}>
      <Tabs items={items} />
    </Card>
  );
};

export default PositionCharts;
