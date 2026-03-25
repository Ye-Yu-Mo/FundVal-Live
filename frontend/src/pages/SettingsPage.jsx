import { useState, useEffect, useRef } from 'react';
import { Card, Form, Input, Button, message, Space, Divider, Tag, Image, Spin, Modal, Select, Table, Popconfirm, Typography, Alert, Switch, InputNumber, List, Grid } from 'antd';
import {
  SaveOutlined, ReloadOutlined, CloudServerOutlined,
  QrcodeOutlined, CheckCircleOutlined, CloseCircleOutlined, LogoutOutlined, ImportOutlined,
  PlusOutlined, EditOutlined, DeleteOutlined, BellOutlined, SendOutlined,
} from '@ant-design/icons';
import { isNativeApp } from '../App';
import { sourceAPI, aiAPI, fundsAPI, notificationChannelsAPI, notificationRulesAPI } from '../api';
import { usePreference } from '../contexts/PreferenceContext';

const { TextArea } = Input;
const { Text } = Typography;
const { useBreakpoint } = Grid;

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

const DataSourceCard = () => {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const { preferredSource, updatePreference } = usePreference();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    form.setFieldsValue({ preferred_source: preferredSource });
  }, [preferredSource, form]);

  const handleSave = async () => {
    const values = form.getFieldsValue();
    setLoading(true);
    try {
      await updatePreference(values.preferred_source);
      message.success('数据源设置已保存');
    } catch (error) {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="数据源设置">
      <Form form={form} layout="vertical" style={{ maxWidth: isMobile ? '100%' : 600 }}>
        <Form.Item
          label="默认数据源"
          name="preferred_source"
          help="选择基金估值和净值的默认数据源"
        >
          <Select>
            <Select.Option value="eastmoney">东方财富</Select.Option>
            <Select.Option value="yangjibao">养基宝</Select.Option>
            <Select.Option value="xiaobeiyangji">小倍养基</Select.Option>
          </Select>
        </Form.Item>
        <Alert
          message="数据源影响所有估值相关数据（基金查询、持仓预估、账户盈亏）"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form.Item>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={loading}
          >
            保存设置
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};


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
  const screens = useBreakpoint();
  const isMobile = !screens.md;
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
        width={isMobile ? '95vw' : 800}
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

// ─── 通知渠道管理 ────────────────────────────────────────────────────────────

const NotificationChannelsCard = () => {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingChannel, setEditingChannel] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const res = await notificationChannelsAPI.list();
      setChannels(res.data);
    } catch {
      message.error('加载通知渠道失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleOpenModal = (channel = null) => {
    setEditingChannel(channel);
    if (channel) {
      form.setFieldsValue({
        channel_type: channel.channel_type,
        webhook_url: channel.config?.webhook_url || '',
        smtp_host: channel.config?.smtp_host || '',
        smtp_port: channel.config?.smtp_port || 465,
        smtp_ssl: channel.config?.smtp_ssl !== false,
        username: channel.config?.username || '',
        password: channel.config?.password || '',
        from_email: channel.config?.from_email || '',
        to_email: channel.config?.to_email || '',
        is_active: channel.is_active,
      });
    } else {
      form.resetFields();
      form.setFieldsValue({ channel_type: 'webhook', is_active: true });
    }
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const config = values.channel_type === 'webhook'
        ? { webhook_url: values.webhook_url }
        : {
            smtp_host: values.smtp_host,
            smtp_port: values.smtp_port,
            smtp_ssl: values.smtp_ssl,
            username: values.username,
            password: values.password,
            from_email: values.from_email || values.username,
            to_email: values.to_email,
          };
      const data = { channel_type: values.channel_type, config, is_active: values.is_active };

      if (editingChannel) {
        await notificationChannelsAPI.update(editingChannel.id, data);
        message.success('更新成功');
      } else {
        await notificationChannelsAPI.create(data);
        message.success('创建成功');
      }
      setModalVisible(false);
      load();
    } catch (err) {
      if (!err.errorFields) message.error('操作失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await notificationChannelsAPI.delete(id);
      message.success('删除成功');
      load();
    } catch {
      message.error('删除失败');
    }
  };

  const handleTest = async (id) => {
    setTestingId(id);
    try {
      await notificationChannelsAPI.test(id);
      message.success('测试通知发送成功');
    } catch {
      message.error('测试通知发送失败，请检查渠道配置');
    } finally {
      setTestingId(null);
    }
  };

  const channelTypeLabel = { webhook: 'Webhook', email: 'Email' };

  const columns = [
    {
      title: '类型',
      dataIndex: 'channel_type',
      key: 'channel_type',
      render: (v) => <Tag>{channelTypeLabel[v] || v}</Tag>,
    },
    {
      title: '配置',
      key: 'config',
      render: (_, r) => r.channel_type === 'webhook'
        ? r.config?.webhook_url
        : `${r.config?.smtp_host} → ${r.config?.to_email}`,
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v) => v ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_, r) => (
        <Space size="small">
          <Button size="small" icon={<SendOutlined />} loading={testingId === r.id} onClick={() => handleTest(r.id)}>测试</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(r)}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)} okText="确定" cancelText="取消">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const channelType = Form.useWatch('channel_type', form);

  return (
    <Card
      title={<Space><BellOutlined />通知渠道</Space>}
      extra={<Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>添加渠道</Button>}
    >
      {isMobile ? (
        <List
          dataSource={channels}
          loading={loading}
          locale={{ emptyText: '暂无通知渠道' }}
          renderItem={(channel) => (
            <Card
              key={channel.id}
              size="small"
              style={{ marginBottom: 8 }}
              data-testid="channel-card"
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>{channel.name}</div>
                  <div style={{ marginBottom: 4 }}>
                    <Tag color="blue">{channel.channel_type}</Tag>
                  </div>
                  <div style={{ fontSize: 12, color: '#999' }}>
                    状态: {channel.is_active ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>}
                  </div>
                </div>
                <Space size="small" direction="vertical">
                  <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(channel)}>编辑</Button>
                  <Popconfirm title="确定删除？" onConfirm={() => handleDelete(channel.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                </Space>
              </div>
            </Card>
          )}
        />
      ) : (
        <Table
          dataSource={channels}
          rowKey="id"
          columns={columns}
          loading={loading}
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无通知渠道' }}
        />
      )}

      <Modal
        title={editingChannel ? '编辑渠道' : '添加渠道'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="保存"
        cancelText="取消"
        destroyOnClose
        width={isMobile ? '95vw' : 600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="channel_type" label="渠道类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'webhook', label: 'Webhook' }, { value: 'email', label: 'Email' }]} />
          </Form.Item>
          {channelType === 'webhook' && (
            <Form.Item name="webhook_url" label="Webhook URL" rules={[{ required: true, message: '请输入 Webhook URL' }, { type: 'url', message: '请输入有效的 URL' }]}>
              <Input placeholder="https://example.com/webhook" />
            </Form.Item>
          )}
          {channelType === 'email' && (
            <>
              <Form.Item name="smtp_host" label="SMTP 服务器" rules={[{ required: true, message: '请输入 SMTP 服务器地址' }]} extra="例如：smtp.qq.com / smtp.gmail.com / smtp.163.com">
                <Input placeholder="smtp.qq.com" />
              </Form.Item>
              <Space.Compact style={{ width: '100%' }}>
                <Form.Item name="smtp_port" label="端口" style={{ width: '40%' }} initialValue={465}>
                  <InputNumber style={{ width: '100%' }} placeholder="465" />
                </Form.Item>
                <Form.Item name="smtp_ssl" label="SSL" valuePropName="checked" style={{ width: '60%', paddingLeft: 12 }} initialValue={true}>
                  <Switch checkedChildren="SSL" unCheckedChildren="STARTTLS" />
                </Form.Item>
              </Space.Compact>
              <Form.Item name="username" label="用户名（邮箱地址）" rules={[{ required: true, message: '请输入用户名' }, { type: 'email', message: '请输入有效的邮箱' }]}>
                <Input placeholder="your@qq.com" />
              </Form.Item>
              <Form.Item name="password" label="密码 / 授权码" rules={[{ required: true, message: '请输入密码或授权码' }]} extra="QQ/163/Gmail 等需使用授权码，非登录密码">
                <Input.Password placeholder="授权码" />
              </Form.Item>
              <Form.Item name="to_email" label="收件人邮箱" rules={[{ required: true, message: '请输入收件人邮箱' }, { type: 'email', message: '请输入有效的邮箱' }]}>
                <Input placeholder="recipient@example.com" />
              </Form.Item>
              <Form.Item name="from_email" label="发件人邮箱（可选）" extra="留空则使用用户名作为发件人">
                <Input placeholder="your@qq.com" />
              </Form.Item>
            </>
          )}
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

// ─── 通知规则管理 ────────────────────────────────────────────────────────────

const NotificationRulesCard = () => {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [rules, setRules] = useState([]);
  const [channels, setChannels] = useState([]);
  const [funds, setFunds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const [rulesRes, channelsRes] = await Promise.all([
        notificationRulesAPI.list(),
        notificationChannelsAPI.list(),
      ]);
      setRules(rulesRes.data);
      setChannels(channelsRes.data);
    } catch {
      message.error('加载通知规则失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleFundSearch = async (keyword) => {
    if (!keyword) return;
    try {
      const res = await fundsAPI.search(keyword);
      setFunds(res.data);
    } catch {
      // ignore
    }
  };

  const handleOpenModal = (rule = null) => {
    setEditingRule(rule);
    if (rule) {
      form.setFieldsValue({
        fund_code: rule.fund_code,
        rule_type: rule.rule_type,
        threshold: parseFloat(rule.threshold),
        cooldown_minutes: rule.cooldown_minutes,
        channel_ids: rule.channels.map(c => c.id),
        is_active: rule.is_active,
      });
    } else {
      form.resetFields();
      form.setFieldsValue({ rule_type: 'growth_up', cooldown_minutes: 60, is_active: true });
    }
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editingRule) {
        await notificationRulesAPI.update(editingRule.id, values);
        message.success('更新成功');
      } else {
        await notificationRulesAPI.create(values);
        message.success('创建成功');
      }
      setModalVisible(false);
      load();
    } catch (err) {
      if (!err.errorFields) message.error('操作失败');
    }
  };

  const handleDelete = async (id) => {
    try {
      await notificationRulesAPI.delete(id);
      message.success('删除成功');
      load();
    } catch {
      message.error('删除失败');
    }
  };

  const ruleTypeLabel = { growth_up: '涨幅超过', growth_down: '跌幅超过' };

  const columns = [
    {
      title: '基金',
      key: 'fund',
      render: (_, r) => `${r.fund_name}（${r.fund_code}）`,
    },
    {
      title: '触发条件',
      key: 'condition',
      render: (_, r) => `${ruleTypeLabel[r.rule_type]} ${r.threshold}%`,
    },
    {
      title: '通知渠道',
      key: 'channels',
      render: (_, r) => r.channels.map(c => (
        <Tag key={c.id}>{c.channel_type === 'webhook' ? 'Webhook' : 'Email'}</Tag>
      )),
    },
    {
      title: '冷却',
      dataIndex: 'cooldown_minutes',
      key: 'cooldown_minutes',
      render: (v) => `${v} 分钟`,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v) => v ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, r) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(r)}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)} okText="确定" cancelText="取消">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const channelOptions = channels.map(c => ({
    value: c.id,
    label: c.channel_type === 'webhook'
      ? `Webhook: ${c.config?.webhook_url?.slice(0, 30)}...`
      : `Email: ${c.config?.email}`,
  }));

  return (
    <Card
      title={<Space><BellOutlined />通知规则</Space>}
      extra={<Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>添加规则</Button>}
    >
      {channels.length === 0 && (
        <Alert message="请先添加通知渠道，再配置通知规则" type="warning" showIcon style={{ marginBottom: 12 }} />
      )}
      {isMobile ? (
        <List
          dataSource={rules}
          loading={loading}
          locale={{ emptyText: '暂无通知规则' }}
          renderItem={(rule) => (
            <Card
              key={rule.id}
              size="small"
              style={{ marginBottom: 8 }}
              data-testid="rule-card"
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>{rule.name || rule.fund_name}</div>
                  <div style={{ marginBottom: 4 }}>
                    <Tag color="blue">{rule.trigger_type}</Tag>
                    {rule.is_active ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag>}
                  </div>
                </div>
                <Space size="small" direction="vertical">
                  <Button size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(rule)}>编辑</Button>
                  <Popconfirm title="确定删除？" onConfirm={() => handleDelete(rule.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                </Space>
              </div>
            </Card>
          )}
        />
      ) : (
        <Table
          dataSource={rules}
          rowKey="id"
          columns={columns}
          loading={loading}
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无通知规则' }}
        />
      )}

      <Modal
        title={editingRule ? '编辑规则' : '添加规则'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="保存"
        cancelText="取消"
        destroyOnClose
        width={isMobile ? '95vw' : 600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="fund" label="基金" rules={[{ required: true, message: '请选择基金' }]}>
            <Select
              showSearch
              placeholder="输入基金代码或名称搜索"
              filterOption={false}
              onSearch={handleFundSearch}
              options={funds.results
                ? funds.results.map(f => ({ value: f.id, label: `${f.fund_name}（${f.fund_code}）` }))
                : (Array.isArray(funds) ? funds.map(f => ({ value: f.id, label: `${f.fund_name}（${f.fund_code}）` })) : [])
              }
            />
          </Form.Item>
          <Form.Item name="rule_type" label="触发条件" rules={[{ required: true }]}>
            <Select options={[
              { value: 'growth_up', label: '涨幅超过' },
              { value: 'growth_down', label: '跌幅超过' },
            ]} />
          </Form.Item>
          <Form.Item name="threshold" label="阈值（%）" rules={[{ required: true, message: '请输入阈值' }]}>
            <InputNumber min={0} max={100} step={0.5} style={{ width: '100%' }} placeholder="例如：5 表示 5%" />
          </Form.Item>
          <Form.Item name="channel_ids" label="通知渠道" rules={[{ required: true, message: '请选择至少一个渠道' }]}>
            <Select mode="multiple" options={channelOptions} placeholder="选择通知渠道" />
          </Form.Item>
          <Form.Item name="cooldown_minutes" label="冷却时间（分钟）" extra="同一规则触发后，冷却时间内不重复通知">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

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
              用 微信 扫码登录
            </div>
          )}
        </Space>
      )}
    </div>
  );
};

const SMS_COOLDOWN = 60;

const XiaoBeiYangJiLogin = () => {
  const [status, setStatus] = useState(null);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [smsLoading, setSmsLoading] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [countdown, setCountdown] = useState(0);
  const countdownRef = useRef(null);

  useEffect(() => {
    sourceAPI.getStatus('xiaobeiyangji')
      .then(res => setStatus(res.data.logged_in ? 'logged_in' : 'logged_out'))
      .catch(() => setStatus('logged_out'));
    return () => clearInterval(countdownRef.current);
  }, []);

  const startCountdown = () => {
    setCountdown(SMS_COOLDOWN);
    countdownRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(countdownRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleSendSms = async () => {
    if (!phone) { message.warning('请输入手机号'); return; }
    setSmsLoading(true);
    try {
      await sourceAPI.sendSms('xiaobeiyangji', phone);
      message.success('验证码已发送');
      startCountdown();
    } catch (e) {
      message.error(e.response?.data?.error || '发送失败');
    } finally {
      setSmsLoading(false);
    }
  };

  const handleLogin = async () => {
    if (!phone || !code) { message.warning('请输入手机号和验证码'); return; }
    setLoginLoading(true);
    try {
      await sourceAPI.verifyPhone('xiaobeiyangji', phone, code);
      setStatus('logged_in');
      setPhone('');
      setCode('');
      message.success('小倍养基登录成功');
    } catch (e) {
      message.error(e.response?.data?.error || '登录失败，请检查验证码');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = async () => {
    setLogoutLoading(true);
    try {
      await sourceAPI.logout('xiaobeiyangji');
      setStatus('logged_out');
      setImportResult(null);
      message.success('已退出小倍养基');
    } catch {
      message.error('退出失败');
    } finally {
      setLogoutLoading(false);
    }
  };

  const handleImport = () => {
    Modal.confirm({
      title: '导入小倍养基持仓',
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
      const res = await sourceAPI.importHoldings('xiaobeiyangji', overwrite);
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
        <span>小倍养基</span>
        {status === 'logged_in' && <Tag icon={<CheckCircleOutlined />} color="success">已登录</Tag>}
        {status === 'logged_out' && <Tag icon={<CloseCircleOutlined />} color="default">未登录</Tag>}
        {status === null && <Tag>检查中...</Tag>}
      </div>

      {status === 'logged_in' ? (
        <Space direction="vertical" size={12}>
          <Space>
            <Button icon={<ImportOutlined />} onClick={handleImport} loading={importLoading} type="primary">
              一键导入持仓
            </Button>
            <Button icon={<LogoutOutlined />} onClick={handleLogout} loading={logoutLoading} danger>
              退出登录
            </Button>
          </Space>
          {importResult && (
            <div style={{ color: '#666', fontSize: 12 }}>
              新增账户 {importResult.accounts_created}，跳过 {importResult.accounts_skipped}；
              新增持仓 {importResult.holdings_created}，跳过 {importResult.holdings_skipped}
            </div>
          )}
        </Space>
      ) : status === 'logged_out' ? (
        <Space direction="vertical" size={8}>
          <Space.Compact>
            <Input
              placeholder="手机号"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              style={{ width: 160 }}
              maxLength={11}
            />
            <Button
              onClick={handleSendSms}
              loading={smsLoading}
              disabled={countdown > 0}
              style={{ width: 120 }}
            >
              {countdown > 0 ? `重新发送(${countdown}s)` : '发送验证码'}
            </Button>
          </Space.Compact>
          <Space.Compact>
            <Input
              placeholder="验证码"
              value={code}
              onChange={e => setCode(e.target.value)}
              style={{ width: 160 }}
              maxLength={6}
              onPressEnter={handleLogin}
            />
            <Button type="primary" onClick={handleLogin} loading={loginLoading} style={{ width: 120 }}>
              登录
            </Button>
          </Space.Compact>
        </Space>
      ) : null}
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
      <DataSourceCard />

      <Card title="数据源管理">
        <Divider orientation="left" plain style={{ marginTop: 0 }}>养基宝</Divider>
        <YangJiBaoLogin />
        <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
          注：养基宝数据源仅支持查询您持仓中的基金估值
        </div>
        <Divider orientation="left" plain>小倍养基</Divider>
        <XiaoBeiYangJiLogin />
      </Card>

      <AIConfigCard />
      <AITemplatesCard />
      <NotificationChannelsCard />
      <NotificationRulesCard />

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
