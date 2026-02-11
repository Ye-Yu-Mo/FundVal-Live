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
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { accountsAPI } from '../api';

const AccountsPage = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState('create');
  const [currentAccount, setCurrentAccount] = useState(null);
  const [form] = Form.useForm();

  // 加载账户列表
  const loadAccounts = async () => {
    setLoading(true);
    try {
      const response = await accountsAPI.list();
      setAccounts(response.data);
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

  const columns = [
    {
      title: '账户名称',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => (
        <Space>
          {name}
          {record.is_default && <Tag color="blue">默认</Tag>}
        </Space>
      ),
    },
    {
      title: '类型',
      key: 'type',
      responsive: ['md'],
      render: (_, record) => getAccountType(record),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      responsive: ['lg'],
      render: (time) => new Date(time).toLocaleDateString(),
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
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreate}
        >
          创建账户
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={accounts}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 'max-content' }}
      />

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
