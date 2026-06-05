import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Statistic,
  Row,
  Col,
  Space,
  Spin,
  Empty,
  message,
  Button,
  Table,
} from 'antd';
import { RobotOutlined, SyncOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { fundsAPI, positionsAPI } from '../api';
import AIAnalysisModal from '../components/AIAnalysisModal';
import { usePreference } from '../contexts/PreferenceContext';

const FundDetailPage = () => {
  const { code } = useParams();
  const { preferredSource } = usePreference();
  const [loading, setLoading] = useState(true);
  const [fund, setFund] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [marketQuote, setMarketQuote] = useState(null);
  const [navHistory, setNavHistory] = useState([]);
  const [accuracy, setAccuracy] = useState(null);
  const [positions, setPositions] = useState([]);
  const [operations, setOperations] = useState([]);
  const [timeRange, setTimeRange] = useState('1M');
  const [chartLoading, setChartLoading] = useState(false);
  const [holdings, setHoldings] = useState([]);
  const [holdingsLoading, setHoldingsLoading] = useState(false);
  const [viewMode, setViewMode] = useState('chart');
  const [intraday, setIntraday] = useState([]);

  // AI 分析
  const [aiModalVisible, setAiModalVisible] = useState(false);

  const buildAiContextData = () => {
    const navHistoryStr = navHistory
      .slice(-30)
      .map((h) => `${h.nav_date}:${h.unit_nav}`)
      .join(',');
    const pos = positions.find((p) => p.fund?.fund_code === code);
    return {
      fund_code: fund?.fund_code || '',
      fund_name: fund?.fund_name || '',
      fund_type: fund?.fund_type || '',
      latest_nav: fund?.latest_nav || '',
      latest_nav_date: fund?.latest_nav_date || '',
      estimate_nav: estimate?.estimate_nav || '',
      estimate_growth: estimate?.estimate_growth || '',
      nav_history: navHistoryStr,
      holding_share: pos?.holding_share || '',
      holding_cost: pos?.holding_cost || '',
      holding_value: pos?.market_value || '',
      pnl: pos?.profit || '',
      pnl_rate: pos?.profit_rate || '',
    };
  };

  // 加载历史净值
  const loadNavHistory = async (range) => {
    try {
      // 计算日期范围
      const now = new Date();
      const startDate = new Date();

      switch (range) {
        case '1W':
          startDate.setDate(now.getDate() - 7);
          break;
        case '1M':
          startDate.setMonth(now.getMonth() - 1);
          break;
        case '3M':
          startDate.setMonth(now.getMonth() - 3);
          break;
        case '6M':
          startDate.setMonth(now.getMonth() - 6);
          break;
        case '1Y':
          startDate.setFullYear(now.getFullYear() - 1);
          break;
        case 'ALL':
          // 10 年前
          startDate.setFullYear(now.getFullYear() - 10);
          break;
      }

      const startDateStr = startDate.toISOString().split('T')[0];

      const params = range === 'ALL' ? {} : { start_date: startDateStr };
      const response = await fundsAPI.navHistory(code, params);

      // 按日期正序排列
      const data = response.data.sort((a, b) => new Date(a.nav_date) - new Date(b.nav_date));

      setNavHistory(data);
    } catch (error) {
      console.error('Load nav history error:', error);
    }
  };

  // 加载持仓分布
  const loadPositions = async () => {
    try {
      const response = await positionsAPI.listByFund(code);

      // 计算市值和盈亏
      const positionsWithCalc = response.data.map((pos) => {
        // 使用持仓数据中的基金净值，如果没有则使用页面的基金净值
        const latestNav = pos.fund?.latest_nav || fund?.latest_nav || 0;
        const marketValue = parseFloat(pos.holding_share) * parseFloat(latestNav);
        const costValue = parseFloat(pos.holding_cost);
        const profit = marketValue - costValue;
        const profitRate = costValue > 0 ? (profit / costValue) * 100 : 0;

        return {
          ...pos,
          market_value: marketValue.toFixed(2),
          profit: profit.toFixed(2),
          profit_rate: profitRate.toFixed(2),
        };
      });

      setPositions(positionsWithCalc);
    } catch (error) {
      // 未认证或没有持仓，不显示错误
      setPositions([]);
    }
  };

  // 加载操作记录
  const loadOperations = async () => {
    try {
      const response = await positionsAPI.listOperations({ fund_code: code });
      setOperations(response.data);
    } catch (error) {
      // 未认证或没有操作记录，不显示错误
      setOperations([]);
    }
  };

  // 加载成分股持仓（含实时行情）
  const loadHoldings = async (fundType) => {
    if (!fundType || (!fundType.includes('指数') && !fundType.includes('ETF'))) {
      setHoldings([]);
      return;
    }
    setHoldingsLoading(true);
    try {
      const response = await fundsAPI.holdingsRealtime(code);
      setHoldings(response.data.holdings || []);
    } catch {
      setHoldings([]);
    } finally {
      setHoldingsLoading(false);
    }
  };

  // 页面加载
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);

      try {
        // 并发加载基金详情、指定源估值、准确率历史和场内价格
        const [detailRes, estimateRes, accuracyRes, marketRes, intradayRes] = await Promise.all([
          fundsAPI.detail(code),
          fundsAPI.getEstimate(code, preferredSource).catch(() => null),
          fundsAPI.getAccuracy(code).catch(() => null),
          fundsAPI.marketQuote(code).catch(() => null),
          fundsAPI.estimateIntraday(code, preferredSource).catch(() => null),
        ]);

        setFund(detailRes.data);
        setEstimate(estimateRes?.data || null);
        setAccuracy(accuracyRes?.data || null);
        setMarketQuote(marketRes?.data || null);
        setIntraday(intradayRes?.data?.snapshots || []);

        // 加载成分股（指数/ETF 基金）
        loadHoldings(detailRes.data?.fund_type);

        // 尝试更新当日净值（静默失败）
        fundsAPI.batchUpdateTodayNav([code]).catch(() => {
          // 静默失败，不影响页面加载
        });

        // 加载历史净值
        await loadNavHistory(timeRange);

        // 加载持仓（可选，未认证会失败）
        await loadPositions();

        // 加载操作记录（用于图表标注）
        await loadOperations();
      } catch (error) {
        message.error('加载基金详情失败');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [code, preferredSource]);

  // ECharts 配置
  const chartOption = useMemo(
    () => ({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      xAxis: {
        type: 'category',
        data: navHistory.map((item) => item.nav_date),
        axisLabel: {
          rotate: window.innerWidth < 768 ? 45 : 0,
        },
      },
      yAxis: {
        type: 'value',
        scale: true,
      },
      series: [
        {
          name: '单位净值',
          type: 'line',
          data: navHistory.map((item) => parseFloat(item.unit_nav)),
          smooth: true,
          markPoint: {
            data: operations
              .map((op) => {
                // 找到操作日期在图表中的索引
                const dateIndex = navHistory.findIndex(
                  (item) => item.nav_date === op.operation_date
                );
                if (dateIndex === -1) return null;

                return {
                  name: op.operation_type === 'BUY' ? '买入' : '卖出',
                  coord: [dateIndex, parseFloat(op.nav)],
                  value: op.operation_type === 'BUY' ? '买' : '卖',
                  itemStyle: {
                    color: op.operation_type === 'BUY' ? '#cf1322' : '#3f8600',
                  },
                  label: {
                    show: true,
                    formatter: '{c}',
                    color: '#fff',
                  },
                };
              })
              .filter((item) => item !== null),
          },
        },
      ],
      grid: {
        left: '3%',
        right: '4%',
        bottom: '10%',
        containLabel: true,
      },
    }),
    [navHistory, positions, operations, intraday]
  );

  // 持仓穿透 30s 自动刷新
  useEffect(() => {
    if (!fund?.fund_type || holdings.length === 0) return;
    const interval = setInterval(() => loadHoldings(fund.fund_type), 30000);
    return () => clearInterval(interval);
  }, [fund?.fund_type, holdings.length]);

  // 加载中
  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
          <Spin tip="加载中..." />
        </div>
      </Card>
    );
  }

  // 基金不存在
  if (!fund) {
    return (
      <Card>
        <Empty description="基金不存在" />
      </Card>
    );
  }

  // 获取主要数据源的准确率记录
  const accuracyRecords = accuracy ? accuracy.eastmoney?.records || [] : [];

  // 计算场内溢价率: (场内价格 - 实时估值) / 实时估值
  const calculatePremium = () => {
    if (!estimate?.estimate_nav || !marketQuote?.market_price) return null;
    const est = parseFloat(estimate.estimate_nav);
    const mkt = parseFloat(marketQuote.market_price);
    if (est === 0) return null;
    // (场内价格 - 实时估值) / 实时估值
    return ((mkt - est) / est) * 100;
  };

  const premium = calculatePremium();

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* 基础信息卡片 */}
      <Card
        title="基金信息"
        extra={
          <Button type="primary" icon={<RobotOutlined />} onClick={() => setAiModalVisible(true)}>
            AI 分析
          </Button>
        }
      >
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="基金代码">{fund.fund_code}</Descriptions.Item>
          <Descriptions.Item label="基金名称">{fund.fund_name}</Descriptions.Item>
          <Descriptions.Item label="基金类型">{fund.fund_type || '-'}</Descriptions.Item>
        </Descriptions>

        <Row gutter={[16, 24]} style={{ marginTop: 16 }}>
          <Col xs={12} sm={6} md={4}>
            <Statistic
              title="最新净值"
              value={fund.latest_nav || '-'}
              precision={fund.latest_nav ? 4 : 0}
              prefix={fund.latest_nav ? '¥' : ''}
              suffix={fund.latest_nav_date ? ` (${fund.latest_nav_date.slice(5)})` : ''}
              valueStyle={{ fontSize: '18px' }}
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Statistic
              title="实时估值"
              value={estimate?.estimate_nav || '-'}
              precision={estimate?.estimate_nav ? 4 : 0}
              prefix={estimate?.estimate_nav ? '¥' : ''}
              valueStyle={{ fontSize: '18px' }}
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Statistic
              title="估算涨跌"
              value={estimate?.estimate_growth || '-'}
              precision={estimate?.estimate_growth ? 2 : 0}
              suffix={estimate?.estimate_growth ? '%' : ''}
              valueStyle={{
                color: estimate?.estimate_growth >= 0 ? '#cf1322' : '#3f8600',
                fontSize: '18px',
              }}
              prefix={estimate?.estimate_growth >= 0 ? '+' : ''}
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Statistic
              title="场内价格"
              value={marketQuote?.market_price || '-'}
              precision={marketQuote?.market_price ? 3 : 0}
              prefix={marketQuote?.market_price ? '¥' : ''}
              valueStyle={{ fontSize: '18px' }}
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Statistic
              title="场内涨跌"
              value={marketQuote?.market_growth || '-'}
              precision={marketQuote?.market_growth ? 2 : 0}
              suffix={marketQuote?.market_growth ? '%' : ''}
              valueStyle={{
                color: marketQuote?.market_growth >= 0 ? '#cf1322' : '#3f8600',
                fontSize: '18px',
              }}
              prefix={marketQuote?.market_growth >= 0 ? '+' : ''}
            />
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Statistic
              title="场内溢价"
              value={premium || '-'}
              precision={2}
              suffix={premium !== null ? '%' : ''}
              valueStyle={{
                color: premium >= 0 ? '#cf1322' : '#3f8600',
                fontSize: '18px',
              }}
              prefix={premium > 0 ? '+' : ''}
            />
          </Col>
        </Row>
      </Card>

      {/* 历史估值卡片 */}
      <Card title="历史估值记录">
        {accuracyRecords.length > 0 ? (
          <Table
            dataSource={accuracyRecords}
            rowKey="date"
            pagination={{ pageSize: 5 }}
            size="small"
            columns={[
              {
                title: '日期',
                dataIndex: 'date',
                key: 'date',
              },
              {
                title: '当天净值',
                dataIndex: 'actual_nav',
                key: 'actual_nav',
                render: (v) => (v ? `¥${parseFloat(v).toFixed(4)}` : '-'),
              },
              {
                title: '收盘估值',
                dataIndex: 'estimate_nav',
                key: 'estimate_nav',
                render: (v) => (v ? `¥${parseFloat(v).toFixed(4)}` : '-'),
              },
              {
                title: '估算误差',
                dataIndex: 'error_rate',
                key: 'error_rate',
                render: (v) => {
                  if (!v) return '-';
                  const val = parseFloat(v);
                  const rate = (val * 100).toFixed(4);
                  const color = val > 0 ? '#cf1322' : '#3f8600';
                  return (
                    <span style={{ color, fontWeight: '500' }}>
                      {val > 0 ? '+' : ''}
                      {rate}%
                    </span>
                  );
                },
              },
            ]}
          />
        ) : (
          <Empty
            description="暂无历史估值数据，每日 15:05 自动采集"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
      </Card>

      {/* 数据源准确性对比 */}
      {accuracy && Object.keys(accuracy).length > 0 && (
        <Card title="数据源准确性对比" size="small">
          {Object.keys(accuracy).length >= 2 ? (
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                grid: { left: 90, right: 30, top: 10, bottom: 20 },
                xAxis: { type: 'value', axisLabel: { formatter: '{value}%' }, name: '平均误差率' },
                yAxis: {
                  type: 'category',
                  data: Object.keys(accuracy).map((k) => {
                    const names = {
                      eastmoney: '东方财富',
                      yangjibao: '养基宝',
                      xiaobeiyangji: '小倍养基',
                    };
                    return `${names[k] || k} (${accuracy[k]?.record_count || 0}样本)`;
                  }),
                },
                series: [
                  {
                    type: 'bar',
                    data: Object.keys(accuracy).map((k) => ({
                      value: parseFloat((accuracy[k]?.avg_error_rate * 100 || 0).toFixed(4)),
                      itemStyle: {
                        color:
                          k === 'eastmoney' ? '#cf1322' : k === 'yangjibao' ? '#1890ff' : '#faad14',
                      },
                    })),
                    label: { show: true, position: 'right', formatter: '{c}%' },
                  },
                ],
              }}
              style={{ height: Math.max(120, Object.keys(accuracy).length * 40 + 40) }}
            />
          ) : (
            Object.entries(accuracy).map(([k, v]) => {
              const names = {
                eastmoney: '东方财富',
                yangjibao: '养基宝',
                xiaobeiyangji: '小倍养基',
              };
              return (
                <Row gutter={16} key={k}>
                  <Col span={8}>
                    <Statistic title="数据源" value={names[k] || k} />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="平均误差率"
                      value={
                        v.avg_error_rate != null ? `${(v.avg_error_rate * 100).toFixed(4)}%` : '-'
                      }
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic title="样本数" value={v.record_count || 0} />
                  </Col>
                </Row>
              );
            })
          )}
        </Card>
      )}

      {/* 历史净值图表 */}
      <Card
        title="历史净值"
        extra={
          <Space wrap>
            {['1W', '1M', '3M', '6M', '1Y', 'ALL'].map((range) => (
              <Button
                key={range}
                size="small"
                type={timeRange === range ? 'primary' : 'default'}
                onClick={() => {
                  setTimeRange(range);
                  loadNavHistory(range);
                }}
              >
                {range === 'ALL' ? '全部' : range === '1W' ? '1周' : range}
              </Button>
            ))}
            <Button
              size="small"
              type={timeRange === 'INTRADAY' ? 'primary' : 'default'}
              onClick={() => {
                setTimeRange('INTRADAY');
                fundsAPI
                  .estimateIntraday(code, preferredSource)
                  .then((res) => setIntraday(res?.data?.snapshots || []))
                  .catch(() => {});
              }}
            >
              当日估值
            </Button>
          </Space>
        }
      >
        {timeRange === 'INTRADAY' ? (
          intraday.length > 0 ? (
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                xAxis: {
                  type: 'category',
                  data: intraday.map((s) =>
                    new Date(s.timestamp).toLocaleTimeString('zh-CN', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  ),
                },
                yAxis: { type: 'value', scale: true, name: '估值净值' },
                series: [
                  {
                    name: '估值净值',
                    type: 'line',
                    data: intraday.map((s) => parseFloat(s.estimate_nav)),
                    smooth: true,
                    lineStyle: { color: '#cf1322', width: 2 },
                    itemStyle: { color: '#cf1322' },
                    symbol: 'circle',
                    symbolSize: 6,
                    areaStyle: { color: 'rgba(207,19,34,0.1)' },
                  },
                ],
                grid: { left: '8%', right: '4%', top: 10, bottom: 20 },
              }}
              style={{ height: window.innerWidth < 768 ? 300 : 400 }}
            />
          ) : (
            <Empty
              description="暂无当日估值数据，交易时段每5分钟自动采集"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )
        ) : navHistory.length > 0 ? (
          <ReactECharts
            option={chartOption}
            notMerge={false}
            lazyUpdate={true}
            style={{ height: window.innerWidth < 768 ? 300 : 400 }}
          />
        ) : (
          <Empty description="暂无历史数据" />
        )}
      </Card>

      {/* 持仓分布 */}
      {positions.length > 0 && (
        <Card title="我的持仓">
          <Table
            dataSource={positions}
            rowKey="id"
            pagination={false}
            scroll={{ x: 'max-content' }}
            columns={[
              {
                title: '账户',
                dataIndex: 'account_name',
                key: 'account_name',
              },
              {
                title: '持仓份额',
                dataIndex: 'holding_share',
                key: 'holding_share',
                render: (v) => parseFloat(v).toFixed(2),
              },
              {
                title: '持仓成本',
                dataIndex: 'holding_cost',
                key: 'holding_cost',
                render: (v) => `¥${parseFloat(v).toFixed(2)}`,
              },
              {
                title: '市值',
                dataIndex: 'market_value',
                key: 'market_value',
                render: (v) => `¥${v}`,
              },
              {
                title: '盈亏',
                dataIndex: 'profit',
                key: 'profit',
                render: (v, record) => (
                  <span style={{ color: parseFloat(v) >= 0 ? '#cf1322' : '#3f8600' }}>
                    {parseFloat(v) >= 0 ? '+' : ''}¥{v} ({record.profit_rate}%)
                  </span>
                ),
              },
            ]}
          />
        </Card>
      )}

      {/* 成分股持仓穿透 */}
      {(holdings.length > 0 || holdingsLoading) && (
        <Card
          title="持仓穿透"
          extra={
            <Space>
              <Button
                size="small"
                type={viewMode === 'chart' ? 'primary' : 'default'}
                onClick={() => setViewMode('chart')}
              >
                图表
              </Button>
              <Button
                size="small"
                type={viewMode === 'table' ? 'primary' : 'default'}
                onClick={() => setViewMode('table')}
              >
                表格
              </Button>
              <Button
                icon={<SyncOutlined />}
                size="small"
                loading={holdingsLoading}
                onClick={() => loadHoldings(fund?.fund_type)}
              >
                刷新
              </Button>
            </Space>
          }
        >
          {viewMode === 'chart' ? (
            holdingsLoading ? (
              <Spin style={{ display: 'block', textAlign: 'center', padding: 40 }} />
            ) : (
              <ReactECharts
                option={{
                  tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'shadow' },
                    formatter: (params) => {
                      const d = params[0];
                      const h = holdings[d.dataIndex];
                      const chg =
                        h.change_percent != null
                          ? `${parseFloat(h.change_percent) >= 0 ? '+' : ''}${parseFloat(h.change_percent).toFixed(2)}%`
                          : '-';
                      return `${h.stock_name}(${h.stock_code})<br/>权重: ${parseFloat(h.weight).toFixed(2)}%<br/>涨跌: ${chg}`;
                    },
                  },
                  grid: { left: 100, right: 40, top: 10, bottom: 20 },
                  xAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
                  yAxis: {
                    type: 'category',
                    data: holdings.map((h) => h.stock_name).reverse(),
                    inverse: true,
                    axisLabel: { width: 90, overflow: 'truncate' },
                  },
                  series: [
                    {
                      type: 'bar',
                      data: holdings
                        .map((h) => ({
                          value: parseFloat(h.weight),
                          itemStyle: {
                            color:
                              h.change_percent != null
                                ? parseFloat(h.change_percent) >= 0
                                  ? '#cf1322'
                                  : '#3f8600'
                                : '#999',
                          },
                        }))
                        .reverse(),
                      label: {
                        show: true,
                        position: 'right',
                        formatter: (params) => {
                          const h = holdings[holdings.length - 1 - params.dataIndex];
                          const chg =
                            h.change_percent != null
                              ? `${parseFloat(h.change_percent) >= 0 ? '+' : ''}${parseFloat(h.change_percent).toFixed(2)}%`
                              : '-';
                          return `${parseFloat(h.weight).toFixed(2)}%  ${chg}`;
                        },
                      },
                    },
                  ],
                }}
                style={{ height: Math.max(300, holdings.length * 36) }}
              />
            )
          ) : (
            <Table
              dataSource={holdings}
              rowKey="stock_code"
              loading={holdingsLoading}
              pagination={{ pageSize: 10, showSizeChanger: false }}
              scroll={{ x: 'max-content' }}
              columns={[
                { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code', width: 100 },
                { title: '股票名称', dataIndex: 'stock_name', key: 'stock_name', width: 120 },
                {
                  title: '持仓占比',
                  dataIndex: 'weight',
                  key: 'weight',
                  width: 100,
                  sorter: (a, b) => parseFloat(a.weight) - parseFloat(b.weight),
                  defaultSortOrder: 'descend',
                  render: (v) => `${parseFloat(v).toFixed(2)}%`,
                },
                {
                  title: '最新价',
                  dataIndex: 'price',
                  key: 'price',
                  width: 100,
                  render: (v) => (v != null ? `¥${parseFloat(v).toFixed(2)}` : '-'),
                },
                {
                  title: '涨跌幅',
                  dataIndex: 'change_percent',
                  key: 'change_percent',
                  width: 100,
                  sorter: (a, b) =>
                    parseFloat(a.change_percent || 0) - parseFloat(b.change_percent || 0),
                  render: (v) => {
                    if (v == null) return '-';
                    const num = parseFloat(v);
                    return (
                      <span style={{ color: num >= 0 ? '#cf1322' : '#3f8600' }}>
                        {num >= 0 ? '+' : ''}
                        {num.toFixed(2)}%
                      </span>
                    );
                  },
                },
                {
                  title: '对基金影响',
                  dataIndex: 'contribution',
                  key: 'contribution',
                  width: 110,
                  render: (v) => {
                    if (v == null) return '-';
                    const num = parseFloat(v);
                    return (
                      <span style={{ color: num >= 0 ? '#cf1322' : '#3f8600' }}>
                        {num >= 0 ? '+' : ''}
                        {num.toFixed(4)}%
                      </span>
                    );
                  },
                },
              ]}
            />
          )}
        </Card>
      )}

      {/* AI 分析 Modal */}
      <AIAnalysisModal
        open={aiModalVisible}
        onClose={() => setAiModalVisible(false)}
        contextType="fund"
        contextData={buildAiContextData()}
        title={`AI 分析 · ${fund?.fund_name || ''}`}
      />
    </Space>
  );
};

export default FundDetailPage;
