import { useState, useEffect } from 'react';
import {
  Card,
  Select,
  Table,
  Statistic,
  Row,
  Col,
  Radio,
  message,
  Empty,
  Tag,
  Button,
  Popconfirm,
  Modal,
  Form,
  Input,
  DatePicker,
  InputNumber,
  AutoComplete,
} from 'antd';
import { RollbackOutlined, PlusOutlined } from '@ant-design/icons';
import { accountsAPI, positionsAPI, fundsAPI } from '../api';

const PositionsPage = () => {
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [positions, setPositions] = useState([]);
  const [operations, setOperations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [operationsLoading, setOperationsLoading] = useState(false);
  const [fundTypeFilter, setFundTypeFilter] = useState('all');
  const [modalVisible, setModalVisible] = useState(false);
  const [operationType, setOperationType] = useState('BUY'); // BUY, SELL
  const [buildPositionMode, setBuildPositionMode] = useState('value'); // value, nav
  const [fundOptions, setFundOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [form] = Form.useForm();

  // 加载账户列表
  const loadAccounts = async () => {
    try {
      const response = await accountsAPI.list();
      const allAccounts = response.data;
      const childAccounts = allAccounts.filter(a => a.parent !== null);

      // 给子账户添加父账户名称
      const childAccountsWithParent = childAccounts.map(child => {
        const parent = allAccounts.find(a => a.id === child.parent);
        return {
          ...child,
          parent_name: parent?.name || '',
        };
      });

      setAccounts(childAccountsWithParent);

      // 默认选中第一个子账户
      if (childAccountsWithParent.length > 0 && !selectedAccountId) {
        setSelectedAccountId(childAccountsWithParent[0].id);
      }
    } catch (error) {
      message.error('加载账户列表失败');
    }
  };

  // 加载持仓列表
  const loadPositions = async (accountId) => {
    if (!accountId) return;

    setLoading(true);
    try {
      const response = await positionsAPI.list(accountId);
      setPositions(response.data);
    } catch (error) {
      message.error('加载持仓列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载操作流水
  const loadOperations = async (accountId) => {
    if (!accountId) return;

    setOperationsLoading(true);
    try {
      const response = await positionsAPI.listOperations({ account: accountId });
      // 按日期倒序排列
      const sorted = response.data.sort((a, b) => {
        return new Date(b.operation_date) - new Date(a.operation_date) ||
               new Date(b.created_at) - new Date(a.created_at);
      });
      setOperations(sorted);
    } catch (error) {
      message.error('加载操作流水失败');
    } finally {
      setOperationsLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccountId) {
      loadPositions(selectedAccountId);
      loadOperations(selectedAccountId);
    }
  }, [selectedAccountId]);

  // 获取当前选中的账户
  const getSelectedAccount = () => {
    return accounts.find(a => a.id === selectedAccountId);
  };

  // 计算统计数据
  const getStatistics = () => {
    const account = getSelectedAccount();
    if (!account) {
      return {
        holding_cost: '0.00',
        holding_value: '0.00',
        pnl: '0.00',
        pnl_rate: null,
        today_pnl: '0.00',
        today_pnl_rate: null,
      };
    }

    return {
      holding_cost: account.holding_cost || '0.00',
      holding_value: account.holding_value || '0.00',
      pnl: account.pnl || '0.00',
      pnl_rate: account.pnl_rate,
      today_pnl: account.today_pnl || '0.00',
      today_pnl_rate: account.today_pnl_rate,
    };
  };

  // 过滤持仓列表
  const getFilteredPositions = () => {
    if (fundTypeFilter === 'all') {
      return positions;
    }
    return positions.filter(p => {
      const fundType = p.fund_type || '';
      return fundType.includes(fundTypeFilter);
    });
  };

  // 格式化金额
  const formatMoney = (value) => {
    if (value === null || value === undefined) return '-';
    return parseFloat(value).toFixed(2);
  };

  // 格式化百分比
  const formatPercent = (value) => {
    if (value === null || value === undefined) return '-';
    return `${(parseFloat(value) * 100).toFixed(2)}%`;
  };

  // 回滚操作
  const handleRollback = async (operationId) => {
    try {
      await positionsAPI.deleteOperation(operationId);
      message.success('回滚成功');
      loadPositions(selectedAccountId);
      loadOperations(selectedAccountId);
    } catch (error) {
      message.error('回滚失败');
    }
  };

  // 获取操作类型标签
  const getOperationTypeTag = (type) => {
    const typeMap = {
      'BUY': { text: '买入', color: 'green' },
      'SELL': { text: '卖出', color: 'red' },
    };
    const config = typeMap[type] || { text: type, color: 'default' };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  // 打开添加操作 Modal
  const handleOpenModal = () => {
    form.resetFields();
    setOperationType('BUY');
    setBuildPositionMode('value');
    setFundOptions([]);
    setModalVisible(true);
  };

  // 搜索基金
  const handleFundSearch = async (keyword) => {
    if (!keyword || keyword.length < 2) {
      setFundOptions([]);
      return;
    }

    setSearchLoading(true);
    try {
      const response = await fundsAPI.search(keyword);
      const options = response.data.map(fund => ({
        value: fund.fund_code,
        label: `${fund.fund_code} - ${fund.fund_name}`,
        fund: fund,
      }));
      setFundOptions(options);
    } catch (error) {
      message.error('搜索基金失败');
    } finally {
      setSearchLoading(false);
    }
  };

  // 选择基金后自动填充净值
  const handleFundSelect = async (value, option) => {
    if (!option.fund) return;

    const fund = option.fund;
    if (fund.latest_nav) {
      form.setFieldsValue({
        nav: parseFloat(fund.latest_nav),
      });

      // 如果是加仓模式，自动计算份额
      if (operationType === 'BUY' && buildPositionMode === 'nav') {
        handleNavModeCalculate();
      }
      // 如果是减仓模式，自动计算金额
      if (operationType === 'SELL') {
        handleSellCalculate();
      }
    }
  };

  // 提交操作
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      // 构造提交数据
      const data = {
        account: selectedAccountId,
        fund_code: values.fund_code,
        operation_type: operationType,
        operation_date: values.operation_date.format('YYYY-MM-DD'),
        before_15: values.before_15 === 'before',
        amount: values.amount,
        share: values.share,
        nav: values.nav,
      };

      await positionsAPI.createOperation(data);
      message.success('操作添加成功');
      setModalVisible(false);
      loadPositions(selectedAccountId);
      loadOperations(selectedAccountId);
    } catch (error) {
      if (error.errorFields) {
        return;
      }
      message.error('操作添加失败');
    }
  };

  // 建仓方式 1：根据市值和收益率计算
  const handleValueModeCalculate = () => {
    const holdingValue = form.getFieldValue('holding_value');
    const pnlRate = form.getFieldValue('pnl_rate');

    if (!holdingValue || pnlRate === undefined) return;

    const cost = holdingValue / (1 + pnlRate / 100);
    const nav = holdingValue / 1000; // 假设份额为 1000，可调整
    const share = 1000;

    form.setFieldsValue({
      amount: cost.toFixed(2),
      share: share.toFixed(4),
      nav: nav.toFixed(4),
    });
  };

  // 建仓方式 2：根据净值和份额计算
  const handleNavModeCalculate = () => {
    const nav = form.getFieldValue('nav');
    const share = form.getFieldValue('share');

    if (!nav || !share) return;

    const amount = nav * share;
    form.setFieldsValue({
      amount: amount.toFixed(2),
    });
  };

  // 加仓：根据金额和净值计算份额
  const handleBuyCalculate = () => {
    const amount = form.getFieldValue('amount');
    const nav = form.getFieldValue('nav');

    if (!amount || !nav) return;

    const share = amount / nav;
    form.setFieldsValue({
      share: share.toFixed(4),
    });
  };

  // 减仓：根据份额和净值计算金额
  const handleSellCalculate = () => {
    const share = form.getFieldValue('share');
    const nav = form.getFieldValue('nav');

    if (!share || !nav) return;

    const amount = share * nav;
    form.setFieldsValue({
      amount: amount.toFixed(2),
    });
  };

  const statistics = getStatistics();

  const operationColumns = [
    {
      title: '操作日期',
      dataIndex: 'operation_date',
      key: 'operation_date',
      width: 120,
    },
    {
      title: '操作类型',
      dataIndex: 'operation_type',
      key: 'operation_type',
      width: 100,
      render: (type) => getOperationTypeTag(type),
    },
    {
      title: '基金代码',
      dataIndex: 'fund_code',
      key: 'fund_code',
      width: 100,
    },
    {
      title: '基金名称',
      dataIndex: 'fund_name',
      key: 'fund_name',
      width: 200,
    },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '份额',
      dataIndex: 'share',
      key: 'share',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '净值',
      dataIndex: 'nav',
      key: 'nav',
      width: 100,
      render: (value) => formatMoney(value),
    },
    {
      title: '时间',
      dataIndex: 'before_15',
      key: 'before_15',
      width: 100,
      render: (before15) => before15 ? '15:00前' : '15:00后',
      responsive: ['md'],
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right',
      render: (_, record, index) => {
        // 仅最新一条操作可回滚
        if (index !== 0) return null;
        return (
          <Popconfirm
            title="确定要回滚此操作吗？"
            description="回滚后将删除此操作记录并重新计算持仓"
            onConfirm={() => handleRollback(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              icon={<RollbackOutlined />}
              danger
            >
              回滚
            </Button>
          </Popconfirm>
        );
      },
    },
  ];

  const columns = [
    {
      title: '基金代码',
      dataIndex: 'fund_code',
      key: 'fund_code',
      width: 100,
    },
    {
      title: '基金名称',
      dataIndex: 'fund_name',
      key: 'fund_name',
      width: 200,
    },
    {
      title: '基金类型',
      dataIndex: 'fund_type',
      key: 'fund_type',
      width: 100,
      responsive: ['lg'],
    },
    {
      title: '持有份额',
      dataIndex: 'holding_share',
      key: 'holding_share',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '持有成本',
      dataIndex: 'holding_cost',
      key: 'holding_cost',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '持仓市值',
      key: 'holding_value',
      width: 120,
      render: (_, record) => {
        const value = parseFloat(record.holding_share || 0) * parseFloat(record.fund?.latest_nav || 0);
        return formatMoney(value);
      },
    },
    {
      title: '盈亏金额',
      dataIndex: 'pnl',
      key: 'pnl',
      width: 120,
      render: (value) => {
        const num = parseFloat(value || 0);
        return (
          <span style={{ color: num >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {formatMoney(value)}
          </span>
        );
      },
    },
    {
      title: '盈亏率',
      key: 'pnl_rate',
      width: 100,
      render: (_, record) => {
        const cost = parseFloat(record.holding_cost || 0);
        const pnl = parseFloat(record.pnl || 0);
        if (cost === 0) return '-';
        const rate = pnl / cost;
        return (
          <span style={{ color: rate >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {formatPercent(rate)}
          </span>
        );
      },
      responsive: ['md'],
    },
    {
      title: '预估市值',
      key: 'estimate_value',
      width: 120,
      render: (_, record) => {
        const estimateNav = record.fund?.estimate_nav;
        if (!estimateNav) return '-';
        const value = parseFloat(record.holding_share || 0) * parseFloat(estimateNav);
        return formatMoney(value);
      },
      responsive: ['lg'],
    },
    {
      title: '预估盈亏',
      key: 'estimate_pnl',
      width: 120,
      render: (_, record) => {
        const estimateNav = record.fund?.estimate_nav;
        if (!estimateNav) return '-';
        const estimateValue = parseFloat(record.holding_share || 0) * parseFloat(estimateNav);
        const pnl = estimateValue - parseFloat(record.holding_cost || 0);
        return (
          <span style={{ color: pnl >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {formatMoney(pnl)}
          </span>
        );
      },
      responsive: ['xl'],
    },
    {
      title: '今日盈亏',
      key: 'today_pnl',
      width: 120,
      render: (_, record) => {
        const latestNav = record.fund?.latest_nav;
        const estimateNav = record.fund?.estimate_nav;
        if (!latestNav || !estimateNav) return '-';
        const todayPnl = parseFloat(record.holding_share || 0) * (parseFloat(estimateNav) - parseFloat(latestNav));
        return (
          <span style={{ color: todayPnl >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {formatMoney(todayPnl)}
          </span>
        );
      },
      responsive: ['lg'],
    },
  ];

  if (accounts.length === 0) {
    return (
      <Card title="持仓查询">
        <Empty description="请先创建子账户" />
      </Card>
    );
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Select
          style={{ width: 300, marginBottom: 16 }}
          placeholder="选择子账户"
          value={selectedAccountId}
          onChange={setSelectedAccountId}
          options={accounts.map(a => ({
            label: `${a.name} (${a.parent_name})`,
            value: a.id,
          }))}
        />

        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="持仓总成本"
              value={statistics.holding_cost}
              prefix="¥"
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="持仓总市值"
              value={statistics.holding_value}
              prefix="¥"
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="总盈亏"
              value={statistics.pnl}
              prefix="¥"
              valueStyle={{ color: parseFloat(statistics.pnl) >= 0 ? '#52c41a' : '#ff4d4f' }}
              suffix={statistics.pnl_rate ? `(${formatPercent(statistics.pnl_rate)})` : ''}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="今日盈亏"
              value={statistics.today_pnl}
              prefix="¥"
              valueStyle={{ color: parseFloat(statistics.today_pnl) >= 0 ? '#52c41a' : '#ff4d4f' }}
              suffix={statistics.today_pnl_rate ? `(${formatPercent(statistics.today_pnl_rate)})` : ''}
            />
          </Col>
        </Row>
      </Card>

      <Card title="持仓列表">
        <Radio.Group
          value={fundTypeFilter}
          onChange={(e) => setFundTypeFilter(e.target.value)}
          style={{ marginBottom: 16 }}
        >
          <Radio.Button value="all">全部</Radio.Button>
          <Radio.Button value="股票">股票型</Radio.Button>
          <Radio.Button value="债券">债券型</Radio.Button>
          <Radio.Button value="混合">混合型</Radio.Button>
          <Radio.Button value="货币">货币型</Radio.Button>
          <Radio.Button value="其他">其他</Radio.Button>
        </Radio.Group>

        <Table
          columns={columns}
          dataSource={getFilteredPositions()}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 'max-content' }}
          locale={{ emptyText: '暂无持仓' }}
        />
      </Card>

      <Card title="操作流水" style={{ marginTop: 16 }} extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleOpenModal}
        >
          添加操作
        </Button>
      }>
        <Table
          columns={operationColumns}
          dataSource={operations}
          rowKey="id"
          loading={operationsLoading}
          pagination={false}
          scroll={{ x: 'max-content' }}
          locale={{ emptyText: '暂无操作记录' }}
        />
      </Card>

      <Modal
        title="添加操作"
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="确定"
        cancelText="取消"
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            before_15: 'before',
          }}
        >
          <Form.Item label="操作类型">
            <Radio.Group value={operationType} onChange={(e) => setOperationType(e.target.value)}>
              <Radio.Button value="BUY">买入</Radio.Button>
              <Radio.Button value="SELL">卖出</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            label="基金代码"
            name="fund_code"
            rules={[{ required: true, message: '请输入基金代码' }]}
          >
            <AutoComplete
              options={fundOptions}
              onSearch={handleFundSearch}
              onSelect={handleFundSelect}
              placeholder="请输入基金代码或名称搜索"
              loading={searchLoading}
            />
          </Form.Item>

          <Form.Item
            label="操作日期"
            name="operation_date"
            rules={[{ required: true, message: '请选择操作日期' }]}
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="操作时间"
            name="before_15"
            rules={[{ required: true, message: '请选择操作时间' }]}
          >
            <Radio.Group>
              <Radio value="before">15:00前</Radio>
              <Radio value="after">15:00后</Radio>
            </Radio.Group>
          </Form.Item>

          {operationType === 'BUY' && (
            <>
              <Form.Item label="建仓方式">
                <Radio.Group value={buildPositionMode} onChange={(e) => setBuildPositionMode(e.target.value)}>
                  <Radio.Button value="value">持有市值 + 收益率</Radio.Button>
                  <Radio.Button value="nav">净值 + 份额</Radio.Button>
                </Radio.Group>
              </Form.Item>

              {buildPositionMode === 'value' ? (
                <>
                  <Form.Item
                    label="持有市值"
                    name="holding_value"
                    rules={[{ required: true, message: '请输入持有市值' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="请输入持有市值"
                      min={0}
                      onChange={handleValueModeCalculate}
                    />
                  </Form.Item>

                  <Form.Item
                    label="收益率 (%)"
                    name="pnl_rate"
                    rules={[{ required: true, message: '请输入收益率' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="请输入收益率"
                      onChange={handleValueModeCalculate}
                    />
                  </Form.Item>
                </>
              ) : (
                <>
                  <Form.Item
                    label="净值"
                    name="nav"
                    rules={[{ required: true, message: '请输入净值' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="请输入净值"
                      min={0}
                      onChange={handleNavModeCalculate}
                    />
                  </Form.Item>

                  <Form.Item
                    label="份额"
                    name="share"
                    rules={[{ required: true, message: '请输入份额' }]}
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="请输入份额"
                      min={0}
                      onChange={handleNavModeCalculate}
                    />
                  </Form.Item>
                </>
              )}

              <Form.Item
                label="金额（自动计算）"
                name="amount"
                rules={[{ required: true, message: '请输入金额' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  min={0}
                  disabled={buildPositionMode === 'value'}
                />
              </Form.Item>

              {buildPositionMode === 'value' && (
                <>
                  <Form.Item
                    label="份额（自动计算）"
                    name="share"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="自动计算"
                      disabled
                    />
                  </Form.Item>

                  <Form.Item
                    label="净值（自动计算）"
                    name="nav"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="自动计算"
                      disabled
                    />
                  </Form.Item>
                </>
              )}
            </>
          )}

          {operationType === 'SELL' && (
            <>
              <Form.Item
                label="份额"
                name="share"
                rules={[{ required: true, message: '请输入份额' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入份额"
                  min={0}
                  onChange={handleSellCalculate}
                />
              </Form.Item>

              <Form.Item
                label="净值"
                name="nav"
                rules={[{ required: true, message: '请输入净值' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入净值"
                  min={0}
                  onChange={handleSellCalculate}
                />
              </Form.Item>

              <Form.Item
                label="金额（自动计算）"
                name="amount"
                rules={[{ required: true, message: '请输入金额' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  min={0}
                  disabled
                />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default PositionsPage;
