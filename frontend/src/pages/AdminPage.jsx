import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Input,
  Tag,
  message,
  Modal,
  Space,
  Typography,
  Row,
  Col,
  Statistic,
  List,
  Grid,
} from 'antd';
import {
  SearchOutlined,
  ReloadOutlined,
  LockOutlined,
  StopOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  BarChartOutlined,
  UserOutlined,
  MailOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { adminAPI } from '../api';

const { Text } = Typography;
const { useBreakpoint } = Grid;

const AdminPage = () => {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [passwordModal, setPasswordModal] = useState({ open: false, password: '', username: '' });
  const [stats, setStats] = useState(null);
  const [taskLoading, setTaskLoading] = useState({});

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

  useEffect(() => {
    loadUsers();
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const { data } = await adminAPI.getStats();
      setStats(data);
    } catch {
      /* stats 加载失败不影响用户列表 */
    }
  };

  const handleTriggerTask = async (taskName, label) => {
    setTaskLoading((prev) => ({ ...prev, [taskName]: true }));
    try {
      await adminAPI.triggerTask(taskName);
      message.success(`${label}已触发`);
    } catch (err) {
      message.error(`${label}触发失败: ${err.response?.data?.error || '未知错误'}`);
    } finally {
      setTaskLoading((prev) => ({ ...prev, [taskName]: false }));
    }
  };

  const handleToggle = async (user) => {
    const action = user.is_active ? '禁用' : '启用';
    Modal.confirm({
      title: `确定${action}用户「${user.username}」？`,
      onOk: async () => {
        try {
          const { data } = await adminAPI.toggleUser(user.id);
          setUsers((prev) =>
            prev.map((u) => (u.id === user.id ? { ...u, is_active: data.is_active } : u))
          );
          message.success(`${action}成功`);
        } catch {
          message.error(`${action}失败`);
        }
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
        } catch {
          message.error('重置密码失败');
        }
      },
    });
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username', width: 150 },
    { title: '邮箱', dataIndex: 'email', key: 'email', width: 250, render: (v) => v || '-' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 80,
      render: (role) => (
        <Tag color={role === 'admin' ? 'red' : 'blue'}>{role === 'admin' ? '管理员' : '用户'}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v) => <Tag color={v ? 'green' : 'red'}>{v ? '正常' : '已禁用'}</Tag>,
    },
    {
      title: '注册时间',
      dataIndex: 'date_joined',
      key: 'date_joined',
      width: 180,
      render: (v) => (v ? new Date(v).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
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
      {stats && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col xs={12} sm={6}>
              <Statistic title="用户总数" value={stats.user_count} prefix={<BarChartOutlined />} />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic title="基金总数" value={stats.fund_count} />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic title="持仓总数" value={stats.position_count} />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic
                title="最新估值"
                value={
                  stats.latest_estimate_time
                    ? new Date(stats.latest_estimate_time).toLocaleTimeString('zh-CN')
                    : '无数据'
                }
              />
            </Col>
          </Row>
          <Space wrap style={{ marginTop: 12 }}>
            <Button
              icon={<SyncOutlined />}
              loading={taskLoading.update_fund_nav}
              onClick={() => handleTriggerTask('update_fund_nav', '同步全部净值')}
            >
              同步全部净值
            </Button>
            <Button
              icon={<SyncOutlined />}
              loading={taskLoading.update_fund_today_nav}
              onClick={() => handleTriggerTask('update_fund_today_nav', '同步当日净值')}
            >
              同步当日净值
            </Button>
            <Button
              loading={taskLoading.recalculate_positions}
              onClick={() => handleTriggerTask('recalculate_positions', '重算全部持仓')}
            >
              重算全部持仓
            </Button>
          </Space>
        </Card>
      )}

      <Card
        title="用户管理"
        extra={
          isMobile ? null : (
            <Space>
              <Input.Search
                placeholder="搜索用户名"
                allowClear
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onSearch={(val) => {
                  setPage(1);
                  loadUsers(1, val);
                }}
                style={{ width: 200 }}
                prefix={<SearchOutlined />}
              />
              <Button icon={<ReloadOutlined />} onClick={() => loadUsers(page, search)}>
                刷新
              </Button>
            </Space>
          )
        }
      >
        {isMobile && (
          <Space style={{ marginBottom: 12, width: '100%' }} direction="vertical">
            <Input.Search
              placeholder="搜索用户名"
              allowClear
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onSearch={(val) => {
                setPage(1);
                loadUsers(1, val);
              }}
              prefix={<SearchOutlined />}
            />
          </Space>
        )}
        {isMobile ? (
          <List
            dataSource={users}
            loading={loading}
            pagination={{
              current: page,
              total,
              pageSize: 20,
              showSizeChanger: false,
              onChange: (p) => {
                setPage(p);
                loadUsers(p, search);
              },
            }}
            renderItem={(user) => (
              <Card size="small" style={{ marginBottom: 8 }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>
                      {user.username}
                      <Tag color={user.role === 'admin' ? 'red' : 'blue'} style={{ marginLeft: 8 }}>
                        {user.role === 'admin' ? '管理员' : '用户'}
                      </Tag>
                      <Tag color={user.is_active ? 'green' : 'red'}>
                        {user.is_active ? '正常' : '已禁用'}
                      </Tag>
                    </div>
                    <div style={{ color: '#999', fontSize: 12 }}>
                      <MailOutlined style={{ marginRight: 4 }} />
                      {user.email || '无邮箱'}
                    </div>
                    <div style={{ color: '#999', fontSize: 12, marginTop: 2 }}>
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      {user.date_joined
                        ? new Date(user.date_joined).toLocaleDateString('zh-CN')
                        : '-'}
                    </div>
                  </div>
                  <Space direction="vertical" size="small">
                    <Button
                      size="small"
                      icon={user.is_active ? <StopOutlined /> : <CheckCircleOutlined />}
                      danger={user.is_active}
                      onClick={() => handleToggle(user)}
                      block
                    >
                      {user.is_active ? '禁用' : '启用'}
                    </Button>
                    <Button
                      size="small"
                      icon={<LockOutlined />}
                      onClick={() => handleResetPassword(user)}
                      block
                    >
                      重置密码
                    </Button>
                  </Space>
                </div>
              </Card>
            )}
          />
        ) : (
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
              showTotal: (t) => `共 ${t} 个用户`,
              onChange: (p) => {
                setPage(p);
                loadUsers(p, search);
              },
            }}
            scroll={{ x: 'max-content' }}
          />
        )}
      </Card>

      <Modal
        title="密码已重置"
        open={passwordModal.open}
        onOk={() => setPasswordModal({ open: false, password: '', username: '' })}
        onCancel={() => setPasswordModal({ open: false, password: '', username: '' })}
        okText="已保存"
        cancelButtonProps={{ style: { display: 'none' } }}
      >
        <p>
          用户 <Text strong>{passwordModal.username}</Text> 的密码已重置为：
        </p>
        <Input.Password value={passwordModal.password} readOnly style={{ marginTop: 8 }} />
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          请立即告知用户，此密码仅显示一次。
        </Text>
      </Modal>
    </>
  );
};

export default AdminPage;
