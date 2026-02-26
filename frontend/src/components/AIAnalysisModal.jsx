import { useState, useEffect } from 'react';
import { Modal, Select, Button, Space, Spin, Empty, Alert, Typography } from 'antd';
import { RobotOutlined, ReloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { aiAPI } from '../api';

const { Text } = Typography;

/**
 * AI 分析 Modal
 *
 * Props:
 *   open: bool
 *   onClose: fn
 *   contextType: 'fund' | 'position'
 *   contextData: object  ← 占位符数据，由父组件构造
 *   title: string
 */
const AIAnalysisModal = ({ open, onClose, contextType, contextData, title = 'AI 分析' }) => {
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    setResult(null);
    setError(null);
    setTemplatesLoading(true);
    aiAPI.listTemplates(contextType)
      .then(res => {
        setTemplates(res.data);
        if (res.data.length > 0) {
          const def = res.data.find(t => t.is_default) || res.data[0];
          setTemplateId(def.id);
        } else {
          setTemplateId(null);
        }
      })
      .catch(() => setError('加载模板失败，请检查网络'))
      .finally(() => setTemplatesLoading(false));
  }, [open, contextType]);

  const handleAnalyze = async () => {
    if (!templateId) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await aiAPI.analyze(templateId, contextType, contextData);
      setResult(res.data.result);
    } catch (e) {
      setError(e?.response?.data?.error || 'AI 接口调用失败，请检查 AI 配置');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setResult(null);
    setError(null);
    onClose();
  };

  const noTemplates = !templatesLoading && templates.length === 0;

  return (
    <Modal
      title={
        <Space>
          <RobotOutlined />
          {title}
        </Space>
      }
      open={open}
      onCancel={handleClose}
      footer={null}
      width={760}
      styles={{ body: { padding: '16px 24px 24px' } }}
    >
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        {/* 模板选择 + 操作栏 */}
        <Space wrap>
          <Select
            style={{ width: 280 }}
            placeholder={templatesLoading ? '加载中...' : '选择分析模板'}
            loading={templatesLoading}
            value={templateId}
            onChange={setTemplateId}
            options={templates.map(t => ({ label: t.name, value: t.id }))}
            disabled={noTemplates}
          />
          <Button
            type="primary"
            icon={result ? <ReloadOutlined /> : <RobotOutlined />}
            loading={loading}
            disabled={!templateId || noTemplates}
            onClick={handleAnalyze}
          >
            {result ? '重新分析' : '开始分析'}
          </Button>
        </Space>

        {/* 无模板提示 */}
        {noTemplates && (
          <Alert
            type="warning"
            showIcon
            title="暂无可用模板"
            description={<span>请先在 <Text strong>设置 → 提示词模板</Text> 中创建 {contextType === 'fund' ? '基金分析' : '持仓分析'} 类型的模板。</span>}
          />
        )}

        {/* 错误提示 */}
        {error && <Alert type="error" showIcon title={error} />}

        {/* 加载中 */}
        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" tip="AI 分析中，请稍候..." />
          </div>
        )}

        {/* 分析结果 */}
        {result && !loading && (
          <div style={{
            background: '#fafafa',
            border: '1px solid #e8e8e8',
            borderRadius: 8,
            padding: '16px 20px',
            maxHeight: 480,
            overflowY: 'auto',
            lineHeight: 1.8,
          }}>
            <ReactMarkdown
              components={{
                h1: ({ children }) => <h3 style={{ marginTop: 8 }}>{children}</h3>,
                h2: ({ children }) => <h4 style={{ marginTop: 8 }}>{children}</h4>,
                h3: ({ children }) => <h5 style={{ marginTop: 8 }}>{children}</h5>,
                p: ({ children }) => <p style={{ marginBottom: 8 }}>{children}</p>,
                ul: ({ children }) => <ul style={{ paddingLeft: 20, marginBottom: 8 }}>{children}</ul>,
                ol: ({ children }) => <ol style={{ paddingLeft: 20, marginBottom: 8 }}>{children}</ol>,
                li: ({ children }) => <li style={{ marginBottom: 4 }}>{children}</li>,
                strong: ({ children }) => <strong style={{ color: '#262626' }}>{children}</strong>,
                code: ({ inline, children }) => inline
                  ? <code style={{ background: '#f0f0f0', padding: '1px 4px', borderRadius: 3, fontSize: 13 }}>{children}</code>
                  : <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, overflowX: 'auto', fontSize: 13 }}><code>{children}</code></pre>,
                blockquote: ({ children }) => (
                  <blockquote style={{ borderLeft: '3px solid #d9d9d9', paddingLeft: 12, color: '#666', margin: '8px 0' }}>
                    {children}
                  </blockquote>
                ),
              }}
            >
              {result}
            </ReactMarkdown>
          </div>
        )}
      </Space>
    </Modal>
  );
};

export default AIAnalysisModal;
