import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Card, Select, Button, Spin, Empty, Table, Row, Col, message, Space, Skeleton } from 'antd';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { PlusOutlined } from '@ant-design/icons';
import { fundsAPI, watchlistsAPI } from '../api';

const COLORS = ['#1890ff', '#cf1322', '#faad14', '#52c41a', '#722ed1'];
const METRIC_NAMES = { '1m': '近1月', '3m': '近3月', '6m': '近6月', '1y': '近1年', max_drawdown: '最大回撤(%)', volatility: '波动率(%)', sharpe: '夏普比率' };

const ComparePage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [funds, setFunds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedCodes, setSelectedCodes] = useState([]);
  const [fundOptions, setFundOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const codesFromUrl = searchParams.get('codes')?.split(',')?.filter(Boolean) || [];

  useEffect(() => {
    if (codesFromUrl.length >= 2) {
      setSelectedCodes(codesFromUrl);
      loadCompare(codesFromUrl);
    }
  }, []);

  const loadCompare = async (codes) => {
    if (codes.length < 2) return;
    setLoading(true);
    try {
      const { data } = await fundsAPI.compare(codes);
      setFunds(data.funds);
      setSearchParams({ codes: codes.join(',') });
    } catch (err) {
      message.error(err.response?.data?.error || '对比失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (keyword) => {
    if (!keyword || keyword.length < 2) { setFundOptions([]); return; }
    setSearchLoading(true);
    try {
      const { data } = await fundsAPI.search(keyword);
      const results = data.results || [];
      setFundOptions(results.slice(0, 20).map(f => ({ value: f.fund_code, label: `${f.fund_code} - ${f.fund_name}` })));
    } catch { setFundOptions([]); }
    finally { setSearchLoading(false); }
  };

  const handleSelect = (code) => {
    if (selectedCodes.includes(code)) return;
    if (selectedCodes.length >= 5) { message.warning('最多对比 5 只基金'); return; }
    const newCodes = [...selectedCodes, code];
    setSelectedCodes(newCodes);
    loadCompare(newCodes);
  };

  const handleRemove = (code) => {
    const newCodes = selectedCodes.filter(c => c !== code);
    setSelectedCodes(newCodes);
    if (newCodes.length >= 2) loadCompare(newCodes);
    else { setFunds([]); setSearchParams({}); }
  };

  const handleImportFromWatchlist = async () => {
    try {
      const { data } = await watchlistsAPI.list();
      if (!data.length) { message.info('暂无自选列表'); return; }
      const allCodes = [...new Set(data.flatMap(w => (w.items || []).map(i => i.fund_code)))];
      if (!allCodes.length) { message.info('自选列表为空'); return; }
      const codes = allCodes.slice(0, 5);
      setSelectedCodes(codes);
      loadCompare(codes);
    } catch { message.error('加载自选列表失败'); }
  };

  const buildRadarData = () => {
    const keys = ['1m', '3m', '6m', '1y'];
    return keys.map(k => {
      const entry = { metric: METRIC_NAMES[k] };
      funds.forEach(f => { entry[f.fund_code] = f.returns?.[k] != null ? parseFloat(f.returns[k]) : 0; });
      return entry;
    });
  };

  const buildTableData = () => {
    const rows = [];
    const metricKeys = ['latest_nav', '1m', '3m', '6m', '1y', 'max_drawdown', 'volatility', 'sharpe'];
    metricKeys.forEach(k => {
      const row = { metric: METRIC_NAMES[k] || k };
      let bestVal = Infinity;
      if (k === 'max_drawdown' || k === 'volatility') bestVal = Infinity;
      else bestVal = -Infinity;

      funds.forEach(f => {
        let val = null;
        if (k === 'latest_nav') val = f.latest_nav ? parseFloat(f.latest_nav) : null;
        else if (['1m','3m','6m','1y'].includes(k)) val = f.returns?.[k] != null ? parseFloat(f.returns[k]) : null;
        else val = f.metrics?.[k] != null ? parseFloat(f.metrics[k]) : null;
        row[f.fund_code] = val;
        if (val != null) {
          if (['max_drawdown','volatility'].includes(k)) { if (val < bestVal) bestVal = val; }
          else { if (val > bestVal) bestVal = val; }
        }
      });
      row._best = bestVal;
      rows.push(row);
    });
    return rows;
  };

  const tableData = buildTableData();
  const tableColumns = [
    { title: '指标', dataIndex: 'metric', key: 'metric', width: 120, fixed: 'left' },
    ...funds.map((f, i) => ({
      title: `${f.fund_name} (${f.fund_code})`,
      dataIndex: f.fund_code,
      key: f.fund_code,
      render: (v, record) => {
        if (v == null) return '-';
        const isBest = record._best != null && v === record._best;
        const isReturn = ['近1月','近3月','近6月','近1年'].includes(record.metric);
        const color = isReturn ? (v >= 0 ? '#cf1322' : '#3f8600') : undefined;
        return <span style={{ color, fontWeight: isBest ? 'bold' : 'normal', background: isBest ? '#f6ffed' : undefined, padding: isBest ? '0 4px' : undefined }}>{typeof v === 'number' ? (isReturn ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : v.toFixed(2)) : v}</span>;
      },
    })),
  ];

  const PRESET_GROUPS = [
    { label: '白酒 vs 新能源 vs 半导体', codes: '161725,012414,014193' },
    { label: '沪深300 vs 中证500 vs 创业板', codes: '510300,510500,159915' },
    { label: '黄金 vs 债券', codes: '000218,007194' },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="基金 PK 对比" extra={
        <Space>
          <Button onClick={handleImportFromWatchlist}>从自选导入</Button>
        </Space>
      }>
        <Space style={{ marginBottom: 8 }} wrap>
          <span style={{ color: '#999' }}>热门组合：</span>
          {PRESET_GROUPS.map(g => (
            <Button key={g.codes} size="small" onClick={() => {
              const codes = g.codes.split(',');
              setSelectedCodes(codes);
              loadCompare(codes);
            }}>{g.label}</Button>
          ))}
        </Space>
        <Space style={{ marginBottom: 16 }} wrap>
          {selectedCodes.map((code, i) => (
            <Button key={code} size="small" type="primary"
              style={{ background: COLORS[i % COLORS.length], borderColor: COLORS[i % COLORS.length] }}
              onClick={() => handleRemove(code)}
            >
              {funds.find(f => f.fund_code === code)?.fund_name || code} ✕
            </Button>
          ))}
          <Select
            showSearch
            value={undefined}
            placeholder="搜索基金代码或名称添加对比"
            filterOption={false}
            onSearch={handleSearch}
            onSelect={handleSelect}
            options={fundOptions}
            loading={searchLoading}
            style={{ minWidth: 250 }}
            suffixIcon={<PlusOutlined />}
          />
        </Space>

        {loading ? <><Skeleton active paragraph={{ rows: 4 }} /><Skeleton active paragraph={{ rows: 4 }} /></> :
         funds.length >= 2 ? (
          <>
            <Card title="收益雷达图" size="small" style={{ marginBottom: 16 }}>
              <ResponsiveContainer width="100%" height={400}>
                <RadarChart data={buildRadarData()}>
                  <PolarGrid />
                  <PolarAngleAxis dataKey="metric" />
                  <PolarRadiusAxis />
                  <Tooltip formatter={(v) => `${v}%`} />
                  <Legend />
                  {funds.map((f, i) => (
                    <Radar key={f.fund_code} name={f.fund_name} dataKey={f.fund_code} stroke={COLORS[i % COLORS.length]} fill={COLORS[i % COLORS.length]} fillOpacity={0.1} />
                  ))}
                </RadarChart>
              </ResponsiveContainer>
            </Card>

            <Card title="指标对比" size="small">
              <Table
                dataSource={tableData}
                columns={tableColumns}
                rowKey="metric"
                pagination={false}
                size="small"
                scroll={{ x: 'max-content' }}
                locale={{ emptyText: '-' }}
              />
            </Card>
          </>
        ) : (
          !loading && <Empty description="请搜索并选择 2-5 只基金开始对比，或点击「从自选导入」" />
        )}
      </Card>
    </Space>
  );
};

export default ComparePage;
