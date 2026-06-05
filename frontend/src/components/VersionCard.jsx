import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, Button, Descriptions, Tag, Spin, message, Space } from 'antd';
import { InfoCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { healthCheck } from '../api';

const VersionCard = () => {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadVersion = async () => {
    setLoading(true);
    try {
      const [healthRes, dbRes] = await Promise.all([
        healthCheck(),
        axios.get('/api/admin/stats/').catch(() => ({ data: null })),
      ]);
      setInfo({
        backend: healthRes.data.version || '-',
        database: healthRes.data.database || 'unknown',
        initialized: healthRes.data.system_initialized ? '已初始化' : '未初始化',
        dbVersion: dbRes.data?.nav_history_count != null ? '正常' : '-',
      });
    } catch {
      setInfo({ backend: '-', database: '未知', initialized: '-', dbVersion: '-' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadVersion(); }, []);

  return (
    <Card
      title="系统版本"
      extra={
        <Button icon={<ReloadOutlined />} size="small" onClick={loadVersion} loading={loading}>
          刷新
        </Button>
      }
    >
      {info ? (
        <Descriptions column={1} size="small">
          <Descriptions.Item label="后端版本">
            <Tag color="blue">{info.backend}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="前端版本">
            <Tag color="green">2.5.2</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="数据库">
            <Tag color={info.database === 'connected' ? 'green' : 'red'}>{info.database}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="系统状态">
            <Tag color={info.initialized === '已初始化' ? 'green' : 'orange'}>{info.initialized}</Tag>
          </Descriptions.Item>
        </Descriptions>
      ) : (
        <Spin />
      )}
    </Card>
  );
};

export default VersionCard;
