import { useState, useEffect } from 'react';
import { Card, Table, Input, Button, Space, message, Typography, Modal, Select } from 'antd';
import { useNavigate } from 'react-router-dom';
import { SearchOutlined, EyeOutlined, StarOutlined, ReloadOutlined } from '@ant-design/icons';
import { Resizable } from 'react-resizable';
import 'react-resizable/css/styles.css';
import { fundsAPI, watchlistsAPI, preferencesAPI } from '../api';

const { Text } = Typography;

// 可调整大小的表头组件
const ResizableTitle = (props) => {
  const { onResize, width, ...restProps } = props;

  if (!width) {
    return <th {...restProps} />;
  }

  return (
    <Resizable
      width={width}
      height={0}
      handle={
        <span
          className="react-resizable-handle"
          onClick={(e) => e.stopPropagation()}
        />
      }
      onResize={onResize}
      draggableOpts={{ enableUserSelectHack: false }}
    >
      <th {...restProps} />
    </Resizable>
  );
};

const FundsPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [estimateLoading, setEstimateLoading] = useState(false);
  const [funds, setFunds] = useState([]);
  const [estimates, setEstimates] = useState({});
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [lastUpdateTime, setLastUpdateTime] = useState(null);
  const [source, setSource] = useState('eastmoney');
  const pageSize = 10;

  // 自选列表相关状态
  const [watchlistModalVisible, setWatchlistModalVisible] = useState(false);
  const [selectedFund, setSelectedFund] = useState(null);
  const [watchlists, setWatchlists] = useState([]);
  const [selectedWatchlistId, setSelectedWatchlistId] = useState(null);

  // 列宽状态
  const [columnWidths, setColumnWidths] = useState({
    fund_code: 80,
    fund_name: window.innerWidth < 768 ? 150 : 200,
    latest_nav: 110,
    estimate_nav: 90,
    estimate_growth: 80,
    action: 80,
  });

  // 处理列宽调整
  const handleResize = (key) => (e, { size }) => {
    setColumnWidths((prev) => ({
      ...prev,
      [key]: size.width,
    }));
  };

  // 加载基金列表
  const loadFunds = async (searchValue = search, pageNum = page) => {
    setLoading(true);
    try {
      const response = await fundsAPI.list({
        search: searchValue,
        page: pageNum,
        page_size: pageSize,
      });
      setFunds(response.data.results);
      setTotal(response.data.count);

      // 加载估值和净值数据
      await loadEstimatesAndNavs(response.data.results);
    } catch (error) {
      message.error('加载基金列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载估值和净值数据
  const loadEstimatesAndNavs = async (fundList, sourceName = source) => {
    if (!fundList || fundList.length === 0) return;

    setEstimateLoading(true);
    try {
      const fundCodes = fundList.map((f) => f.fund_code);

      // 并发获取估值和净值
      const [estimatesResponse, navsResponse] = await Promise.all([
        fundsAPI.batchEstimate(fundCodes, sourceName),
        fundsAPI.batchUpdateNav(fundCodes),
      ]);

      setEstimates(estimatesResponse.data);
      setLastUpdateTime(new Date());

      // 更新基金列表中的净值
      const updatedFunds = fundList.map(fund => {
        const navData = navsResponse.data[fund.fund_code];
        if (navData && !navData.error) {
          return {
            ...fund,
            latest_nav: navData.latest_nav,
            latest_nav_date: navData.latest_nav_date,
          };
        }
        return fund;
      });
      setFunds(updatedFunds);
    } catch (error) {
      console.error('获取数据失败:', error);
      message.error('获取数据失败');
    } finally {
      setEstimateLoading(false);
    }
  };

  // 刷新估值和净值
  const handleRefresh = async () => {
    if (funds.length === 0) return;
    await loadEstimatesAndNavs(funds);
    message.success('数据已刷新');
  };

  // 切换数据源
  const handleSourceChange = async (newSource) => {
    setSource(newSource);
    await preferencesAPI.update(newSource).catch(() => {});
    if (funds.length > 0) {
      await loadEstimatesAndNavs(funds, newSource);
    }
  };

  useEffect(() => {
    // 加载用户偏好数据源
    preferencesAPI.get().then(res => {
      setSource(res.data.preferred_source || 'eastmoney');
    }).catch(() => {});
    loadFunds();
  }, []);

  const handleSearch = (value) => {
    setSearch(value);
    setPage(1);
    loadFunds(value, 1);
  };

  const handlePageChange = (pageNum) => {
    setPage(pageNum);
    loadFunds(search, pageNum);
  };

  const handleViewDetail = (fundCode) => {
    navigate(`/dashboard/funds/${fundCode}`);
  };

  const handleAddToWatchlist = async (fund) => {
    setSelectedFund(fund);

    // 加载自选列表
    try {
      const response = await watchlistsAPI.list();
      setWatchlists(response.data);

      if (response.data.length === 0) {
        message.warning('请先创建自选列表');
        navigate('/dashboard/watchlists');
        return;
      }

      // 默认选中第一个
      setSelectedWatchlistId(response.data[0].id);
      setWatchlistModalVisible(true);
    } catch (error) {
      message.error('加载自选列表失败');
    }
  };

  // 确认添加到自选
  const handleConfirmAddToWatchlist = async () => {
    if (!selectedWatchlistId || !selectedFund) {
      return;
    }

    try {
      await watchlistsAPI.addItem(selectedWatchlistId, selectedFund.fund_code);
      message.success('添加成功');
      setWatchlistModalVisible(false);
    } catch (error) {
      const errorMsg = error.response?.data?.error || '添加失败';
      message.error(errorMsg);
    }
  };

  const columns = [
    {
      title: '代码',
      dataIndex: 'fund_code',
      key: 'fund_code',
      width: columnWidths.fund_code,
      responsive: ['sm'],
      resizable: true,
      onHeaderCell: (column) => ({
        width: column.width,
        onResize: handleResize('fund_code'),
      }),
    },
    {
      title: '基金名称',
      dataIndex: 'fund_name',
      key: 'fund_name',
      width: columnWidths.fund_name,
      ellipsis: true,
      resizable: true,
      onHeaderCell: (column) => ({
        width: column.width,
        onResize: handleResize('fund_name'),
      }),
    },
    {
      title: '最新净值',
      dataIndex: 'latest_nav',
      key: 'latest_nav',
      width: columnWidths.latest_nav,
      resizable: true,
      onHeaderCell: (column) => ({
        width: column.width,
        onResize: handleResize('latest_nav'),
      }),
      render: (nav, record) => {
        if (!nav) return '-';

        const date = record.latest_nav_date;
        const dateStr = date ? `(${date.slice(5)})` : '';

        return (
          <span style={{ whiteSpace: 'nowrap' }}>
            {Number(nav).toFixed(4)}
            <Text type="secondary" style={{ fontSize: '11px', marginLeft: '2px' }}>
              {dateStr}
            </Text>
          </span>
        );
      },
    },
    {
      title: '实时估值',
      dataIndex: 'fund_code',
      key: 'estimate_nav',
      width: columnWidths.estimate_nav,
      responsive: ['lg'],
      resizable: true,
      onHeaderCell: (column) => ({
        width: column.width,
        onResize: handleResize('estimate_nav'),
      }),
      render: (code) => {
        const estimate = estimates[code];
        if (!estimate) return '-';
        if (estimate.error) return <Text type="secondary">-</Text>;
        return estimate.estimate_nav ? Number(estimate.estimate_nav).toFixed(4) : '-';
      },
    },
    {
      title: '涨跌',
      dataIndex: 'fund_code',
      key: 'estimate_growth',
      width: columnWidths.estimate_growth,
      responsive: ['md'],
      resizable: true,
      onHeaderCell: (column) => ({
        width: column.width,
        onResize: handleResize('estimate_growth'),
      }),
      render: (code) => {
        const estimate = estimates[code];
        if (!estimate || !estimate.estimate_growth) return '-';

        const growth = parseFloat(estimate.estimate_growth);
        const color = growth >= 0 ? '#cf1322' : '#3f8600';
        const prefix = growth >= 0 ? '+' : '';

        return (
          <Text strong style={{ color, fontSize: '13px' }}>
            {prefix}{growth.toFixed(2)}%
          </Text>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: columnWidths.action,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.fund_code)}
          />
          <Button
            type="link"
            size="small"
            icon={<StarOutlined />}
            onClick={() => handleAddToWatchlist(record)}
          />
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="基金列表"
      extra={
        <Space>
          {lastUpdateTime && (
            <Text type="secondary" style={{ fontSize: '12px' }}>
              估值更新时间: {lastUpdateTime.toLocaleTimeString()}
            </Text>
          )}
          <Select
            value={source}
            onChange={handleSourceChange}
            size="small"
            style={{ width: 100 }}
            options={[
              { label: '东方财富', value: 'eastmoney' },
              { label: '养基宝', value: 'yangjibao' },
            ]}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={estimateLoading}
            size="small"
          >
            刷新
          </Button>
        </Space>
      }
    >
      <Space style={{ width: '100%', marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索基金名称或代码"
          allowClear
          enterButton={<SearchOutlined />}
          size="large"
          onSearch={handleSearch}
          onChange={(e) => {
            if (!e.target.value) {
              handleSearch('');
            }
          }}
          style={{ width: '100%' }}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={funds}
        rowKey="fund_code"
        loading={loading || estimateLoading}
        scroll={{ x: 'max-content' }}
        components={{
          header: {
            cell: ResizableTitle,
          },
        }}
        pagination={{
          current: page,
          pageSize: pageSize,
          total: total,
          onChange: handlePageChange,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 条`,
          simple: window.innerWidth < 768,
        }}
      />

      {/* 添加到自选 Modal */}
      <Modal
        title="添加到自选列表"
        open={watchlistModalVisible}
        onOk={handleConfirmAddToWatchlist}
        onCancel={() => setWatchlistModalVisible(false)}
        okText="添加"
        cancelText="取消"
      >
        <p>基金：{selectedFund?.fund_code} - {selectedFund?.fund_name}</p>
        <Select
          style={{ width: '100%' }}
          placeholder="选择自选列表"
          value={selectedWatchlistId}
          onChange={setSelectedWatchlistId}
          options={watchlists.map(w => ({
            label: w.name,
            value: w.id,
          }))}
        />
      </Modal>
    </Card>
  );
};

export default FundsPage;
