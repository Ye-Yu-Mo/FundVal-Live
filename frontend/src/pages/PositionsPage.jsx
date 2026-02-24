import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Card,
  Select,
  Table,
  Statistic,
  Row,
  Col,
  Radio,
  message,
  Empty,
  Tag,
  Button,
  Popconfirm,
  Modal,
  Form,
  Input,
  DatePicker,
  InputNumber,
  AutoComplete,
  Space,
} from 'antd';
import { RollbackOutlined, PlusOutlined, EditOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { positionsAPI, fundsAPI } from '../api';
import { useAccounts } from '../contexts/AccountContext';
import PositionCharts from '../components/PositionCharts';

const PositionsPage = () => {
  const [searchParams] = useSearchParams();
  const {
    accounts: allAccounts,
    loading: accountsLoading,
    loadAccounts,
  } = useAccounts();

  // 过滤出子账户
  const accounts = allAccounts
    .filter(a => a.parent !== null)
    .map(child => {
      const parent = allAccounts.find(a => a.id === child.parent);
      return {
        ...child,
        parent_name: parent?.name || '',
      };
    });

  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [positions, setPositions] = useState([]);
  const [operations, setOperations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [operationsLoading, setOperationsLoading] = useState(false);
  const [fundTypeFilter, setFundTypeFilter] = useState('all');

  // 建仓 Modal 状态
  const [buildModalVisible, setBuildModalVisible] = useState(false);
  const [buildPositionMode, setBuildPositionMode] = useState('value'); // value, nav
  const [buildForm] = Form.useForm();
  const [selectedFundInfo, setSelectedFundInfo] = useState(null); // 选中的基金信息

  // 加仓/减仓 Modal 状态
  const [operationModalVisible, setOperationModalVisible] = useState(false);
  const [operationType, setOperationType] = useState('BUY'); // BUY, SELL
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [operationForm] = Form.useForm();
  const [navLoading, setNavLoading] = useState(false);
  const [navError, setNavError] = useState(null);

  const [fundOptions, setFundOptions] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');

  // 批量删除操作
  const [selectedOperationIds, setSelectedOperationIds] = useState([]);
  const [batchDeleteLoading, setBatchDeleteLoading] = useState(false);

  // 加载账户列表
  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  // 从 URL 参数读取 accountId，或默认选中第一个子账户
  useEffect(() => {
    const accountIdFromUrl = searchParams.get('account');

    if (accountIdFromUrl && accounts.length > 0) {
      // 如果 URL 中有 accountId，且该账户存在，则选中
      const accountExists = accounts.some(a => a.id === accountIdFromUrl);
      if (accountExists) {
        setSelectedAccountId(accountIdFromUrl);
        return;
      }
    }

    // 否则，默认选中第一个子账户
    if (accounts.length > 0 && !selectedAccountId) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accounts, selectedAccountId, searchParams]);

  // 加载持仓列表
  const loadPositions = async (accountId) => {
    if (!accountId) return;

    setLoading(true);
    try {
      const response = await positionsAPI.list(accountId);
      const positionsData = response.data;
      setPositions(positionsData);

      // 自动刷新持仓中基金的净值和估值
      if (positionsData.length > 0) {
        const fundCodes = positionsData.map(p => p.fund_code);
        try {
          const [navsResponse, estimatesResponse] = await Promise.all([
            fundsAPI.batchUpdateNav(fundCodes),
            fundsAPI.batchEstimate(fundCodes),
          ]);

          // 更新持仓列表中的基金数据
          const updatedPositions = positionsData.map(position => {
            const navData = navsResponse.data[position.fund_code];
            const estimateData = estimatesResponse.data[position.fund_code];

            return {
              ...position,
              fund: {
                ...position.fund,
                latest_nav: navData?.latest_nav || position.fund?.latest_nav,
                latest_nav_date: navData?.latest_nav_date || position.fund?.latest_nav_date,
                estimate_nav: estimateData?.estimate_nav || position.fund?.estimate_nav,
                estimate_growth: estimateData?.estimate_growth || position.fund?.estimate_growth,
                estimate_time: estimateData?.estimate_time || position.fund?.estimate_time,
              },
            };
          });

          setPositions(updatedPositions);
        } catch (error) {
          console.error('刷新基金数据失败:', error);
          // 不影响主流程，继续显示持仓
        }
      }
    } catch (error) {
      console.error('加载持仓列表失败:', error);
      message.error(error.response?.data?.message || '加载持仓列表失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  // 加载操作流水
  const loadOperations = async (accountId) => {
    if (!accountId) return;

    setOperationsLoading(true);
    try {
      const response = await positionsAPI.listOperations({ account: accountId });
      // 按日期倒序排列
      const sorted = response.data.sort((a, b) => {
        return new Date(b.operation_date) - new Date(a.operation_date) ||
               new Date(b.created_at) - new Date(a.created_at);
      });
      setOperations(sorted);
    } catch (error) {
      console.error('加载操作流水失败:', error);
      message.error(error.response?.data?.message || '加载操作流水失败，请稍后重试');
    } finally {
      setOperationsLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccountId) {
      loadPositions(selectedAccountId);
      loadOperations(selectedAccountId);
    }
  }, [selectedAccountId]);

  // 监听加仓/减仓 Modal 的日期/时间变化，自动查询净值
  useEffect(() => {
    if (!operationModalVisible || !selectedPosition) {
      return;
    }

    const operationDate = operationForm.getFieldValue('operation_date');
    const before15 = operationForm.getFieldValue('before_15');

    if (operationDate && before15) {
      queryNav(selectedPosition.fund_code, operationDate, before15);
    }
  }, [operationModalVisible, selectedPosition]);

  // 获取当前选中的账户
  const getSelectedAccount = () => {
    return accounts.find(a => a.id === selectedAccountId);
  };

  // 计算统计数据
  const getStatistics = () => {
    const account = getSelectedAccount();
    if (!account) {
      return {
        holding_cost: '0.00',
        holding_value: '0.00',
        pnl: '0.00',
        pnl_rate: null,
        today_pnl: '0.00',
        today_pnl_rate: null,
      };
    }

    return {
      holding_cost: account.holding_cost || '0.00',
      holding_value: account.holding_value || '0.00',
      pnl: account.pnl || '0.00',
      pnl_rate: account.pnl_rate,
      today_pnl: account.today_pnl || '0.00',
      today_pnl_rate: account.today_pnl_rate,
    };
  };

  // 过滤持仓列表
  const getFilteredPositions = () => {
    if (fundTypeFilter === 'all') {
      return positions;
    }
    return positions.filter(p => {
      const fundType = p.fund_type || '';
      return fundType.includes(fundTypeFilter);
    });
  };

  // 格式化金额（千分位分隔）
  const formatMoney = (value) => {
    if (value === null || value === undefined) return '-';
    const num = parseFloat(value);
    return num.toLocaleString('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  // 格式化百分比
  const formatPercent = (value) => {
    if (value === null || value === undefined) return '-';
    return `${(parseFloat(value) * 100).toFixed(2)}%`;
  };

  // 格式化日期
  const formatDate = (date) => {
    if (!date) return '-';
    return new Date(date).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).replace(/\//g, '-');
  };

  // 回滚操作
  const handleRollback = async (operationId) => {
    try {
      await positionsAPI.deleteOperation(operationId);
      message.success('回滚成功');
      loadPositions(selectedAccountId);
      loadOperations(selectedAccountId);
    } catch (error) {
      console.error('回滚失败:', error);
      message.error(error.response?.data?.message || '回滚失败，请稍后重试');
    }
  };

  // 清空持仓
  const handleClearPosition = (position) => {
    Modal.confirm({
      title: '确定要清空该持仓吗？',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <p>将删除 <strong>{position.fund_name}</strong> 的所有操作记录</p>
          <p>持仓份额：{formatMoney(position.holding_share)}</p>
          <p>持仓成本：{formatMoney(position.holding_cost)}</p>
          <p style={{ color: '#ff4d4f', marginTop: 8 }}>此操作不可恢复！</p>
        </div>
      ),
      okText: '确定清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await positionsAPI.clearPosition(position.id);
          message.success('清空持仓成功');
          loadPositions(selectedAccountId);
          loadOperations(selectedAccountId);
        } catch (error) {
          console.error('清空持仓失败:', error);
          message.error(error.response?.data?.detail || '清空持仓失败');
        }
      },
    });
  };

  // 批量删除操作
  const handleBatchDelete = () => {
    if (selectedOperationIds.length === 0) {
      message.warning('请先选择要删除的操作记录');
      return;
    }

    Modal.confirm({
      title: '确定要批量删除操作吗？',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <p>将删除 <strong>{selectedOperationIds.length}</strong> 条操作记录</p>
          <p style={{ color: '#ff4d4f', marginTop: 8 }}>此操作不可恢复，删除后将自动重算持仓！</p>
        </div>
      ),
      okText: '确定删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setBatchDeleteLoading(true);
        try {
          const { data } = await positionsAPI.batchDeleteOperations(selectedOperationIds);
          message.success(`成功删除 ${data.deleted_count} 条操作记录`);
          setSelectedOperationIds([]);
          loadPositions(selectedAccountId);
          loadOperations(selectedAccountId);
        } catch (error) {
          console.error('批量删除失败:', error);
          message.error(error.response?.data?.error || '批量删除失败');
        } finally {
          setBatchDeleteLoading(false);
        }
      },
    });
  };

  // 获取操作类型标签
  const getOperationTypeTag = (type, record) => {
    // 判断是否是建仓：如果是 BUY 且是该基金的第一条操作
    const isBuild = type === 'BUY' && isFirstOperation(record);

    const typeMap = {
      'BUY': { text: isBuild ? '建仓' : '加仓', color: 'red' },
      'SELL': { text: '减仓', color: 'green' },
    };
    const config = typeMap[type] || { text: type, color: 'default' };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  // 判断是否是第一条操作（建仓）
  const isFirstOperation = (record) => {
    // 找到该基金的所有操作，按时间排序
    const fundOperations = operations
      .filter(op => op.fund_code === record.fund_code)
      .sort((a, b) => {
        const dateCompare = new Date(a.operation_date) - new Date(b.operation_date);
        if (dateCompare !== 0) return dateCompare;
        return new Date(a.created_at) - new Date(b.created_at);
      });

    // 如果是第一条操作，则是建仓
    return fundOperations.length > 0 && fundOperations[0].id === record.id;
  };

  // 打开建仓 Modal
  const handleOpenBuildModal = () => {
    buildForm.resetFields();
    setBuildPositionMode('value');
    setFundOptions([]);
    setSearchKeyword('');
    setSelectedFundInfo(null);
    setBuildModalVisible(true);
  };

  // 打开加仓/减仓 Modal
  const handleOpenOperationModal = (position) => {
    operationForm.resetFields();
    setSelectedPosition(position);
    setOperationType('BUY');
    setOperationModalVisible(true);
    setNavError(null);

    // 不再自动填充净值，改为自动查询
  };

  // 查询净值
  const queryNav = async (fundCode, operationDate, before15) => {
    console.log('queryNav called:', { fundCode, operationDate, before15 });

    if (!fundCode || !operationDate || before15 === undefined) {
      console.log('queryNav skipped: missing parameters');
      return;
    }

    setNavLoading(true);
    setNavError(null);

    try {
      const dateStr = operationDate.format('YYYY-MM-DD');
      const before15Bool = before15 === 'before';

      console.log('Calling API:', { fundCode, dateStr, before15Bool });

      const response = await fundsAPI.queryNav(
        fundCode,
        dateStr,
        before15Bool
      );

      console.log('API response:', response.data);

      operationForm.setFieldsValue({
        nav: parseFloat(response.data.nav)
      });
    } catch (error) {
      console.error('queryNav error:', error);
      const errorMsg = error.response?.data?.error || '净值查询失败';
      setNavError(errorMsg);
      message.error(errorMsg);
    } finally {
      setNavLoading(false);
    }
  };

  // 搜索基金
  const handleFundSearch = async (keyword) => {
    setSearchKeyword(keyword);

    if (!keyword || keyword.length < 2) {
      setFundOptions([]);
      return;
    }

    setSearchLoading(true);
    try {
      const response = await fundsAPI.search(keyword);
      // API 返回分页格式：{count, results}
      const funds = response.data.results || [];

      const options = funds.map(fund => ({
        value: fund.fund_code,
        label: `${fund.fund_code} - ${fund.fund_name}`,
        fund: fund,
      }));
      setFundOptions(options);
    } catch (error) {
      console.error('搜索基金失败:', error);
      message.error(error.response?.data?.message || '搜索基金失败，请稍后重试');
    } finally {
      setSearchLoading(false);
    }
  };

  // 选择基金后自动填充净值（建仓用）
  const handleBuildFundSelect = async (value, option) => {
    if (!option.fund) return;

    const fund = option.fund;

    // 获取最新净值和估值
    try {
      const [navResponse, estimateResponse] = await Promise.all([
        fundsAPI.batchUpdateNav([fund.fund_code]),
        fundsAPI.batchEstimate([fund.fund_code]),
      ]);

      const navData = navResponse.data[fund.fund_code];
      const estimateData = estimateResponse.data[fund.fund_code];

      // 更新选中的基金信息
      setSelectedFundInfo({
        fund_code: fund.fund_code,
        fund_name: fund.fund_name,
        latest_nav: navData?.latest_nav || fund.latest_nav,
        latest_nav_date: navData?.latest_nav_date,
        estimate_nav: estimateData?.estimate_nav,
        estimate_growth: estimateData?.estimate_growth,
        estimate_time: estimateData?.estimate_time,
      });

      // 自动填充净值（仅在"持有市值+收益金额"模式下）
      const latestNav = navData?.latest_nav || fund.latest_nav;
      if (latestNav && buildPositionMode === 'value') {
        buildForm.setFieldsValue({
          nav: parseFloat(latestNav),
        });
      }
    } catch (error) {
      console.error('获取基金信息失败:', error);
      message.warning('获取基金最新信息失败，请手动输入净值');

      // 降级：使用搜索结果中的净值（仅在"持有市值+收益金额"模式下）
      if (fund.latest_nav && buildPositionMode === 'value') {
        buildForm.setFieldsValue({
          nav: parseFloat(fund.latest_nav),
        });
      }
    }
  };

  // 提交建仓操作
  const handleBuildSubmit = async () => {
    try {
      const values = await buildForm.validateFields();

      // 检查基金是否已有持仓
      const existingPosition = positions.find(p => p.fund_code === values.fund_code);
      if (existingPosition) {
        message.error('该基金已有持仓，请使用加仓功能');
        return;
      }

      // 构造提交数据（建仓默认当前时间，15:00前）
      const now = new Date();
      const data = {
        account: selectedAccountId,
        fund_code: values.fund_code,
        operation_type: 'BUY',
        operation_date: now.toISOString().split('T')[0],
        before_15: true,
        amount: values.amount,
        share: values.share,
        nav: values.nav,
      };

      await positionsAPI.createOperation(data);
      message.success('建仓成功');
      setBuildModalVisible(false);

      // 立即刷新该基金的净值和估值
      try {
        await Promise.all([
          fundsAPI.batchUpdateNav([values.fund_code]),
          fundsAPI.batchEstimate([values.fund_code]),
        ]);
      } catch (error) {
        console.error('刷新基金数据失败:', error);
        // 不影响主流程
      }

      loadPositions(selectedAccountId);
      loadOperations(selectedAccountId);
    } catch (error) {
      if (error.errorFields) {
        return;
      }
      console.error('建仓失败:', error);
      const errorMsg = error.response?.data?.message ||
                       error.response?.data?.fund_code?.[0] ||
                       '建仓失败，请检查输入信息';
      message.error(errorMsg);
    }
  };

  // 提交加仓/减仓操作
  const handleOperationSubmit = async () => {
    try {
      const values = await operationForm.validateFields();

      // 构造提交数据
      const data = {
        account: selectedAccountId,
        fund_code: selectedPosition.fund_code,
        operation_type: operationType,
        operation_date: values.operation_date.format('YYYY-MM-DD'),
        before_15: values.before_15 === 'before',
        amount: values.amount,
        share: values.share,
        nav: values.nav,
      };

      await positionsAPI.createOperation(data);
      message.success(operationType === 'BUY' ? '加仓成功' : '减仓成功');
      setOperationModalVisible(false);

      // 立即刷新该基金的净值和估值
      try {
        await Promise.all([
          fundsAPI.batchUpdateNav([selectedPosition.fund_code]),
          fundsAPI.batchEstimate([selectedPosition.fund_code]),
        ]);
      } catch (error) {
        console.error('刷新基金数据失败:', error);
        // 不影响主流程
      }

      loadPositions(selectedAccountId);
      loadOperations(selectedAccountId);
    } catch (error) {
      if (error.errorFields) {
        return;
      }
      console.error('操作失败:', error);
      const errorMsg = error.response?.data?.message ||
                       error.response?.data?.fund_code?.[0] ||
                       '操作失败，请检查输入信息';
      message.error(errorMsg);
    }
  };

  // 建仓方式 1：根据市值和收益金额计算
  const handleBuildValueModeCalculate = () => {
    const holdingValue = buildForm.getFieldValue('holding_value');
    const pnlAmount = buildForm.getFieldValue('pnl_amount');

    if (holdingValue === undefined || pnlAmount === undefined) return;

    // 成本 = 持有市值 - 收益金额
    const cost = holdingValue - pnlAmount;
    if (cost <= 0) {
      message.warning('收益金额不能大于或等于持有市值');
      return;
    }

    // 获取最新净值（从选中的基金）
    const fundCode = buildForm.getFieldValue('fund_code');
    const selectedFund = fundOptions.find(opt => opt.value === fundCode);
    if (!selectedFund || !selectedFund.fund.latest_nav) {
      message.warning('请先选择基金以获取最新净值');
      return;
    }

    const latestNav = parseFloat(selectedFund.fund.latest_nav);
    // 份额 = 持有市值 / 最新净值
    const share = holdingValue / latestNav;
    // 持有净值 = 成本 / 份额
    const holdingNav = cost / share;

    buildForm.setFieldsValue({
      amount: cost.toFixed(2),
      share: share.toFixed(4),
      nav: holdingNav.toFixed(4),
    });
  };

  // 建仓方式 2：根据净值和份额计算
  const handleBuildNavModeCalculate = () => {
    const nav = buildForm.getFieldValue('nav');
    const share = buildForm.getFieldValue('share');

    if (!nav || !share) return;

    const amount = nav * share;
    buildForm.setFieldsValue({
      amount: amount.toFixed(2),
    });
  };

  // 加仓：根据金额和净值计算份额
  const handleOperationBuyCalculate = () => {
    const amount = operationForm.getFieldValue('amount');
    const nav = operationForm.getFieldValue('nav');

    if (!amount || !nav) return;

    const share = amount / nav;
    operationForm.setFieldsValue({
      share: share.toFixed(4),
    });
  };

  // 减仓：根据份额和净值计算金额
  const handleOperationSellCalculate = () => {
    const share = operationForm.getFieldValue('share');
    const nav = operationForm.getFieldValue('nav');

    if (!share || !nav) return;

    const amount = share * nav;
    operationForm.setFieldsValue({
      amount: amount.toFixed(2),
    });
  };

  const statistics = getStatistics();

  const operationColumns = [
    {
      title: '操作日期',
      dataIndex: 'operation_date',
      key: 'operation_date',
      width: 120,
      render: (date) => formatDate(date),
    },
    {
      title: '操作类型',
      dataIndex: 'operation_type',
      key: 'operation_type',
      width: 100,
      render: (type, record) => getOperationTypeTag(type, record),
    },
    {
      title: '基金代码',
      dataIndex: 'fund_code',
      key: 'fund_code',
      width: 100,
    },
    {
      title: '基金名称',
      dataIndex: 'fund_name',
      key: 'fund_name',
      width: 200,
    },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '份额',
      dataIndex: 'share',
      key: 'share',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '净值',
      dataIndex: 'nav',
      key: 'nav',
      width: 100,
      render: (value) => formatMoney(value),
    },
    {
      title: '时间',
      dataIndex: 'before_15',
      key: 'before_15',
      width: 100,
      render: (before15) => before15 ? '15:00前' : '15:00后',
      responsive: ['md'],
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      fixed: 'right',
      render: (_, record, index) => {
        // 仅最新一条操作可回滚
        if (index !== 0) return null;
        return (
          <Popconfirm
            title="确定要回滚此操作吗？"
            description="回滚后将删除此操作记录并重新计算持仓"
            onConfirm={() => handleRollback(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              icon={<RollbackOutlined />}
              danger
            >
              回滚
            </Button>
          </Popconfirm>
        );
      },
    },
  ];

  const columns = [
    {
      title: '基金代码',
      dataIndex: 'fund_code',
      key: 'fund_code',
      width: 100,
    },
    {
      title: '基金名称',
      dataIndex: 'fund_name',
      key: 'fund_name',
      width: 200,
    },
    {
      title: '基金类型',
      dataIndex: 'fund_type',
      key: 'fund_type',
      width: 100,
      responsive: ['lg'],
    },
    {
      title: '持有份额',
      dataIndex: 'holding_share',
      key: 'holding_share',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '持有成本',
      dataIndex: 'holding_cost',
      key: 'holding_cost',
      width: 120,
      render: (value) => formatMoney(value),
    },
    {
      title: '持仓市值',
      key: 'holding_value',
      width: 120,
      render: (_, record) => {
        const value = parseFloat(record.holding_share || 0) * parseFloat(record.fund?.latest_nav || 0);
        return formatMoney(value);
      },
    },
    {
      title: '盈亏金额',
      dataIndex: 'pnl',
      key: 'pnl',
      width: 120,
      render: (value) => {
        const num = parseFloat(value || 0);
        return (
          <span style={{ color: num >= 0 ? '#ff4d4f' : '#52c41a' }}>
            {formatMoney(value)}
          </span>
        );
      },
    },
    {
      title: '盈亏率',
      key: 'pnl_rate',
      width: 100,
      render: (_, record) => {
        const cost = parseFloat(record.holding_cost || 0);
        const pnl = parseFloat(record.pnl || 0);
        if (cost === 0) return '-';
        const rate = pnl / cost;
        return (
          <span style={{ color: rate >= 0 ? '#ff4d4f' : '#52c41a' }}>
            {formatPercent(rate)}
          </span>
        );
      },
      responsive: ['md'],
    },
    {
      title: '预估市值',
      key: 'estimate_value',
      width: 120,
      render: (_, record) => {
        const estimateNav = record.fund?.estimate_nav;
        if (!estimateNav) return '-';
        const value = parseFloat(record.holding_share || 0) * parseFloat(estimateNav);
        return formatMoney(value);
      },
      responsive: ['lg'],
    },
    {
      title: '预估盈亏',
      key: 'estimate_pnl',
      width: 120,
      render: (_, record) => {
        const estimateNav = record.fund?.estimate_nav;
        if (!estimateNav) return '-';
        const estimateValue = parseFloat(record.holding_share || 0) * parseFloat(estimateNav);
        const pnl = estimateValue - parseFloat(record.holding_cost || 0);
        return (
          <span style={{ color: pnl >= 0 ? '#ff4d4f' : '#52c41a' }}>
            {formatMoney(pnl)}
          </span>
        );
      },
      responsive: ['xl'],
    },
    {
      title: '今日盈亏',
      key: 'today_pnl',
      width: 120,
      render: (_, record) => {
        const latestNav = record.fund?.latest_nav;
        const estimateNav = record.fund?.estimate_nav;
        if (!latestNav || !estimateNav) return '-';
        const todayPnl = parseFloat(record.holding_share || 0) * (parseFloat(estimateNav) - parseFloat(latestNav));

        // 判断是否是预估值：如果 estimate_nav 存在且不等于 latest_nav，则是预估
        const isEstimate = estimateNav && estimateNav !== latestNav;

        return (
          <span style={{ color: todayPnl >= 0 ? '#ff4d4f' : '#52c41a' }}>
            {formatMoney(todayPnl)}
            {isEstimate && <span style={{ color: '#999', fontSize: '12px' }}> (预估)</span>}
          </span>
        );
      },
      responsive: ['lg'],
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleOpenOperationModal(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleClearPosition(record)}
          >
            清空
          </Button>
        </Space>
      ),
    },
  ];

  if (accounts.length === 0) {
    return (
      <Card title="持仓查询">
        <Empty
          description={
            <span>
              暂无子账户
              <br />
              请先在账户管理页面创建子账户
            </span>
          }
        />
      </Card>
    );
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Select
          style={{ width: 300, marginBottom: 16 }}
          placeholder="选择子账户"
          value={selectedAccountId}
          onChange={setSelectedAccountId}
          options={accounts.map(a => ({
            label: `${a.name} (${a.parent_name})`,
            value: a.id,
          }))}
        />

        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="持仓总成本"
              value={statistics.holding_cost}
              prefix="¥"
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="持仓总市值"
              value={statistics.holding_value}
              prefix="¥"
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="总盈亏"
              value={statistics.pnl}
              formatter={(v) => {
                const color = Number(v) >= 0 ? '#ff4d4f' : '#52c41a';
                const suffix = statistics.pnl_rate ? ` (${formatPercent(statistics.pnl_rate)})` : '';
                return (
                  <span style={{ color }}>
                    ¥{v}{suffix}
                  </span>
                );
              }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="今日盈亏 (预估)"
              value={statistics.today_pnl}
              formatter={(v) => {
                const color = Number(v) >= 0 ? '#ff4d4f' : '#52c41a';
                const suffix = statistics.today_pnl_rate ? ` (${formatPercent(statistics.today_pnl_rate)})` : '';
                return (
                  <span style={{ color }}>
                    ¥{v}{suffix}
                  </span>
                );
              }}
            />
          </Col>
        </Row>
      </Card>

      {/* 数据可视化 */}
      <PositionCharts positions={positions} accountId={selectedAccountId} />

      <Card
        title="持仓列表"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleOpenBuildModal}
          >
            建仓
          </Button>
        }
      >
        <Radio.Group
          value={fundTypeFilter}
          onChange={(e) => setFundTypeFilter(e.target.value)}
          style={{ marginBottom: 16 }}
        >
          <Radio.Button value="all">全部</Radio.Button>
          <Radio.Button value="股票">股票型</Radio.Button>
          <Radio.Button value="债券">债券型</Radio.Button>
          <Radio.Button value="混合">混合型</Radio.Button>
          <Radio.Button value="货币">货币型</Radio.Button>
          <Radio.Button value="其他">其他</Radio.Button>
        </Radio.Group>

        <Table
          columns={columns}
          dataSource={getFilteredPositions()}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 'max-content' }}
          locale={{
            emptyText: (
              <Empty
                description={
                  fundTypeFilter === 'all'
                    ? '暂无持仓，点击右上角「添加操作」开始记录'
                    : `暂无${fundTypeFilter}型基金持仓`
                }
              />
            ),
          }}
        />
      </Card>

      <Card
        title="操作流水"
        style={{ marginTop: 16 }}
        extra={
          selectedOperationIds.length > 0 && (
            <Button
              type="primary"
              danger
              icon={<DeleteOutlined />}
              loading={batchDeleteLoading}
              onClick={handleBatchDelete}
            >
              批量删除 ({selectedOperationIds.length})
            </Button>
          )
        }
      >
        <Table
          columns={operationColumns}
          dataSource={operations}
          rowKey="id"
          loading={operationsLoading}
          pagination={false}
          scroll={{ x: 'max-content' }}
          rowSelection={{
            selectedRowKeys: selectedOperationIds,
            onChange: (selectedRowKeys) => setSelectedOperationIds(selectedRowKeys),
            getCheckboxProps: (record) => ({
              disabled: false,
            }),
          }}
          locale={{
            emptyText: (
              <Empty description="暂无操作记录，点击右上角「添加操作」开始记录" />
            ),
          }}
        />
      </Card>

      {/* 建仓 Modal */}
      <Modal
        title="建仓"
        open={buildModalVisible}
        onOk={handleBuildSubmit}
        onCancel={() => setBuildModalVisible(false)}
        okText="确定"
        cancelText="取消"
        width={600}
      >
        <Form
          form={buildForm}
          layout="vertical"
        >
          <Form.Item
            label="基金代码或基金名称"
            name="fund_code"
            rules={[{ required: true, message: '请输入基金代码或基金名称' }]}
          >
            <AutoComplete
              options={fundOptions}
              onSearch={handleFundSearch}
              onSelect={handleBuildFundSelect}
              placeholder={searchKeyword ? '' : '输入基金代码或基金名称搜索（至少2个字符）'}
              loading={searchLoading}
              style={{ width: '100%' }}
              popupMatchSelectWidth={true}
            />
          </Form.Item>

          {/* 显示选中基金的信息 */}
          {selectedFundInfo && (
            <Card size="small" style={{ marginBottom: 16, backgroundColor: '#f5f5f5' }}>
              <div style={{ fontSize: '12px' }}>
                <div><strong>{selectedFundInfo.fund_name}</strong> ({selectedFundInfo.fund_code})</div>
                <div style={{ marginTop: 8 }}>
                  <span>最新净值: </span>
                  <span style={{ fontWeight: 'bold' }}>
                    {selectedFundInfo.latest_nav || '-'}
                  </span>
                  {selectedFundInfo.latest_nav_date && (
                    <span style={{ color: '#999', marginLeft: 8 }}>
                      ({formatDate(selectedFundInfo.latest_nav_date)})
                    </span>
                  )}
                </div>
                {selectedFundInfo.estimate_nav && (
                  <div style={{ marginTop: 4 }}>
                    <span>估算净值: </span>
                    <span style={{ fontWeight: 'bold' }}>
                      {selectedFundInfo.estimate_nav}
                    </span>
                    {selectedFundInfo.estimate_growth && (
                      <span style={{
                        color: parseFloat(selectedFundInfo.estimate_growth) >= 0 ? '#ff4d4f' : '#52c41a',
                        marginLeft: 8
                      }}>
                        ({parseFloat(selectedFundInfo.estimate_growth) >= 0 ? '+' : ''}{selectedFundInfo.estimate_growth}%)
                      </span>
                    )}
                  </div>
                )}
              </div>
            </Card>
          )}

          <Form.Item label="建仓方式">
            <Radio.Group value={buildPositionMode} onChange={(e) => setBuildPositionMode(e.target.value)}>
              <Radio.Button value="value">持有市值 + 收益金额</Radio.Button>
              <Radio.Button value="nav">持有净值 + 份额</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {buildPositionMode === 'value' ? (
            <>
              <Form.Item
                label="持有市值"
                name="holding_value"
                rules={[{ required: true, message: '请输入持有市值' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入持有市值"
                  min={0}
                  onChange={handleBuildValueModeCalculate}
                />
              </Form.Item>

              <Form.Item
                label="收益金额"
                name="pnl_amount"
                rules={[{ required: true, message: '请输入收益金额' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入收益金额（可为负数）"
                  onChange={handleBuildValueModeCalculate}
                />
              </Form.Item>

              <Form.Item
                label="成本（自动计算）"
                name="amount"
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  disabled
                />
              </Form.Item>

              <Form.Item
                label="份额（自动计算）"
                name="share"
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  disabled
                />
              </Form.Item>

              <Form.Item
                label="持有净值（自动计算）"
                name="nav"
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  disabled
                />
              </Form.Item>
            </>
          ) : (
            <>
              <Form.Item
                label="持有净值"
                name="nav"
                rules={[{ required: true, message: '请输入持有净值' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入持有净值"
                  min={0}
                  onChange={handleBuildNavModeCalculate}
                />
              </Form.Item>

              <Form.Item
                label="份额"
                name="share"
                rules={[{ required: true, message: '请输入份额' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入份额"
                  min={0}
                  onChange={handleBuildNavModeCalculate}
                />
              </Form.Item>

              <Form.Item
                label="金额（自动计算）"
                name="amount"
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  disabled
                />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      {/* 加仓/减仓 Modal */}
      <Modal
        title={`${operationType === 'BUY' ? '加仓' : '减仓'} - ${selectedPosition?.fund_name || ''}`}
        open={operationModalVisible}
        onOk={handleOperationSubmit}
        onCancel={() => setOperationModalVisible(false)}
        okText="确定"
        cancelText="取消"
        width={600}
      >
        <Form
          form={operationForm}
          layout="vertical"
          initialValues={{
            before_15: 'before',
          }}
        >
          <Form.Item label="操作类型">
            <Radio.Group value={operationType} onChange={(e) => setOperationType(e.target.value)}>
              <Radio.Button value="BUY">加仓</Radio.Button>
              <Radio.Button value="SELL">减仓</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            label="操作日期"
            name="operation_date"
            rules={[{ required: true, message: '请选择操作日期' }]}
          >
            <DatePicker
              style={{ width: '100%' }}
              onChange={(date) => {
                const before15 = operationForm.getFieldValue('before_15');
                if (date && before15 && selectedPosition) {
                  queryNav(selectedPosition.fund_code, date, before15);
                }
              }}
            />
          </Form.Item>

          <Form.Item
            label="操作时间"
            name="before_15"
            rules={[{ required: true, message: '请选择操作时间' }]}
          >
            <Radio.Group
              onChange={(e) => {
                const operationDate = operationForm.getFieldValue('operation_date');
                if (operationDate && selectedPosition) {
                  queryNav(selectedPosition.fund_code, operationDate, e.target.value);
                }
              }}
            >
              <Radio value="before">15:00前</Radio>
              <Radio value="after">15:00后</Radio>
            </Radio.Group>
          </Form.Item>

          {operationType === 'BUY' ? (
            <>
              <Form.Item
                label="金额"
                name="amount"
                rules={[{ required: true, message: '请输入金额' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入金额"
                  min={0}
                  onChange={handleOperationBuyCalculate}
                />
              </Form.Item>

              <Form.Item
                label="净值（自动查询）"
                name="nav"
                rules={[{ required: true, message: '净值查询中...' }]}
                validateStatus={navError ? 'error' : navLoading ? 'validating' : 'success'}
                help={navError || (navLoading ? '查询中...' : '')}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动查询"
                  disabled
                  onChange={handleOperationBuyCalculate}
                />
              </Form.Item>

              <Form.Item
                label="份额（自动计算）"
                name="share"
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  disabled
                />
              </Form.Item>
            </>
          ) : (
            <>
              <Form.Item
                label="份额"
                name="share"
                rules={[{ required: true, message: '请输入份额' }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="请输入份额"
                  min={0}
                  onChange={handleOperationSellCalculate}
                />
              </Form.Item>

              <Form.Item
                label="净值（自动查询）"
                name="nav"
                rules={[{ required: true, message: '净值查询中...' }]}
                validateStatus={navError ? 'error' : navLoading ? 'validating' : 'success'}
                help={navError || (navLoading ? '查询中...' : '')}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动查询"
                  disabled
                  onChange={handleOperationSellCalculate}
                />
              </Form.Item>

              <Form.Item
                label="金额（自动计算）"
                name="amount"
              >
                <InputNumber
                  style={{ width: '100%' }}
                  placeholder="自动计算"
                  disabled
                />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default PositionsPage;
