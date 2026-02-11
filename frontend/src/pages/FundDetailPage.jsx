import { Card } from 'antd';
import { useParams } from 'react-router-dom';

const FundDetailPage = () => {
  const { code } = useParams();

  return (
    <Card title={`基金详情 - ${code}`}>
      <p>基金详情页面（待实现）</p>
    </Card>
  );
};

export default FundDetailPage;
