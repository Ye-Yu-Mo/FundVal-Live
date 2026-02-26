import { useState, useEffect } from 'react';
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
  Select,
} from 'antd';
import { RobotOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { fundsAPI, positionsAPI, preferencesAPI, aiAPI } from '../api';
import AIAnalysisModal from '../components/AIAnalysisModal';

const FundDetailPage = () => {
  const { code } = useParams();
  const [loading, setLoading] = useState(true);
  const [fund, setFund] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [navHistory, setNavHistory] = useState([]);
  const [positions, setPositions] = useState([]);
  const [operations, setOperations] = useState([]);
  const [timeRange, setTimeRange] = useState('1M');
  const [chartLoading, setChartLoading] = useState(false);
  const [source, setSource] = useState('eastmoney');

  // AI 分析
  const [aiModalVisible, setAiModalVisible] = useState(false);

  const buildAiContextData = () => {
    const navHistoryStr = navHistory.slice(-30).map(h => `${h.nav_date}:${h.unit_nav}`).join(',');
    const pos = positions.find(p => p.fund?.fund_code === code);
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
    setChartLoading(true);
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
      const endDateStr = now.toISOString().split('T')[0];

      console.log(`Loading ${range} data for fund ${code}: ${startDateStr} to ${endDateStr}`);

      // 先同步数据
      try {
        console.log('Syncing nav history...');
        await fundsAPI.syncNavHistory([code], startDateStr, endDateStr);
        console.log('Sync completed');
      } catch (syncError) {
        console.error('Sync failed:', syncError);
        // 同步失败不影响后续加载
      }

      // 加载数据
      const params = range === 'ALL' ? {} : { start_date: startDateStr };
      const response = await fundsAPI.navHistory(code, params);

      console.log('Nav history response:', response.data.length, 'records');

      // 按日期正序排列
      const data = response.data.sort((a, b) =>
        new Date(a.nav_date) - new Date(b.nav_date)
      );

      setNavHistory(data);
    } catch (error) {
      console.error('Load nav history error:', error);
      message.error('加载历史净值失败');
    } finally {
      setChartLoading(false);
    }
  };

  // 加载持仓分布
  const loadPositions = async () => {
    try {
      const response = await positionsAPI.listByFund(code);

      // 计算市值和盈亏
      const positionsWithCalc = response.data.map(pos => {
        // 使用持仓数据中的基金净值，如果没有则使用页面的基金净值
        const latestNav = pos.fund?.latest_nav || fund?.latest_nav || 0;
        const marketValue = parseFloat(pos.holding_share) * parseFloat(latestNav);
        const costValue = parseFloat(pos.holding_cost);
        const profit = marketValue - costValue;
        const profitRate = costValue > 0 ? (profit / costValue * 100) : 0;

        return {
          ...pos,
          market_value: marketValue.toFixed(2),
          profit: profit.toFixed(2),
          profit_rate: profitRate.toFixed(2)
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
      console.log('Operations loaded:', response.data.length);
    } catch (error) {
      // 未认证或没有操作记录，不显示错误
      setOperations([]);
    }
  };

  // 页面加载
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);

      try {
        // 加载用户偏好数据源
        const prefRes = await preferencesAPI.get().catch(() => null);
        const preferredSource = prefRes?.data?.preferred_source || 'eastmoney';
        setSource(preferredSource);

        // 并发加载基金详情和估值
        const [detailRes, estimateRes] = await Promise.all([
          fundsAPI.detail(code),
          fundsAPI.getEstimate(code, preferredSource).catch(() => null),
        ]);

        setFund(detailRes.data);
        setEstimate(estimateRes?.data || null);

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
  }, [code]);

  // ECharts 配置
  const chartOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    xAxis: {
      type: 'category',
      data: navHistory.map(item => item.nav_date),
      axisLabel: {
        rotate: window.innerWidth < 768 ? 45 : 0
      }
    },
    yAxis: {
      type: 'value',
      scale: true
    },
    series: [
      {
        name: '单位净值',
        type: 'line',
        data: navHistory.map(item => parseFloat(item.unit_nav)),
        smooth: true,
        markPoint: {
          data: operations.map(op => {
            console.log('Processing operation:', op);
            // 找到操作日期在图表中的索引
            const dateIndex = navHistory.findIndex(item => item.nav_date === op.operation_date);
            console.log(`Operation date: ${op.operation_date}, found at index: ${dateIndex}`);

            if (dateIndex === -1) return null;

            return {
              name: op.operation_type === 'BUY' ? '买入' : '卖出',
              coord: [dateIndex, parseFloat(op.nav)],
              value: op.operation_type === 'BUY' ? '买' : '卖',
              itemStyle: {
                color: op.operation_type === 'BUY' ? '#cf1322' : '#3f8600'
              },
              label: {
                show: true,
                formatter: '{c}',
                color: '#fff'
              }
            };
          }).filter(item => item !== null)
        }
      }
    ],
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      containLabel: true
    }
  };

  console.log('Chart option:', chartOption);
  console.log('Nav history length:', navHistory.length);
  console.log('Operations count:', operations.length);
  console.log('Mark points:', chartOption.series[0].markPoint.data);

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

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* 基础信息卡片 */}
      <Card
        title="基金信息"
        extra={
          <Space>
            <Button icon={<RobotOutlined />} onClick={() => setAiModalVisible(true)}>AI 分析</Button>
            <Select
              value={source}
              size="small"
              style={{ width: 100 }}
              onChange={async (newSource) => {
                setSource(newSource);
                await preferencesAPI.update(newSource).catch(() => {});
                const res = await fundsAPI.getEstimate(code, newSource).catch(() => null);
                setEstimate(res?.data || null);
              }}
              options={[
                { label: '东方财富', value: 'eastmoney' },
                { label: '养基宝', value: 'yangjibao' },
              ]}
            />
          </Space>
        }
      >
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="基金代码">{fund.fund_code}</Descriptions.Item>
          <Descriptions.Item label="基金名称">{fund.fund_name}</Descriptions.Item>
          <Descriptions.Item label="基金类型">{fund.fund_type || '-'}</Descriptions.Item>
        </Descriptions>

        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col xs={24} sm={8}>
            <Statistic
              title="最新净值"
              value={fund.latest_nav || '-'}
              precision={fund.latest_nav ? 4 : 0}
              prefix={fund.latest_nav ? '¥' : ''}
              suffix={fund.latest_nav_date ? ` (${fund.latest_nav_date.slice(5)})` : ''}
            />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic
              title="实时估值"
              value={estimate?.estimate_nav || '-'}
              precision={estimate?.estimate_nav ? 4 : 0}
              prefix={estimate?.estimate_nav ? '¥' : ''}
            />
          </Col>
          <Col xs={24} sm={8}>
            <Statistic
              title="估算涨跌"
              value={estimate?.estimate_growth || '-'}
              precision={estimate?.estimate_growth ? 2 : 0}
              suffix={estimate?.estimate_growth ? '%' : ''}
              valueStyle={{
                color: estimate?.estimate_growth >= 0 ? '#cf1322' : '#3f8600'
              }}
              prefix={estimate?.estimate_growth >= 0 ? '+' : ''}
            />
          </Col>
        </Row>
      </Card>

      {/* 历史净值图表 */}
      <Card
        title="历史净值"
        loading={chartLoading}
        extra={
          <Space wrap>
            {['1W', '1M', '3M', '6M', '1Y', 'ALL'].map(range => (
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
          </Space>
        }
      >
        {navHistory.length > 0 ? (
          <ReactECharts
            option={chartOption}
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
                key: 'account_name'
              },
              {
                title: '持仓份额',
                dataIndex: 'holding_share',
                key: 'holding_share',
                render: (v) => parseFloat(v).toFixed(2)
              },
              {
                title: '持仓成本',
                dataIndex: 'holding_cost',
                key: 'holding_cost',
                render: (v) => `¥${parseFloat(v).toFixed(2)}`
              },
              {
                title: '市值',
                dataIndex: 'market_value',
                key: 'market_value',
                render: (v) => `¥${v}`
              },
              {
                title: '盈亏',
                dataIndex: 'profit',
                key: 'profit',
                render: (v, record) => (
                  <span style={{ color: parseFloat(v) >= 0 ? '#cf1322' : '#3f8600' }}>
                    {parseFloat(v) >= 0 ? '+' : ''}¥{v} ({record.profit_rate}%)
                  </span>
                )
              }
            ]}
          />
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
