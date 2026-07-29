import { Tag, Tooltip } from 'antd';

const SOURCE_INFO = {
  penetration: {
    label: '持仓推算',
    tooltip: '基于基金持仓成分股权重和个股实时行情反向推算，仅供参考',
  },
};

export default function EstimateSourceTag({ source, style }) {
  const info = SOURCE_INFO[source];
  if (!info) return null;

  return (
    <Tooltip title={info.tooltip}>
      <Tag color="default" style={{ fontSize: 10, lineHeight: '16px', opacity: 0.6, ...style }}>
        {info.label}
      </Tag>
    </Tooltip>
  );
}
