import { useState, useEffect } from 'react';
import { Form, Input, Button, Card, message, Typography, Layout, theme } from 'antd';
import { CloudServerOutlined, SaveOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { Content } = Layout;

function ServerConfigPage({ onConfigSaved }) {
  const [loading, setLoading] = useState(false);
  const { token } = theme.useToken();
  const [form] = Form.useForm();

  useEffect(() => {
    // 检查是否已有配置
    const savedUrl = localStorage.getItem('apiBaseUrl');
    if (savedUrl) {
      form.setFieldsValue({ serverUrl: savedUrl });
    }
  }, [form]);

  const onFinish = async (values) => {
    setLoading(true);
    try {
      // 验证 URL 格式
      const url = values.serverUrl.trim();
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        message.error('服务器地址必须以 http:// 或 https:// 开头');
        setLoading(false);
        return;
      }

      // 测试连接
      const response = await fetch(`${url}/api/health/`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        localStorage.setItem('apiBaseUrl', url);
        message.success('服务器配置成功！');
        if (onConfigSaved) {
          onConfigSaved(url);
        }
      } else {
        message.error('无法连接到服务器，请检查地址是否正确');
      }
    } catch (error) {
      message.error(`连接失败: ${error.message}`);
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
    maxWidth: 500,
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
          <Title level={2} style={{ marginBottom: 8 }}>服务器配置</Title>
          <Text type="secondary">请输入 Fundval 服务器地址</Text>
        </div>

        <Card style={cardStyle} styles={{ body: { padding: 40 } }}>
          <Form
            form={form}
            name="server_config"
            onFinish={onFinish}
            autoComplete="off"
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="serverUrl"
              label="服务器地址"
              rules={[
                { required: true, message: '请输入服务器地址' },
                { type: 'url', message: '请输入有效的 URL' }
              ]}
              extra="例如: http://192.168.1.100:8000 或 https://fundval.example.com"
            >
              <Input
                prefix={<CloudServerOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
                placeholder="http://your-server:8000"
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                icon={<SaveOutlined />}
              >
                保存配置
              </Button>
            </Form.Item>
          </Form>

          <div style={{ marginTop: 24, padding: 16, background: '#f5f5f5', borderRadius: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <strong>提示：</strong>
              <br />
              • 确保服务器已启动并可访问
              <br />
              • 如果使用局域网，请使用服务器的 IP 地址
              <br />
              • 如果使用域名，请确保 DNS 解析正确
            </Text>
          </div>
        </Card>
      </Content>
    </Layout>
  );
}

export default ServerConfigPage;
