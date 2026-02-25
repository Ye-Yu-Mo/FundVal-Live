import { useState, useEffect, useRef } from 'react';
import { Card, Form, Input, Button, message, Space, Divider, Tag, Image, Spin } from 'antd';
import {
  SaveOutlined, ReloadOutlined, CloudServerOutlined,
  QrcodeOutlined, CheckCircleOutlined, CloseCircleOutlined, LogoutOutlined,
} from '@ant-design/icons';
import { isNativeApp } from '../App';
import { sourceAPI } from '../api';

const POLL_INTERVAL = 2000;
const POLL_TIMEOUT = 120000;

const YangJiBaoLogin = () => {
  const [status, setStatus] = useState(null);   // null | 'logged_in' | 'logged_out'
  const [qrUrl, setQrUrl] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [logoutLoading, setLogoutLoading] = useState(false);
  const pollTimerRef = useRef(null);
  const pollStartRef = useRef(null);
  const qrIdRef = useRef(null);

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setPolling(false);
  };

  useEffect(() => {
    loadStatus();
    return () => stopPolling();
  }, []);

  const loadStatus = async () => {
    try {
      const res = await sourceAPI.getStatus('yangjibao');
      setStatus(res.data.logged_in ? 'logged_in' : 'logged_out');
    } catch {
      setStatus('logged_out');
    }
  };

  const handleGetQRCode = async () => {
    setQrLoading(true);
    stopPolling();
    try {
      const res = await sourceAPI.getQRCode('yangjibao');
      const { qr_id, qr_url } = res.data;
      qrIdRef.current = qr_id;
      setQrUrl(qr_url);
      startPolling(qr_id);
    } catch (e) {
      message.error('获取二维码失败');
    } finally {
      setQrLoading(false);
    }
  };

  const startPolling = (qrId) => {
    setPolling(true);
    pollStartRef.current = Date.now();
    poll(qrId);
  };

  const poll = async (qrId) => {
    if (Date.now() - pollStartRef.current > POLL_TIMEOUT) {
      stopPolling();
      setQrUrl(null);
      message.warning('二维码已过期，请重新获取');
      return;
    }

    try {
      const res = await sourceAPI.checkQRCodeState('yangjibao', qrId);
      const { state } = res.data;

      if (state === 'confirmed') {
        stopPolling();
        setQrUrl(null);
        setStatus('logged_in');
        message.success('养基宝登录成功');
        return;
      }

      if (state === 'expired') {
        stopPolling();
        setQrUrl(null);
        message.warning('二维码已过期，请重新获取');
        return;
      }
    } catch {
      // 网络错误继续轮询
    }

    pollTimerRef.current = setTimeout(() => poll(qrId), POLL_INTERVAL);
  };

  const handleLogout = async () => {
    setLogoutLoading(true);
    try {
      await sourceAPI.logout('yangjibao');
      setStatus('logged_out');
      setQrUrl(null);
      stopPolling();
      message.success('已退出养基宝');
    } catch {
      message.error('退出失败');
    } finally {
      setLogoutLoading(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>养基宝</span>
        {status === 'logged_in' && (
          <Tag icon={<CheckCircleOutlined />} color="success">已登录</Tag>
        )}
        {status === 'logged_out' && (
          <Tag icon={<CloseCircleOutlined />} color="default">未登录</Tag>
        )}
        {status === null && <Tag>检查中...</Tag>}
      </div>

      {status === 'logged_in' ? (
        <Button
          icon={<LogoutOutlined />}
          onClick={handleLogout}
          loading={logoutLoading}
          danger
        >
          退出登录
        </Button>
      ) : (
        <Space direction="vertical" size={12}>
          <Button
            icon={<QrcodeOutlined />}
            onClick={handleGetQRCode}
            loading={qrLoading}
            type="primary"
          >
            {qrUrl ? '刷新二维码' : '获取二维码'}
          </Button>

          {qrUrl && (
            <div style={{ position: 'relative', display: 'inline-block' }}>
              <Image
                src={qrUrl}
                width={160}
                height={160}
                preview={false}
                style={{ border: '1px solid #f0f0f0', borderRadius: 4 }}
              />
              {polling && (
                <div style={{
                  position: 'absolute', bottom: 4, right: 4,
                  background: 'rgba(0,0,0,0.5)', borderRadius: 4,
                  padding: '2px 6px',
                }}>
                  <Spin size="small" style={{ color: '#fff' }} />
                </div>
              )}
            </div>
          )}

          {qrUrl && (
            <div style={{ color: '#888', fontSize: 12 }}>
              用养基宝 App 扫码登录
            </div>
          )}
        </Space>
      )}
    </div>
  );
};

const SettingsPage = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const isNative = isNativeApp();

  useEffect(() => {
    if (isNative) {
      const savedApiUrl = localStorage.getItem('apiBaseUrl') || '';
      form.setFieldsValue({ apiBaseUrl: savedApiUrl });
    }
  }, [form, isNative]);

  const handleSave = async (values) => {
    setLoading(true);
    try {
      const url = values.apiBaseUrl.trim();
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        message.error('服务器地址必须以 http:// 或 https:// 开头');
        return;
      }

      const cleanUrl = url.replace(/\/$/, '');
      const response = await fetch(`${cleanUrl}/api/health/`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (response.ok) {
        localStorage.setItem('apiBaseUrl', cleanUrl);
        message.success('配置已保存，刷新页面后生效');
      } else {
        message.error('无法连接到服务器，请检查地址是否正确');
      }
    } catch (error) {
      message.error(`连接失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    form.setFieldsValue({ apiBaseUrl: '' });
    message.info('已清空服务器配置');
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="数据源管理">
        <YangJiBaoLogin />
        <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
          注：养基宝数据源仅支持查询您持仓中的基金估值
        </div>
      </Card>

      {isNative && (
        <Card title="系统设置">
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSave}
            style={{ maxWidth: 600 }}
          >
            <Form.Item
              label="服务器地址"
              name="apiBaseUrl"
              rules={[
                { required: true, message: '请输入服务器地址' },
                {
                  pattern: /^https?:\/\/.+/,
                  message: '请输入有效的 URL（以 http:// 或 https:// 开头）'
                }
              ]}
              extra="后端 API 服务器地址，例如：http://192.168.1.100:8000"
            >
              <Input
                prefix={<CloudServerOutlined />}
                placeholder="http://your-server:8000"
              />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<SaveOutlined />}
                  loading={loading}
                >
                  保存配置
                </Button>
                <Button icon={<ReloadOutlined />} onClick={handleReset}>
                  清空配置
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      )}

      {!isNative && (
        <Card title="系统设置">
          <p>Web 版本无需配置服务器地址。</p>
          <p>如需修改服务器，请使用桌面端或移动端应用。</p>
        </Card>
      )}
    </Space>
  );
};

export default SettingsPage;
