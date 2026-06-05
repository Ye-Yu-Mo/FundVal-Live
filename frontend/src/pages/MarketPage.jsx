import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Tabs,
  Table,
  Select,
  Spin,
  Empty,
  AutoComplete,
  List,
  Tag,
  Button,
  Space,
  Grid,
} from 'antd';
import { TrophyOutlined, FireOutlined, AimOutlined, SearchOutlined } from '@ant-design/icons';
import { fundsAPI } from '../api';

const { useBreakpoint } = Grid;

const CATEGORIES = [
  { value: '', label: '全部' },
  { value: '股票', label: '股票' },
  { value: '混合', label: '混合' },
  { value: '债券', label: '债券' },
  { value: '指数', label: '指数' },
  { value: 'QDII', label: 'QDII' },
  { value: '黄金', label: '黄金' },
  { value: '半导体', label: '半导体' },
];

const MarketPage = () => {
  const navigate = useNavigate();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [indices, setIndices] = useState([]);
  const [tab, setTab] = useState('gain');
  const [category, setCategory] = useState('');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [fundOptions, setFundOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const loadIndices = async () => {
    try {
      const { data: d } = await fundsAPI.marketIndices();
      setIndices(d.indices || []);
    } catch {}
  };
  const loadRankings = async (t = tab, cat = category, p = 1) => {
    setLoading(true);
    try {
      const { data: d } = await fundsAPI.rankings({ type: t, category: cat, page: p });
      setData(d.results || []);
      setTotal(d.count || 0);
    } catch {
      setData([]);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    loadIndices();
    loadRankings();
    const i = setInterval(loadIndices, 30000);
    return () => clearInterval(i);
  }, []);

  const handleSearch = async (keyword) => {
    setSearchKeyword(keyword);
    if (keyword.length < 2) {
      setFundOptions([]);
      return;
    }
    setSearchLoading(true);
    try {
      const { data: d } = await fundsAPI.search(keyword);
      setFundOptions(
        (d.results || [])
          .slice(0, 20)
          .map((f) => ({ value: f.fund_code, label: `${f.fund_code} - ${f.fund_name}` }))
      );
    } catch {
      setFundOptions([]);
    } finally {
      setSearchLoading(false);
    }
  };

  const columns = [
    { title: '#', key: 'rank', width: 40, render: (_, __, i) => (page - 1) * 20 + i + 1 },
    {
      title: '代码',
      dataIndex: 'fund_code',
      key: 'code',
      width: 90,
      render: (v) => <a onClick={() => navigate(`/dashboard/funds/${v}`)}>{v}</a>,
    },
    { title: '名称', dataIndex: 'fund_name', key: 'name', ellipsis: true },
    { title: '类型', dataIndex: 'fund_type', key: 'type', width: 80, responsive: ['md'] },
    ...(tab === 'gain'
      ? [
          {
            title: '涨跌',
            dataIndex: 'estimate_growth',
            key: 'g',
            width: 90,
            render: (v) => (
              <span style={{ color: parseFloat(v || 0) >= 0 ? '#cf1322' : '#3f8600' }}>
                {v != null ? `${parseFloat(v) >= 0 ? '+' : ''}${parseFloat(v)}%` : '-'}
              </span>
            ),
          },
        ]
      : []),
    ...(tab === 'popular' ? [{ title: '关注', dataIndex: 'pos_count', key: 'p', width: 60 }] : []),
    ...(tab === 'accuracy'
      ? [
          {
            title: '误差',
            dataIndex: 'avg_error',
            key: 'e',
            width: 80,
            render: (v) => (v ? `${(parseFloat(v) * 100).toFixed(2)}%` : '-'),
          },
        ]
      : []),
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {indices.length > 0 && (
        <Card size="small">
          <div style={{ display: 'flex', gap: 16, overflowX: 'auto' }}>
            {indices.map((idx) => {
              const chg = idx.change_percent ? parseFloat(idx.change_percent) : null;
              return (
                <div key={idx.code} style={{ textAlign: 'center', minWidth: 100 }}>
                  <div style={{ fontSize: 12, color: '#999' }}>{idx.name}</div>
                  <div style={{ fontSize: 16, fontWeight: 'bold' }}>{idx.price || '-'}</div>
                  <div
                    style={{
                      fontSize: 12,
                      color: chg != null ? (chg >= 0 ? '#cf1322' : '#3f8600') : '#999',
                    }}
                  >
                    {chg != null ? `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%` : '-'}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <Card
        extra={
          <Select
            value={category || undefined}
            placeholder="分类"
            allowClear
            style={{ width: 100 }}
            onChange={(v) => {
              setCategory(v || '');
              setPage(1);
              loadRankings(tab, v || '', 1);
            }}
            options={CATEGORIES.map((c) => ({ value: c.value, label: c.label }))}
          />
        }
      >
        <Tabs
          activeKey={tab}
          onChange={(k) => {
            setTab(k);
            setPage(1);
            loadRankings(k, category, 1);
          }}
          items={[
            {
              key: 'gain',
              label: (
                <span>
                  <TrophyOutlined />
                  涨幅榜
                </span>
              ),
            },
            {
              key: 'popular',
              label: (
                <span>
                  <FireOutlined />
                  人气榜
                </span>
              ),
            },
            {
              key: 'accuracy',
              label: (
                <span>
                  <AimOutlined />
                  准度榜
                </span>
              ),
            },
            {
              key: 'search',
              label: (
                <span>
                  <SearchOutlined />
                  搜索
                </span>
              ),
            },
          ]}
        />
        {tab === 'search' ? (
          <div style={{ padding: '16px 0' }}>
            <AutoComplete
              style={{ width: '100%' }}
              options={fundOptions}
              onSearch={handleSearch}
              onSelect={(code) => navigate(`/dashboard/funds/${code}`)}
              placeholder="输入基金代码或名称搜索"
            />
            {searchKeyword && fundOptions.length === 0 && !searchLoading && (
              <Empty style={{ marginTop: 24 }} description="未找到该基金，试试同步基金列表" />
            )}
          </div>
        ) : (
          <Spin spinning={loading}>
            {data.length > 0 ? (
              isMobile ? (
                <List
                  dataSource={data}
                  pagination={{
                    current: page,
                    total,
                    pageSize: 20,
                    showSizeChanger: false,
                    onChange: (p) => {
                      setPage(p);
                      loadRankings(tab, category, p);
                    },
                  }}
                  renderItem={(item, i) => (
                    <Card
                      size="small"
                      style={{ marginBottom: 8 }}
                      onClick={() => navigate(`/dashboard/funds/${item.fund_code}`)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <div>
                          <span style={{ fontWeight: 500 }}>
                            {(page - 1) * 20 + i + 1}. {item.fund_name}
                          </span>
                          <Tag style={{ marginLeft: 8 }}>{item.fund_type}</Tag>
                          <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
                            {item.fund_code}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          {tab === 'gain' && (
                            <span
                              style={{
                                fontSize: 16,
                                color:
                                  parseFloat(item.estimate_growth || 0) >= 0
                                    ? '#cf1322'
                                    : '#3f8600',
                              }}
                            >
                              {item.estimate_growth != null
                                ? `${parseFloat(item.estimate_growth) >= 0 ? '+' : ''}${parseFloat(item.estimate_growth)}%`
                                : '-'}
                            </span>
                          )}
                          {tab === 'popular' && <span>{item.pos_count || 0} 人关注</span>}
                          {tab === 'accuracy' && (
                            <span>
                              {item.avg_error
                                ? `${(parseFloat(item.avg_error) * 100).toFixed(2)}%`
                                : '-'}
                            </span>
                          )}
                        </div>
                      </div>
                    </Card>
                  )}
                />
              ) : (
                <Table
                  dataSource={data}
                  columns={columns}
                  rowKey="fund_code"
                  size="small"
                  scroll={{ x: 'max-content' }}
                  pagination={{
                    current: page,
                    total,
                    pageSize: 20,
                    showSizeChanger: false,
                    onChange: (p) => {
                      setPage(p);
                      loadRankings(tab, category, p);
                    },
                  }}
                />
              )
            ) : (
              <Empty description="暂无数据" />
            )}
          </Spin>
        )}
      </Card>
    </Space>
  );
};

export default MarketPage;
