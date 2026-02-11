import { useState } from 'react';
import { Form, Input, Button, Card, message, Switch, Steps, Result, Typography, Divider, Layout, Space, theme } from 'antd';
import {
  SafetyCertificateOutlined,
  KeyOutlined,
  UserOutlined,
  CheckCircleOutlined,
  CloudServerOutlined,
  LockOutlined,
  UserAddOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { verifyBootstrapKey, initializeSystem } from '../api';

const { Title, Text, Paragraph } = Typography;
const { Content, Footer } = Layout;

function InitializePage() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [bootstrapKey, setBootstrapKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  const { token } = theme.useToken();

  const onVerifyKey = async (values) => {
    setLoading(true);
    try {
      await verifyBootstrapKey(values.bootstrap_key);
      setBootstrapKey(values.bootstrap_key);
      message.success('密钥验证成功');
      setCurrentStep(1);
    } catch (error) {
      message.error(error.response?.data?.error || '密钥无效');
    } finally {
      setLoading(false);
    }
  };

  const onInitialize = async (values) => {
    setLoading(true);
    try {
      await initializeSystem({
        bootstrap_key: bootstrapKey,
        admin_username: values.admin_username,
        admin_password: values.admin_password,
        allow_register: values.allow_register,
      });
      setCurrentStep(2);
    } catch (error) {
      message.error(error.response?.data?.error || '初始化失败');
    } finally {
      setLoading(false);
    }
  };

  const handleGoLogin = () => {
    navigate('/login');
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
    maxWidth: 600,
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

  const infoBoxStyle = {
    background: token.colorPrimaryBg,
    border: `1px solid ${token.colorPrimaryBorder}`,
    padding: 16,
    borderRadius: token.borderRadius,
    marginBottom: 24,
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
          <Title level={2} style={{ marginBottom: 0 }}>系统初始化</Title>
          <Text type="secondary">请完成必要的配置以启动服务</Text>
        </div>

        <Card style={cardStyle} styles={{ body: { padding: 40 } }}>
          <Steps
            current={currentStep}
            size="small"
            style={{ marginBottom: 40 }}
            className="init-steps"
            items={[
              {
                title: '验证身份',
                icon: <KeyOutlined />,
              },
              {
                title: '管理员配置',
                icon: <UserAddOutlined />,
              },
              {
                title: '完成',
                icon: <CheckCircleOutlined />,
              },
            ]}
          />

          {currentStep === 0 && (
            <div>
              <div style={infoBoxStyle}>
                <Space align="start">
                  <SafetyCertificateOutlined style={{ fontSize: 20, color: token.colorPrimary, marginTop: 4 }} />
                  <div>
                    <Text strong>安全验证</Text>
                    <Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 13 }}>
                      为了确保安全，请输入服务器启动日志中生成的 <b>Bootstrap Key</b>。
                    </Paragraph>
                  </div>
                </Space>
              </div>

              <Form onFinish={onVerifyKey} layout="vertical" size="large">
                <Form.Item
                  name="bootstrap_key"
                  rules={[{ required: true, message: '请输入 Bootstrap Key' }]}
                >
                  <Input.TextArea
                    rows={4}
                    placeholder="请输入密钥..."
                    style={{ resize: 'none', fontFamily: 'monospace' }}
                  />
                </Form.Item>
                <Form.Item style={{ marginBottom: 0 }}>
                  <Button type="primary" htmlType="submit" loading={loading} block size="large" icon={<CheckCircleOutlined />}>
                    验证并继续
                  </Button>
                </Form.Item>
              </Form>
            </div>
          )}

          {currentStep === 1 && (
            <div>
              <Form
                form={form}
                onFinish={onInitialize}
                layout="vertical"
                initialValues={{ allow_register: false }}
                size="large"
              >
                <Form.Item
                  label="管理员用户名"
                  name="admin_username"
                  rules={[{ required: true, message: '请设置管理员用户名' }]}
                >
                  <Input prefix={<UserOutlined style={{ color: 'rgba(0,0,0,.25)' }} />} placeholder="例如: admin" />
                </Form.Item>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <Form.Item
                    label="设置密码"
                    name="admin_password"
                    rules={[
                      { required: true, message: '请设置密码' },
                      { min: 8, message: '密码至少 8 位' },
                    ]}
                  >
                    <Input.Password prefix={<LockOutlined style={{ color: 'rgba(0,0,0,.25)' }} />} placeholder="至少 8 位" />
                  </Form.Item>

                  <Form.Item
                    label="确认密码"
                    name="confirm_password"
                    dependencies={['admin_password']}
                    rules={[
                      { required: true, message: '请确认密码' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('admin_password') === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error('两次输入的密码不一致'));
                        },
                      }),
                    ]}
                  >
                    <Input.Password prefix={<LockOutlined style={{ color: 'rgba(0,0,0,.25)' }} />} placeholder="重复密码" />
                  </Form.Item>
                </div>

                <Divider style={{ margin: '12px 0 24px' }} />

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, padding: 12, background: '#fafafa', borderRadius: token.borderRadius }}>
                  <div>
                    <div style={{ fontWeight: 500 }}>开放注册</div>
                    <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>是否允许其他人注册账户</div>
                  </div>
                  <Form.Item
                    name="allow_register"
                    valuePropName="checked"
                    noStyle
                  >
                    <Switch />
                  </Form.Item>
                </div>

                <Form.Item style={{ marginBottom: 0 }}>
                  <Button type="primary" htmlType="submit" loading={loading} block size="large">
                    完成初始化
                  </Button>
                </Form.Item>
              </Form>
            </div>
          )}

          {currentStep === 2 && (
            <Result
              status="success"
              title="系统初始化成功！"
              subTitle="管理员账户已创建，您可以开始配置您的服务了。"
              extra={[
                <Button type="primary" key="login" onClick={handleGoLogin} block size="large">
                  前往登录页
                </Button>,
              ]}
            />
          )}
        </Card>
      </Content>

      <Footer style={{ textAlign: 'center', background: 'transparent' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>&copy; 2026 Fundval. All rights reserved.</Text>
      </Footer>
    </Layout>
  );
}

export default InitializePage;
