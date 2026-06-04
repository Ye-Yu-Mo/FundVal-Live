import { useState, useEffect } from 'react';
import { Card, Table, Button, Input, Tag, message, Modal, Space, Typography } from 'antd';
import { SearchOutlined, ReloadOutlined, LockOutlined, StopOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { adminAPI } from '../api';

const { Text } = Typography;

const AdminPage = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [passwordModal, setPasswordModal] = useState({ open: false, password: '', username: '' });

  const loadUsers = async (pageNum = 1, searchTerm = '') => {
    setLoading(true);
    try {
      const params = { page: pageNum, page_size: 20 };
      if (searchTerm) params.search = searchTerm;
      const { data } = await adminAPI.listUsers(params);
      setUsers(data.results);
      setTotal(data.count);
    } catch (err) {
      message.error('加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const handleToggle = async (user) => {
    const action = user.is_active ? '禁用' : '启用';
    Modal.confirm({
      title: `确定${action}用户「${user.username}」？`,
      onOk: async () => {
        try {
          const { data } = await adminAPI.toggleUser(user.id);
          setUsers(prev => prev.map(u =>
            u.id === user.id ? { ...u, is_active: data.is_active } : u
          ));
          message.success(`${action}成功`);
        } catch { message.error(`${action}失败`); }
      },
    });
  };

  const handleResetPassword = async (user) => {
    Modal.confirm({
      title: `确定重置「${user.username}」的密码？`,
      content: '重置后将生成新密码，请妥善保存。',
      onOk: async () => {
        try {
          const { data } = await adminAPI.resetPassword(user.id);
          setPasswordModal({
            open: true,
            password: data.new_password,
            username: user.username,
          });
        } catch { message.error('重置密码失败'); }
      },
    });
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username', width: 150 },
    { title: '邮箱', dataIndex: 'email', key: 'email', width: 250, render: v => v || '-' },
    {
      title: '角色', dataIndex: 'role', key: 'role', width: 80,
      render: role => <Tag color={role === 'admin' ? 'red' : 'blue'}>{role === 'admin' ? '管理员' : '用户'}</Tag>,
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80,
      render: v => <Tag color={v ? 'green' : 'red'}>{v ? '正常' : '已禁用'}</Tag>,
    },
    {
      title: '注册时间', dataIndex: 'date_joined', key: 'date_joined', width: 180,
      render: v => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作', key: 'action', width: 200, fixed: 'right',
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={record.is_active ? <StopOutlined /> : <CheckCircleOutlined />}
            danger={record.is_active}
            onClick={() => handleToggle(record)}
          >
            {record.is_active ? '禁用' : '启用'}
          </Button>
          <Button size="small" icon={<LockOutlined />} onClick={() => handleResetPassword(record)}>
            重置密码
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="用户管理"
        extra={
          <Space>
            <Input.Search
              placeholder="搜索用户名"
              allowClear
              value={search}
              onChange={e => setSearch(e.target.value)}
              onSearch={val => { setPage(1); loadUsers(1, val); }}
              style={{ width: 200 }}
              prefix={<SearchOutlined />}
            />
            <Button icon={<ReloadOutlined />} onClick={() => loadUsers(page, search)}>刷新</Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            showSizeChanger: false,
            showTotal: t => `共 ${t} 个用户`,
            onChange: p => { setPage(p); loadUsers(p, search); },
          }}
          scroll={{ x: 'max-content' }}
        />
      </Card>

      <Modal
        title="密码已重置"
        open={passwordModal.open}
        onOk={() => setPasswordModal({ open: false, password: '', username: '' })}
        onCancel={() => setPasswordModal({ open: false, password: '', username: '' })}
        okText="已保存"
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        <p>用户 <Text strong>{passwordModal.username}</Text> 的密码已重置为：</p>
        <Input.Password
          value={passwordModal.password}
          readOnly
          style={{ marginTop: 8 }}
        />
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          请立即告知用户，此密码仅显示一次。
        </Text>
      </Modal>
    </>
  );
};

export default AdminPage;
