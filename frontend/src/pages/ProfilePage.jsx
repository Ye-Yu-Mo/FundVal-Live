import { useNavigate } from 'react-router-dom';
import { Card, Space, Button } from 'antd';
import { AccountBookOutlined, SettingOutlined, UserOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

const ProfilePage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const items = [
    { key: 'accounts', icon: <AccountBookOutlined />, title: '账户管理', desc: '管理我的账户和持仓', path: '/dashboard/accounts' },
    { key: 'settings', icon: <SettingOutlined />, title: '系统设置', desc: '数据源、AI配置、通知渠道', path: '/dashboard/settings' },
    ...(user?.role === 'admin' ? [{ key: 'admin', icon: <UserOutlined />, title: '用户管理', desc: '管理员面板', path: '/dashboard/admin' }] : []),
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Card>
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <UserOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 8 }} />
          <div style={{ fontSize: 18, fontWeight: 'bold' }}>{user?.username}</div>
          <div style={{ color: '#999', fontSize: 13 }}>{user?.role === 'admin' ? '管理员' : '用户'}</div>
        </div>
      </Card>
      {items.map(item => (
        <Card key={item.key} hoverable onClick={() => navigate(item.path)} style={{ cursor: 'pointer' }}>
          <Space>
            <span style={{ fontSize: 24, color: '#1890ff' }}>{item.icon}</span>
            <div>
              <div style={{ fontWeight: 500 }}>{item.title}</div>
              <div style={{ fontSize: 12, color: '#999' }}>{item.desc}</div>
            </div>
          </Space>
        </Card>
      ))}
    </Space>
  );
};

export default ProfilePage;
