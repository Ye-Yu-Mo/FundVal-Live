import { useState } from 'react';
import { Form, Input, Button, Card, message, Typography, Layout, theme } from 'antd';
import { UserOutlined, LockOutlined, UserAddOutlined, CloudServerOutlined } from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import { register } from '../api';
import { setToken } from '../utils/auth';
import { useAuth } from '../contexts/AuthContext';

const { Title, Text } = Typography;
const { Content, Footer } = Layout;

function RegisterPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const { token } = theme.useToken();
  const { login: authLogin } = useAuth();

  const onFinish = async (values) => {
    setLoading(true);
    try {
      const response = await register(values.username, values.password, values.password_confirm);
      const { access_token, refresh_token, user } = response.data;

      setToken(access_token, refresh_token);
      authLogin(user);
      message.success(`注册成功，欢迎 ${user.username}！`);

      navigate('/dashboard');
    } catch (error) {
      const errorMsg = error.response?.data?.error ||
                       error.response?.data?.username?.[0] ||
                       error.response?.data?.password?.[0] ||
                       error.response?.data?.password_confirm?.[0] ||
                       '注册失败';
      message.error(errorMsg);
    } finally {
      setLoading(false);
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
          <Form
            name="register"
            onFinish={onFinish}
            autoComplete="off"
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="username"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 3, message: '用户名至少 3 个字符' },
                { max: 150, message: '用户名最多 150 个字符' }
              ]}
            >
              <Input
                prefix={<UserOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
                placeholder="用户名"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 8, message: '密码至少 8 个字符' }
              ]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
                placeholder="密码"
              />
            </Form.Item>

            <Form.Item
              name="password_confirm"
              dependencies={['password']}
              rules={[
                { required: true, message: '请确认密码' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('password') === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error('两次密码不一致'));
                  },
                }),
              ]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
                placeholder="确认密码"
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 16 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                icon={<UserAddOutlined />}
              >
                注册
              </Button>
            </Form.Item>

            <div style={{ textAlign: 'center' }}>
              <Text type="secondary">
                已有账号？ <Link to="/login">立即登录</Link>
              </Text>
            </div>
          </Form>
        </Card>
      </Content>

      <Footer style={{ textAlign: 'center', background: 'transparent' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>&copy; 2026 Fundval. All rights reserved.</Text>
      </Footer>
    </Layout>
  );
}

export default RegisterPage;

