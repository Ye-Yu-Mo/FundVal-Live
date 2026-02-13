import { useState, useEffect } from 'react';
import { Form, Input, Button, Card, message, Typography, Layout, theme, Modal } from 'antd';
import { UserOutlined, LockOutlined, LoginOutlined, CloudServerOutlined, SettingOutlined } from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import { login } from '../api';
import { setToken } from '../utils/auth';
import { useAuth } from '../contexts/AuthContext';
import { isNativeApp } from '../App';

const { Title, Text } = Typography;
const { Content, Footer } = Layout;

function LoginPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [serverModalVisible, setServerModalVisible] = useState(false);
  const [serverUrl, setServerUrl] = useState(localStorage.getItem('apiBaseUrl') || '');
  const [testingConnection, setTestingConnection] = useState(false);
  const [isNative, setIsNative] = useState(isNativeApp());
  const { token } = theme.useToken();
  const { login: authLogin } = useAuth();

  // 检查是否是 native app（延迟检查以防 Tauri API 延迟加载）
  useEffect(() => {
    const checkNative = () => {
      const native = isNativeApp();
      setIsNative(native);
      console.log('isNativeApp:', native);
    };

    checkNative();

    // 延迟再检查一次，以防 Tauri API 还没加载
    const timer = setTimeout(checkNative, 100);
    return () => clearTimeout(timer);
  }, []);

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const response = await login(values.username, values.password);
      const { access_token, refresh_token, user } = response.data;

      setToken(access_token, refresh_token);
      authLogin(user);
      message.success(`欢迎回来，${user.username}！`);

      navigate('/dashboard');
    } catch (error) {
      message.error(error.response?.data?.error || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleServerConfig = async () => {
    if (!serverUrl.trim()) {
      message.error('请输入服务器地址');
      return;
    }

    if (!serverUrl.startsWith('http://') && !serverUrl.startsWith('https://')) {
      message.error('服务器地址必须以 http:// 或 https:// 开头');
      return;
    }

    setTestingConnection(true);
    try {
      const response = await fetch(`${serverUrl}/api/health/`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        localStorage.setItem('apiBaseUrl', serverUrl);
        message.success('服务器配置成功！');
        setServerModalVisible(false);
        // 刷新页面以应用新配置
        window.location.reload();
      } else {
        message.error('无法连接到服务器，请检查地址是否正确');
      }
    } catch (error) {
      message.error(`连接失败: ${error.message}`);
    } finally {
      setTestingConnection(false);
    }
  };

  const layoutStyle = {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    background: '#f0f2f5',
  };

  const cardStyle = {
    width: '100%',
    maxWidth: 450,
    margin: '0 auto',
    borderRadius: token.borderRadiusLG,
    boxShadow: '0 10px 25px rgba(0,0,0,0.08)',
  };

  const logoBoxStyle = {
    width: 48,
    height: 48,
    background: token.colorPrimary,
    borderRadius: 12,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    boxShadow: `0 4px 12px ${token.colorPrimary}40`,
  };

  return (
    <Layout style={layoutStyle}>
      <Content style={{ padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>

        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <div style={logoBoxStyle}>
              <CloudServerOutlined style={{ fontSize: 24, color: '#fff' }} />
            </div>
          </div>
          <Title level={2} style={{ marginBottom: 0 }}>Fundval</Title>
          <Text type="secondary">基金估值与资产管理系统</Text>
        </div>

        <Card style={cardStyle} styles={{ body: { padding: 40 } }}>
          {isNative && (
            <div style={{ marginBottom: 16, textAlign: 'right' }}>
              <Button
                type="text"
                size="small"
                icon={<SettingOutlined />}
                onClick={() => setServerModalVisible(true)}
              >
                服务器配置
              </Button>
            </div>
          )}

          <Form
            name="login"
            onFinish={onFinish}
            autoComplete="off"
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                prefix={<UserOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
                placeholder="用户名"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
                placeholder="密码"
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 16 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                icon={<LoginOutlined />}
              >
                登录
              </Button>
            </Form.Item>

            <div style={{ textAlign: 'center' }}>
              <Text type="secondary">
                还没有账号？ <Link to="/register">立即注册</Link>
              </Text>
            </div>
          </Form>
        </Card>
      </Content>

      <Footer style={{ textAlign: 'center', background: 'transparent' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>&copy; 2026 Fundval. All rights reserved.</Text>
      </Footer>

      {/* 服务器配置弹窗 */}
      <Modal
        title="服务器配置"
        open={serverModalVisible}
        onOk={handleServerConfig}
        onCancel={() => setServerModalVisible(false)}
        confirmLoading={testingConnection}
        okText="保存"
        cancelText="取消"
      >
        <Form layout="vertical">
          <Form.Item
            label="服务器地址"
            extra="例如: http://192.168.1.100:8000 或 https://fundval.example.com"
          >
            <Input
              prefix={<CloudServerOutlined />}
              placeholder="http://your-server:8000"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
}

export default LoginPage;
