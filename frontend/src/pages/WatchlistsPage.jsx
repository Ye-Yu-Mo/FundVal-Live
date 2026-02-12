import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Tabs,
  Button,
  Modal,
  Form,
  Input,
  message,
  Popconfirm,
  Empty,
  Spin,
  Table,
  Space,
  AutoComplete,
} from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { watchlistsAPI, fundsAPI } from '../api';

// 自选列表内容组件（移到外面避免重新创建）
const WatchlistContent = ({
  watchlist,
  fundOptions,
  handleSearch,
  handleAddFund,
  searchKeyword,
  setSearchKeyword,
  searchLoading,
  fundsData,
  fundsLoading,
  columns,
  navigate,
}) => {
  if (!watchlist) {
    return <Empty description="请选择自选列表" />;
  }

  return (
    <div>
      {/* 搜索添加基金 */}
      <Space style={{ marginBottom: 16 }}>
        <AutoComplete
          style={{ width: 300 }}
          options={fundOptions}
          onSearch={handleSearch}
          onSelect={handleAddFund}
          placeholder="搜索基金代码或名称"
          value={searchKeyword}
          onChange={setSearchKeyword}
          notFoundContent={searchLoading ? <Spin size="small" /> : null}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            if (searchKeyword) {
              handleAddFund(searchKeyword);
            }
          }}
          disabled={!searchKeyword}
        >
          添加
        </Button>
      </Space>

      {/* 基金列表 */}
      {!watchlist.items || watchlist.items.length === 0 ? (
        <Empty
          description="还没有添加基金"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <p style={{ color: '#999', marginTop: 8 }}>
            在上方搜索框添加基金到自选列表
          </p>
        </Empty>
      ) : (
        <Table
          columns={columns}
          dataSource={fundsData}
          loading={fundsLoading}
          rowKey="fund_code"
          pagination={false}
          size="middle"
        />
      )}
    </div>
  );
};

const WatchlistsPage = () => {
  const navigate = useNavigate();
  const [watchlists, setWatchlists] = useState([]);
  const [selectedWatchlistId, setSelectedWatchlistId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [fundsData, setFundsData] = useState([]);
  const [fundsLoading, setFundsLoading] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [fundOptions, setFundOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // 加载自选列表
  const loadWatchlists = async () => {
    setLoading(true);
    try {
      const response = await watchlistsAPI.list();
      setWatchlists(response.data);
      if (response.data.length > 0 && !selectedWatchlistId) {
        setSelectedWatchlistId(response.data[0].id);
      }
    } catch (error) {
      message.error('加载自选列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 初始加载
  useEffect(() => {
    loadWatchlists();
  }, []);

  // 创建自选列表
  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await watchlistsAPI.create(values);
      message.success('创建成功');
      form.resetFields();
      setModalVisible(false);
      loadWatchlists();
    } catch (error) {
      if (error.errorFields) {
        // 表单验证错误
        return;
      }
      message.error('创建失败');
    }
  };

  // 删除自选列表
  const handleDelete = async (id) => {
    try {
      await watchlistsAPI.delete(id);
      message.success('删除成功');
      // 如果删除的是当前选中的，清空选中状态
      if (id === selectedWatchlistId) {
        setSelectedWatchlistId(null);
      }
      loadWatchlists();
    } catch (error) {
      message.error('删除失败');
    }
  };

  // 加载基金详情
  const loadFundDetails = async () => {
    const currentWatchlist = watchlists.find(w => w.id === selectedWatchlistId);

    if (!currentWatchlist || !currentWatchlist.items || currentWatchlist.items.length === 0) {
      setFundsData([]);
      return;
    }

    const fundCodes = currentWatchlist.items.map(item => item.fund_code);

    setFundsLoading(true);
    try {
      // 批量更新最新净值和估值
      const [navsResponse, estimatesResponse] = await Promise.all([
        fundsAPI.batchUpdateNav(fundCodes),
        fundsAPI.batchEstimate(fundCodes),
      ]);

      // 合并数据
      const fundsWithEstimate = currentWatchlist.items.map(item => {
        const nav = navsResponse.data[item.fund_code] || {};
        const estimate = estimatesResponse.data[item.fund_code] || {};
        return {
          ...item,
          latest_nav: nav.latest_nav || estimate.latest_nav,
          latest_nav_date: nav.latest_nav_date || estimate.latest_nav_date,
          estimate_nav: estimate.estimate_nav,
          estimate_growth: estimate.estimate_growth,
          fund_name: estimate.fund_name || item.fund_name,
        };
      });

      setFundsData(fundsWithEstimate);
    } catch (error) {
      message.error('加载基金数据失败');
      setFundsData(currentWatchlist.items);
    } finally {
      setFundsLoading(false);
    }
  };

  // 自动刷新估值数据
  useEffect(() => {
    if (!selectedWatchlistId) return;

    // 立即加载一次
    loadFundDetails();

    // 每 30 秒刷新一次
    const interval = setInterval(loadFundDetails, 30000);

    return () => clearInterval(interval);
  }, [selectedWatchlistId, watchlists]);

  // 移除基金（占位，阶段四实现）
  const handleRemoveFund = async (fundCode) => {
    message.info('移除功能将在阶段四实现');
  };

  // 搜索基金
  const handleSearch = async (keyword) => {
    if (!keyword || keyword.length < 2) {
      setFundOptions([]);
      return;
    }

    setSearchLoading(true);
    try {
      const response = await fundsAPI.search(keyword);
      setFundOptions(response.data.results.slice(0, 20).map(f => ({
        value: f.fund_code,
        label: `${f.fund_code} - ${f.fund_name}`,
      })));
    } catch (error) {
      message.error('搜索失败');
    } finally {
      setSearchLoading(false);
    }
  };

  // 添加基金
  const handleAddFund = async (fundCode) => {
    if (!selectedWatchlistId) {
      message.error('请先选择自选列表');
      return;
    }

    if (!fundCode) {
      message.error('请输入基金代码');
      return;
    }

    try {
      await watchlistsAPI.addItem(selectedWatchlistId, fundCode);
      message.success('添加成功');
      setSearchKeyword('');
      setFundOptions([]);

      // 重新加载自选列表
      await loadWatchlists();

      // 立即刷新基金详情（获取净值数据）
      loadFundDetails();
    } catch (error) {
      const errorMsg = error.response?.data?.error || '添加失败';
      message.error(errorMsg);
    }
  };

  // 表格列定义
  const columns = [
    {
      title: '基金代码',
      dataIndex: 'fund_code',
      key: 'fund_code',
      width: 100,
      render: (code) => (
        <a onClick={() => navigate(`/dashboard/funds/${code}`)}>{code}</a>
      ),
    },
    {
      title: '基金名称',
      dataIndex: 'fund_name',
      key: 'fund_name',
      ellipsis: true,
    },
    {
      title: '最新净值',
      dataIndex: 'latest_nav',
      key: 'latest_nav',
      width: 120,
      render: (value) => value ? `¥${parseFloat(value).toFixed(4)}` : '-',
    },
    {
      title: '估算净值',
      dataIndex: 'estimate_nav',
      key: 'estimate_nav',
      width: 120,
      render: (value) => value ? `¥${parseFloat(value).toFixed(4)}` : '-',
    },
    {
      title: '估算涨跌',
      dataIndex: 'estimate_growth',
      key: 'estimate_growth',
      width: 120,
      render: (value) => {
        if (value === null || value === undefined) return '-';
        const num = parseFloat(value);
        return (
          <span style={{ color: num >= 0 ? '#ff4d4f' : '#52c41a' }}>
            {num >= 0 ? '+' : ''}{num.toFixed(2)}%
          </span>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_, record) => (
        <Popconfirm
          title="确定移除？"
          onConfirm={() => handleRemoveFund(record.fund_code)}
        >
          <Button type="link" danger size="small">
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  // 获取当前自选列表
  const currentWatchlist = watchlists.find(w => w.id === selectedWatchlistId);

  // 如果正在加载
  if (loading && watchlists.length === 0) {
    return (
      <Card title="自选列表">
        <div style={{ textAlign: 'center', padding: '50px 0' }}>
          <Spin tip="加载中..." />
        </div>
      </Card>
    );
  }

  // 如果没有自选列表
  if (watchlists.length === 0) {
    return (
      <Card title="自选列表">
        <Empty
          description="还没有自选列表"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setModalVisible(true)}
          >
            创建第一个自选列表
          </Button>
        </Empty>

        <Modal
          title="创建自选列表"
          open={modalVisible}
          onOk={handleCreate}
          onCancel={() => {
            setModalVisible(false);
            form.resetFields();
          }}
          okText="创建"
          cancelText="取消"
        >
          <Form form={form} layout="vertical">
            <Form.Item
              name="name"
              label="列表名称"
              rules={[
                { required: true, message: '请输入列表名称' },
                { max: 50, message: '名称不能超过50个字符' },
              ]}
            >
              <Input placeholder="例如：我的自选" />
            </Form.Item>
          </Form>
        </Modal>
      </Card>
    );
  }

  // 有自选列表
  return (
    <Card
      title="自选列表"
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalVisible(true)}
        >
          创建自选
        </Button>
      }
    >
      <Tabs
        activeKey={selectedWatchlistId}
        onChange={setSelectedWatchlistId}
        items={watchlists.map(w => ({
          key: w.id,
          label: (
            <span>
              {w.name}
              <Popconfirm
                title="确定删除？"
                description="删除后无法恢复"
                onConfirm={(e) => {
                  e.stopPropagation();
                  handleDelete(w.id);
                }}
                okText="确定"
                cancelText="取消"
              >
                <DeleteOutlined
                  style={{ marginLeft: 8, color: '#ff4d4f' }}
                  onClick={(e) => e.stopPropagation()}
                />
              </Popconfirm>
            </span>
          ),
          children: (
            <WatchlistContent
              watchlist={w}
              fundOptions={fundOptions}
              handleSearch={handleSearch}
              handleAddFund={handleAddFund}
              searchKeyword={searchKeyword}
              setSearchKeyword={setSearchKeyword}
              searchLoading={searchLoading}
              fundsData={fundsData}
              fundsLoading={fundsLoading}
              columns={columns}
              navigate={navigate}
            />
          ),
        }))}
      />

      <Modal
        title="创建自选列表"
        open={modalVisible}
        onOk={handleCreate}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="列表名称"
            rules={[
              { required: true, message: '请输入列表名称' },
              { max: 50, message: '名称不能超过50个字符' },
            ]}
          >
            <Input placeholder="例如：我的自选" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default WatchlistsPage;
