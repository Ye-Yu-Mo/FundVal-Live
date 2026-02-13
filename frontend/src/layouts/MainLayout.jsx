import { Layout, Menu, Dropdown, Space, Grid } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  FundOutlined,
  AccountBookOutlined,
  PieChartOutlined,
  StarOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

const MainLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const screens = useBreakpoint();

  // 判断是否为移动端（< 768px）
  const isMobile = !screens.md;

  const menuItems = [
    {
      key: '/dashboard/watchlists',
      icon: <StarOutlined />,
      label: isMobile ? '自选' : '自选列表',
    },
    {
      key: '/dashboard/positions',
      icon: <PieChartOutlined />,
      label: isMobile ? '持仓' : '持仓查询',
    },
    {
      key: '/dashboard/accounts',
      icon: <AccountBookOutlined />,
      label: isMobile ? '账户' : '账户管理',
    },
    {
      key: '/dashboard/funds',
      icon: <FundOutlined />,
      label: isMobile ? '基金' : '基金查询',
    },
    {
      key: '/dashboard/settings',
      icon: <SettingOutlined />,
      label: isMobile ? '设置' : '系统设置',
    },
  ];

  const handleMenuClick = ({ key }) => {
    navigate(key);
  };

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  // 移动端布局
  if (isMobile) {
    return (
      <Layout style={{ minHeight: '100vh' }}>
        {/* 顶部导航栏 */}
        <Header
          style={{
            background: '#fff',
            padding: '0 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid #f0f0f0',
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 1000,
            height: 56,
            lineHeight: '56px',
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 'bold' }}>Fundval</div>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <UserOutlined />
              <span>{user?.username}</span>
            </Space>
          </Dropdown>
        </Header>

        {/* 内容区 */}
        <Content
          style={{
            marginTop: 56,
            marginBottom: 56,
            padding: 12,
            background: '#f0f2f5',
            minHeight: 'calc(100vh - 112px)',
          }}
        >
          {children}
        </Content>

        {/* 底部导航栏 */}
        <div
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            background: '#fff',
            borderTop: '1px solid #f0f0f0',
            zIndex: 1000,
            height: 56,
          }}
        >
          <Menu
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={handleMenuClick}
            style={{
              display: 'flex',
              justifyContent: 'space-around',
              border: 'none',
              lineHeight: '56px',
            }}
          />
        </div>
      </Layout>
    );
  }

  // 桌面端布局
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={200}
        theme="light"
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          overflow: 'auto',
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
            fontSize: 16,
            fontWeight: 'bold',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <FundOutlined style={{ fontSize: 24, color: '#1890ff', marginRight: 12 }} />
          <span>Fundval</span>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout style={{ marginLeft: 200 }}>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            borderBottom: '1px solid #f0f0f0',
            position: 'fixed',
            top: 0,
            right: 0,
            left: 200,
            zIndex: 999,
          }}
        >
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <UserOutlined />
              <span>{user?.username}</span>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ marginTop: 64, padding: 24, background: '#f0f2f5', minHeight: 'calc(100vh - 64px)' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
