import { useState, useEffect, useRef } from 'react';
import { Card, Form, Input, Button, message, Space, Divider, Tag, Image, Spin, Modal, Select, Table, Popconfirm, Typography } from 'antd';
import {
  SaveOutlined, ReloadOutlined, CloudServerOutlined,
  QrcodeOutlined, CheckCircleOutlined, CloseCircleOutlined, LogoutOutlined, ImportOutlined,
  PlusOutlined, EditOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { isNativeApp } from '../App';
import { sourceAPI, aiAPI } from '../api';

const { TextArea } = Input;
const { Text } = Typography;

const FUND_PLACEHOLDERS = [
  { key: '{{fund_code}}', desc: '基金代码' },
  { key: '{{fund_name}}', desc: '基金名称' },
  { key: '{{fund_type}}', desc: '基金类型' },
  { key: '{{latest_nav}}', desc: '最新净值' },
  { key: '{{latest_nav_date}}', desc: '净值日期' },
  { key: '{{estimate_nav}}', desc: '估值净值' },
  { key: '{{estimate_growth}}', desc: '估值涨跌幅(%)' },
  { key: '{{nav_history}}', desc: '近30条净值历史（日期:净值，逗号分隔）' },
  { key: '{{holding_share}}', desc: '持仓份额' },
  { key: '{{holding_cost}}', desc: '持仓成本' },
  { key: '{{holding_value}}', desc: '持仓市值' },
  { key: '{{pnl}}', desc: '盈亏金额' },
  { key: '{{pnl_rate}}', desc: '盈亏比例(%)' },
];

const POSITION_PLACEHOLDERS = [
  { key: '{{account_name}}', desc: '账户名称' },
  { key: '{{holding_cost}}', desc: '总持仓成本' },
  { key: '{{holding_value}}', desc: '总持仓市值' },
  { key: '{{pnl}}', desc: '总盈亏金额' },
  { key: '{{pnl_rate}}', desc: '总盈亏比例(%)' },
  { key: '{{positions}}', desc: '持仓明细（代码|名称|份额|成本|市值|盈亏，换行分隔）' },
];

const AIConfigCard = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    aiAPI.getConfig().then(res => {
      form.setFieldsValue({
        api_endpoint: res.data.api_endpoint || '',
        api_key: '',
        model_name: res.data.model_name || 'gpt-4o-mini',
      });
    }).catch(() => {});
  }, [form]);

  const handleSave = async (values) => {
    if (!values.api_key) {
      message.error('请输入 API Key');
      return;
    }
    setLoading(true);
    try {
      await aiAPI.updateConfig(values);
      message.success('AI配置已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="AI 配置">
      <Form form={form} layout="vertical" onFinish={handleSave} style={{ maxWidth: 600 }}>
        <Form.Item label="API Endpoint" name="api_endpoint" rules={[{ required: true, message: '请输入接口地址' }]}>
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>
        <Form.Item label="API Key" name="api_key" rules={[{ required: true, message: '请输入 API Key' }]} extra="每次保存需重新输入 Key，读取时不显示原始值">
          <Input.Password placeholder="sk-..." />
        </Form.Item>
        <Form.Item label="模型名称" name="model_name" rules={[{ required: true, message: '请输入模型名称' }]}>
          <Input placeholder="gpt-4o-mini" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading}>保存配置</Button>
        </Form.Item>
      </Form>
    </Card>
  );
};

const AITemplatesCard = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [form] = Form.useForm();
  const [contextType, setContextType] = useState('fund');

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const res = await aiAPI.listTemplates();
      setTemplates(res.data);
    } catch {
      message.error('加载模板失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTemplates(); }, []);

  const openCreate = () => {
    setEditingTemplate(null);
    setContextType('fund');
    form.resetFields();
    form.setFieldsValue({ context_type: 'fund', is_default: false });
    setModalVisible(true);
  };

  const openEdit = (tpl) => {
    setEditingTemplate(tpl);
    setContextType(tpl.context_type);
    form.setFieldsValue(tpl);
    setModalVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingTemplate) {
        await aiAPI.updateTemplate(editingTemplate.id, values);
        message.success('模板已更新');
      } else {
        await aiAPI.createTemplate(values);
        message.success('模板已创建');
      }
      setModalVisible(false);
      loadTemplates();
    } catch (e) {
      if (e?.errorFields) return;
      message.error('保存失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await aiAPI.deleteTemplate(id);
      message.success('已删除');
      loadTemplates();
    } catch {
      message.error('删除失败');
    }
  };

  const placeholders = contextType === 'fund' ? FUND_PLACEHOLDERS : POSITION_PLACEHOLDERS;

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '类型', dataIndex: 'context_type', key: 'context_type',
      render: v => v === 'fund' ? <Tag color="blue">基金</Tag> : <Tag color="green">持仓</Tag>,
    },
    { title: '默认', dataIndex: 'is_default', key: 'is_default', render: v => v ? <Tag color="gold">默认</Tag> : '-' },
    {
      title: '操作', key: 'action',
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="提示词模板"
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建模板</Button>}
    >
      <Table
        dataSource={templates}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
      />

      <Modal
        title={editingTemplate ? '编辑模板' : '新建模板'}
        open={modalVisible}
        onOk={handleOk}
        onCancel={() => setModalVisible(false)}
        width={800}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item label="模板名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：基金趋势分析" />
          </Form.Item>
          <Form.Item label="分析维度" name="context_type" rules={[{ required: true }]}>
            <Select onChange={setContextType} options={[
              { label: '基金分析', value: 'fund' },
              { label: '持仓分析', value: 'position' },
            ]} />
          </Form.Item>
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Form.Item label="系统提示词" name="system_prompt" rules={[{ required: true, message: '请输入系统提示词' }]}>
                <TextArea rows={4} placeholder="你是一个专业的基金分析师..." />
              </Form.Item>
              <Form.Item label="用户提示词" name="user_prompt" rules={[{ required: true, message: '请输入用户提示词' }]}>
                <TextArea rows={8} placeholder="请分析基金 {{fund_code}} ..." />
              </Form.Item>
            </div>
            <div style={{ width: 220, flexShrink: 0 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>可用占位符</div>
              {placeholders.map(p => (
                <div key={p.key} style={{ marginBottom: 6 }}>
                  <Text code copyable style={{ fontSize: 12 }}>{p.key}</Text>
                  <div style={{ fontSize: 11, color: '#888' }}>{p.desc}</div>
                </div>
              ))}
            </div>
          </div>
          <Form.Item name="is_default" valuePropName="checked" style={{ marginBottom: 0 }}>
            <Select placeholder="是否设为默认" options={[
              { label: '设为默认模板', value: true },
              { label: '非默认', value: false },
            ]} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

const POLL_INTERVAL = 2000;
const POLL_TIMEOUT = 120000;

const YangJiBaoLogin = () => {
  const [status, setStatus] = useState(null);   // null | 'logged_in' | 'logged_out'
  const [qrUrl, setQrUrl] = useState(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);
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
      setImportResult(null);
      stopPolling();
      message.success('已退出养基宝');
    } catch {
      message.error('退出失败');
    } finally {
      setLogoutLoading(false);
    }
  };

  const handleImport = async () => {
    Modal.confirm({
      title: '导入养基宝持仓',
      content: (
        <div>
          <p>请选择导入方式：</p>
          <ul style={{ paddingLeft: 20, color: '#666' }}>
            <li><b>新建账户</b>：跳过已有持仓记录，仅新增</li>
            <li><b>覆盖账户</b>：清空已有持仓流水后重新导入</li>
          </ul>
        </div>
      ),
      okText: '新建账户',
      cancelText: '覆盖账户',
      onOk: () => doImport(false),
      onCancel: () => doImport(true),
    });
  };

  const doImport = async (overwrite) => {
    setImportLoading(true);
    setImportResult(null);
    try {
      const res = await sourceAPI.importFromYangJiBao(overwrite);
      setImportResult(res.data);
      message.success(`导入完成：新增 ${res.data.holdings_created} 条持仓`);
    } catch (e) {
      message.error(e.response?.data?.error || '导入失败');
    } finally {
      setImportLoading(false);
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
        <Space orientation="vertical" size={12}>
          <Space>
            <Button
              icon={<ImportOutlined />}
              onClick={handleImport}
              loading={importLoading}
              type="primary"
            >
              一键导入持仓
            </Button>
            <Button
              icon={<LogoutOutlined />}
              onClick={handleLogout}
              loading={logoutLoading}
              danger
            >
              退出登录
            </Button>
          </Space>
          {importResult && (
            <div style={{ color: '#666', fontSize: 12 }}>
              新增账户 {importResult.accounts_created}，跳过 {importResult.accounts_skipped}；
              新增持仓 {importResult.holdings_created}，跳过 {importResult.holdings_skipped}
            </div>
          )}
          <div style={{ color: '#aaa', fontSize: 12 }}>
            注：仅支持导入当前持仓中的基金
          </div>
        </Space>
      ) : (
        <Space orientation="vertical" size={12}>
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
                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUrl)}`}
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
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      <Card title="数据源管理">
        <YangJiBaoLogin />
        <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
          注：养基宝数据源仅支持查询您持仓中的基金估值
        </div>
      </Card>

      <AIConfigCard />
      <AITemplatesCard />

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
