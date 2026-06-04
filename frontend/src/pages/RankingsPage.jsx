import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tabs, Table, Select, Spin, Empty, Tag } from 'antd';
import { TrophyOutlined, FireOutlined, AimOutlined } from '@ant-design/icons';
import { fundsAPI } from '../api';

const CATEGORIES = [
  { value: '', label: '全部' },
  { value: '股票', label: '股票型' },
  { value: '混合', label: '混合型' },
  { value: '债券', label: '债券型' },
  { value: '指数', label: '指数型' },
  { value: 'QDII', label: 'QDII' },
  { value: '黄金', label: '黄金' },
  { value: '半导体', label: '半导体' },
];

const RankingsPage = () => {
  const navigate = useNavigate();
  const [type, setType] = useState('gain');
  const [category, setCategory] = useState('');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadData = async (rankType = type, cat = category) => {
    setLoading(true);
    try {
      const { data: res } = await fundsAPI.rankings({ type: rankType, category: cat, page: 1 });
      setData(res.results || []);
    } catch {
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const columns = [
    { title: '排名', key: 'rank', width: 60, render: (_, __, i) => i + 1 },
    {
      title: '基金代码', dataIndex: 'fund_code', key: 'code', width: 100,
      render: (code) => <a onClick={() => navigate(`/dashboard/funds/${code}`)}>{code}</a>,
    },
    { title: '基金名称', dataIndex: 'fund_name', key: 'name', ellipsis: true },
    { title: '类型', dataIndex: 'fund_type', key: 'type', width: 80, responsive: ['md'] },
    ...(type === 'gain' ? [{
      title: '估算涨跌', dataIndex: 'estimate_growth', key: 'growth', width: 100,
      render: v => <span style={{ color: parseFloat(v) >= 0 ? '#cf1322' : '#3f8600' }}>{v != null ? `${parseFloat(v) >= 0 ? '+' : ''}${parseFloat(v)}%` : '-'}</span>,
    }] : []),
    ...(type === 'popular' ? [{
      title: '关注数', dataIndex: 'pos_count', key: 'popular', width: 80,
    }] : []),
    ...(type === 'accuracy' ? [{
      title: '平均误差', dataIndex: 'avg_error', key: 'error', width: 100,
      render: v => v ? `${(parseFloat(v) * 100).toFixed(2)}%` : '-',
    }] : []),
  ];

  return (
    <Card title="排行榜" extra={
      <Select value={category || undefined} placeholder="分类筛选" allowClear style={{ width: 120 }}
        onChange={v => { setCategory(v || ''); loadData(type, v || ''); }}
        options={CATEGORIES.map(c => ({ value: c.value, label: c.label }))}
      />
    }>
      <Tabs activeKey={type} onChange={k => { setType(k); loadData(k, category); }}
        items={[
          { key: 'gain', label: <span><TrophyOutlined />涨幅榜</span> },
          { key: 'popular', label: <span><FireOutlined />人气榜</span> },
          { key: 'accuracy', label: <span><AimOutlined />准度榜</span> },
        ]}
      />
      <Spin spinning={loading}>
        {data.length > 0 ? (
          <Table dataSource={data} columns={columns} rowKey="fund_code" pagination={false} size="small" scroll={{ x: 'max-content' }} />
        ) : (
          !loading && <Empty description="暂无数据" />
        )}
      </Spin>
    </Card>
  );
};

export default RankingsPage;
