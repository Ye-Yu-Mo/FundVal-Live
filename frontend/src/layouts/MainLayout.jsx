import { Layout, Menu, Dropdown, Space, Grid, theme } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  FundOutlined,
  SunOutlined,
  MoonOutlined,
  AccountBookOutlined,
  PieChartOutlined,
  StarOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
  GithubOutlined,
  RadarChartOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { usePreference } from '../contexts/PreferenceContext';
import Footer from '../components/Footer';

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

const MainLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { themeMode, updateThemeMode } = usePreference();
  const screens = useBreakpoint();
  const { token } = theme.useToken();

  // 判断是否为移动端（< 768px）
  const isMobile = !screens.md;

  const desktopMenuItems = [
    { key: '/dashboard/watchlists', icon: <StarOutlined />, label: '自选列表' },
    { key: '/dashboard/market', icon: <FundOutlined />, label: '行情中心' },
    { key: '/dashboard/positions', icon: <PieChartOutlined />, label: '持仓查询' },
    { key: '/dashboard/compare', icon: <RadarChartOutlined />, label: '基金对比' },
    { key: '/dashboard/accounts', icon: <AccountBookOutlined />, label: '账户管理' },
    { key: '/dashboard/settings', icon: <SettingOutlined />, label: '系统设置' },
    ...(user?.role === 'admin' ? [{ key: '/dashboard/admin', icon: <UserOutlined />, label: '用户管理' }] : []),
  ];
  const mobileMenuItems = [
    { key: '/dashboard/watchlists', icon: <StarOutlined />, label: '自选' },
    { key: '/dashboard/market', icon: <FundOutlined />, label: '行情' },
    { key: '/dashboard/positions', icon: <PieChartOutlined />, label: '持仓' },
    { key: '/dashboard/compare', icon: <RadarChartOutlined />, label: '对比' },
    { key: '/dashboard/profile', icon: <UserOutlined />, label: '我的' },
  ];
  const menuItems = isMobile ? mobileMenuItems : desktopMenuItems;

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
            background: token.colorBgContainer,
            padding: '0 16px',
            paddingTop: 'env(safe-area-inset-top)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 1000,
            height: 'calc(56px + env(safe-area-inset-top))',
          }}
        >
          <div style={{ fontSize: 16, fontWeight: 'bold' }}>Fundval</div>
          <Space>
            <a
              href="https://github.com/Ye-Yu-Mo/FundVal-Live"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'inherit', fontSize: 18 }}
            >
              <GithubOutlined />
            </a>
            <span
              onClick={() => updateThemeMode(themeMode === 'dark' ? 'light' : 'dark')}
              style={{ cursor: 'pointer', fontSize: 18 }}
            >
              {themeMode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
            </span>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <UserOutlined />
                <span>{user?.username}</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>

        {/* 内容区 */}
        <Content
          style={{
            marginTop: 'calc(56px + env(safe-area-inset-top))',
            marginBottom: 'calc(56px + env(safe-area-inset-bottom))',
            padding: 12,
            background: token.colorBgLayout,
            minHeight: 'calc(100vh - 112px - env(safe-area-inset-top) - env(safe-area-inset-bottom))',
          }}
        >
          {children}
          <Footer />
        </Content>

        {/* 底部导航栏 */}
        <div
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            background: token.colorBgContainer,
            borderTop: `1px solid ${token.colorBorderSecondary}`,
            zIndex: 1000,
            height: 'calc(56px + env(safe-area-inset-bottom))',
            paddingBottom: 'env(safe-area-inset-bottom)',
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
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <FundOutlined style={{ fontSize: 24, color: token.colorPrimary, marginRight: 12 }} />
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
            background: token.colorBgContainer,
            padding: '0 24px',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            position: 'fixed',
            top: 0,
            right: 0,
            left: 200,
            zIndex: 999,
          }}
        >
          <Space>
            <a
              href="https://github.com/Ye-Yu-Mo/FundVal-Live"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'inherit', fontSize: 18 }}
            >
              <GithubOutlined />
            </a>
            <span
              onClick={() => updateThemeMode(themeMode === 'dark' ? 'light' : 'dark')}
              style={{ cursor: 'pointer', fontSize: 18 }}
            >
              {themeMode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
            </span>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <UserOutlined />
                <span>{user?.username}</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content style={{ marginTop: 64, padding: 24, background: token.colorBgLayout, minHeight: 'calc(100vh - 64px)' }}>
          {children}
        </Content>
        <Footer />
      </Layout>
    </Layout>
  );
};

export default MainLayout;
