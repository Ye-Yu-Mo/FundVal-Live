import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Checkbox,
  message,
  Popconfirm,
  Tag,
  Statistic,
  Row,
  Col,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { accountsAPI } from '../api';

const AccountsPage = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState('create');
  const [currentAccount, setCurrentAccount] = useState(null);
  const [selectedParentId, setSelectedParentId] = useState(null);
  const [showAllSummary, setShowAllSummary] = useState(false);
  const [form] = Form.useForm();

  // 加载账户列表
  const loadAccounts = async () => {
    setLoading(true);
    try {
      const response = await accountsAPI.list();
      setAccounts(response.data);

      // 自动选中默认父账户
      if (!selectedParentId) {
        const defaultParent = response.data.find(a => a.is_default && !a.parent);
        if (defaultParent) {
          setSelectedParentId(defaultParent.id);
        } else {
          // 如果没有默认父账户，选择第一个父账户
          const firstParent = response.data.find(a => !a.parent);
          if (firstParent) {
            setSelectedParentId(firstParent.id);
          }
        }
      }
    } catch (error) {
      message.error('加载账户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  // 打开创建 Modal
  const handleCreate = () => {
    setModalMode('create');
    setCurrentAccount(null);
    form.resetFields();
    setModalVisible(true);
  };

  // 打开编辑 Modal
  const handleEdit = (account) => {
    setModalMode('edit');
    setCurrentAccount(account);
    form.setFieldsValue({
      name: account.name,
      parent: account.parent,
      is_default: account.is_default,
    });
    setModalVisible(true);
  };

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      if (modalMode === 'create') {
        await accountsAPI.create(values);
        message.success('创建账户成功');
      } else {
        await accountsAPI.update(currentAccount.id, values);
        message.success('更新账户成功');
      }

      setModalVisible(false);
      loadAccounts();
    } catch (error) {
      if (error.errorFields) {
        // 表单验证错误
        return;
      }
      message.error(modalMode === 'create' ? '创建账户失败' : '更新账户失败');
    }
  };

  // 删除账户
  const handleDelete = async (id) => {
    try {
      await accountsAPI.delete(id);
      message.success('删除账户成功');
      loadAccounts();
    } catch (error) {
      message.error('删除账户失败');
    }
  };

  // 获取账户类型显示
  const getAccountType = (account) => {
    if (account.parent) {
      const parentAccount = accounts.find((a) => a.id === account.parent);
      return parentAccount ? `子账户 (${parentAccount.name})` : '子账户';
    }
    return '总账户';
  };

  // 获取可选的父账户列表（排除自己和子账户）
  const getParentOptions = () => {
    if (modalMode === 'create') {
      return accounts.filter((a) => !a.parent);
    }
    // 编辑时，排除自己和自己的子账户
    return accounts.filter(
      (a) => !a.parent && a.id !== currentAccount?.id
    );
  };

  // 获取父账户列表
  const getParentAccounts = () => {
    return accounts.filter(a => !a.parent);
  };

  // 获取当前选中的父账户
  const getSelectedParent = () => {
    if (showAllSummary) return null;
    return accounts.find(a => a.id === selectedParentId);
  };

  // 获取当前显示的子账户列表
  const getChildAccounts = () => {
    const parent = getSelectedParent();
    return parent?.children || [];
  };

  // 计算全部账户汇总
  const getAllAccountsSummary = () => {
    const parents = getParentAccounts();
    return parents.reduce((sum, parent) => ({
      holding_cost: (parseFloat(sum.holding_cost) + parseFloat(parent.holding_cost || 0)).toFixed(2),
      holding_value: (parseFloat(sum.holding_value) + parseFloat(parent.holding_value || 0)).toFixed(2),
      pnl: (parseFloat(sum.pnl) + parseFloat(parent.pnl || 0)).toFixed(2),
      estimate_value: (parseFloat(sum.estimate_value) + parseFloat(parent.estimate_value || 0)).toFixed(2),
      estimate_pnl: (parseFloat(sum.estimate_pnl) + parseFloat(parent.estimate_pnl || 0)).toFixed(2),
      today_pnl: (parseFloat(sum.today_pnl) + parseFloat(parent.today_pnl || 0)).toFixed(2),
    }), {
      holding_cost: '0.00',
      holding_value: '0.00',
      pnl: '0.00',
      estimate_value: '0.00',
      estimate_pnl: '0.00',
      today_pnl: '0.00',
    });
  };

  // 格式化百分比
  const formatPercent = (value) => {
    if (value === null || value === undefined) return '-';
    return `${(parseFloat(value) * 100).toFixed(2)}%`;
  };

  // 格式化金额
  const formatMoney = (value) => {
    if (value === null || value === undefined) return '-';
    return parseFloat(value).toFixed(2);
  };

  const columns = [
    {
      title: '账户名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '持仓成本',
      dataIndex: 'holding_cost',
      key: 'holding_cost',
      render: (value) => formatMoney(value),
    },
    {
      title: '持仓市值',
      dataIndex: 'holding_value',
      key: 'holding_value',
      render: (value) => formatMoney(value),
    },
    {
      title: '总盈亏',
      dataIndex: 'pnl',
      key: 'pnl',
      render: (value) => {
        const num = parseFloat(value);
        return (
          <span style={{ color: num >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {formatMoney(value)}
          </span>
        );
      },
    },
    {
      title: '收益率',
      dataIndex: 'pnl_rate',
      key: 'pnl_rate',
      render: (value) => {
        if (value === null || value === undefined) return '-';
        const num = parseFloat(value);
        return (
          <span style={{ color: num >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {formatPercent(value)}
          </span>
        );
      },
    },
    {
      title: '预估市值',
      dataIndex: 'estimate_value',
      key: 'estimate_value',
      render: (value) => formatMoney(value),
      responsive: ['lg'],
    },
    {
      title: '今日盈亏',
      dataIndex: 'today_pnl',
      key: 'today_pnl',
      render: (value) => {
        if (value === null || value === undefined) return '-';
        const num = parseFloat(value);
        return (
          <span style={{ color: num >= 0 ? '#52c41a' : '#ff4d4f' }}>
            {formatMoney(value)}
          </span>
        );
      },
      responsive: ['md'],
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定要删除账户吗？"
            description="删除后无法恢复"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="账户管理"
      extra={
        <Space>
          <Button
            data-testid="all-accounts-summary-button"
            onClick={() => setShowAllSummary(!showAllSummary)}
          >
            {showAllSummary ? '返回单账户' : '全部账户汇总'}
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreate}
          >
            创建账户
          </Button>
        </Space>
      }
    >
      {!showAllSummary && (
        <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
          <Select
            data-testid="parent-account-selector"
            style={{ width: 300 }}
            placeholder="选择父账户"
            value={selectedParentId}
            onChange={setSelectedParentId}
            options={getParentAccounts().map(a => ({
              label: `${a.name}${a.is_default ? ' (默认)' : ''}`,
              value: a.id,
            }))}
          />
        </Space>
      )}

      {showAllSummary ? (
        <div data-testid="all-accounts-summary">
          <Card title="全部账户汇总" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic title="持仓成本" value={getAllAccountsSummary().holding_cost} prefix="¥" />
              </Col>
              <Col span={6}>
                <Statistic title="持仓市值" value={getAllAccountsSummary().holding_value} prefix="¥" />
              </Col>
              <Col span={6}>
                <Statistic
                  title="总盈亏"
                  value={getAllAccountsSummary().pnl}
                  prefix="¥"
                  valueStyle={{ color: parseFloat(getAllAccountsSummary().pnl) >= 0 ? '#52c41a' : '#ff4d4f' }}
                />
              </Col>
              <Col span={6}>
                <Statistic
                  title="今日盈亏"
                  value={getAllAccountsSummary().today_pnl}
                  prefix="¥"
                  valueStyle={{ color: parseFloat(getAllAccountsSummary().today_pnl) >= 0 ? '#52c41a' : '#ff4d4f' }}
                />
              </Col>
            </Row>
          </Card>

          <Table
            columns={columns.filter(c => c.key !== 'action')}
            dataSource={getParentAccounts()}
            rowKey="id"
            loading={loading}
            pagination={false}
            scroll={{ x: 'max-content' }}
          />
        </div>
      ) : (
        <>
          {getSelectedParent() && (
            <Card
              data-testid="parent-account-summary"
              title={`${getSelectedParent().name} - 汇总`}
              style={{ marginBottom: 16 }}
            >
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic title="持仓成本" value={formatMoney(getSelectedParent().holding_cost)} prefix="¥" />
                </Col>
                <Col span={6}>
                  <Statistic title="持仓市值" value={formatMoney(getSelectedParent().holding_value)} prefix="¥" />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="总盈亏"
                    value={formatMoney(getSelectedParent().pnl)}
                    prefix="¥"
                    valueStyle={{ color: parseFloat(getSelectedParent().pnl) >= 0 ? '#52c41a' : '#ff4d4f' }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic
                    title="收益率"
                    value={formatPercent(getSelectedParent().pnl_rate)}
                    valueStyle={{ color: parseFloat(getSelectedParent().pnl_rate) >= 0 ? '#52c41a' : '#ff4d4f' }}
                  />
                </Col>
              </Row>
            </Card>
          )}

          <div data-testid="child-accounts-list">
            <Table
              columns={columns}
              dataSource={getChildAccounts()}
              rowKey="id"
              loading={loading}
              pagination={false}
              scroll={{ x: 'max-content' }}
              locale={{ emptyText: '暂无子账户' }}
            />
          </div>
        </>
      )}

      <Modal
        title={modalMode === 'create' ? '创建账户' : '编辑账户'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="确定"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            parent: null,
            is_default: false,
          }}
        >
          <Form.Item
            label="账户名称"
            name="name"
            rules={[{ required: true, message: '请输入账户名称' }]}
          >
            <Input placeholder="请输入账户名称" />
          </Form.Item>

          <Form.Item label="父账户" name="parent">
            <Select
              placeholder="选择父账户（可选）"
              allowClear
              options={getParentOptions().map((a) => ({
                label: a.name,
                value: a.id,
              }))}
            />
          </Form.Item>

          <Form.Item name="is_default" valuePropName="checked">
            <Checkbox>设为默认账户</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default AccountsPage;
