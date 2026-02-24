"""
API ViewSets

实现所有 API 端点
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import (
    Fund, Account, Position, PositionOperation,
    Watchlist, WatchlistItem, EstimateAccuracy, FundNavHistory
)
from .serializers import (
    FundSerializer, AccountSerializer, PositionSerializer,
    PositionOperationSerializer, WatchlistSerializer, UserRegisterSerializer,
    FundNavHistorySerializer, QueryNavSerializer
)
from .sources import SourceRegistry
from .services import recalculate_all_positions
from fundval.config import config


class FundViewSet(viewsets.ReadOnlyModelViewSet):
    """基金 ViewSet"""

    queryset = Fund.objects.all()
    serializer_class = FundSerializer
    permission_classes = [AllowAny]
    lookup_field = 'fund_code'
    filter_backends = [filters.SearchFilter]
    search_fields = ['fund_code', 'fund_name']

    def get_queryset(self):
        queryset = super().get_queryset()

        # 按类型过滤
        fund_type = self.request.query_params.get('fund_type')
        if fund_type:
            queryset = queryset.filter(fund_type=fund_type)

        return queryset

    def list(self, request, *args, **kwargs):
        """基金列表（分页）"""
        queryset = self.filter_queryset(self.get_queryset()).order_by('fund_code')

        page_size = int(request.query_params.get('page_size', 20))

        # 手动分页
        from django.core.paginator import Paginator
        paginator = Paginator(queryset, page_size)
        page_number = int(request.query_params.get('page', 1))
        page = paginator.get_page(page_number)

        serializer = self.get_serializer(page, many=True)
        return Response({
            'count': paginator.count,
            'results': serializer.data
        })

    @action(detail=True, methods=['get'])
    def estimate(self, request, fund_code=None):
        """获取基金估值"""
        fund = self.get_object()
        source_name = request.query_params.get('source', 'eastmoney')

        source = SourceRegistry.get_source(source_name)
        if not source:
            return Response(
                {'error': f'数据源 {source_name} 不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            data = source.fetch_estimate(fund_code)
            return Response(data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def accuracy(self, request, fund_code=None):
        """获取基金各数据源准确率"""
        fund = self.get_object()
        days = int(request.query_params.get('days', 100))

        # 获取最近 N 天的准确率记录
        records = EstimateAccuracy.objects.filter(
            fund=fund,
            error_rate__isnull=False
        ).order_by('-estimate_date')[:days]

        # 按数据源分组统计
        result = {}
        for record in records:
            source_name = record.source_name
            if source_name not in result:
                result[source_name] = {
                    'records': [],
                    'total_error': Decimal('0'),
                    'count': 0
                }

            result[source_name]['records'].append({
                'date': record.estimate_date,
                'error_rate': record.error_rate
            })
            result[source_name]['total_error'] += record.error_rate
            result[source_name]['count'] += 1

        # 计算平均误差率
        for source_name, data in result.items():
            if data['count'] > 0:
                data['avg_error_rate'] = data['total_error'] / data['count']
            else:
                data['avg_error_rate'] = Decimal('0')

            data['record_count'] = data['count']
            del data['total_error']
            del data['count']

        return Response(result)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def batch_estimate(self, request):
        """
        批量获取基金估值（带缓存）

        请求体:
        {
            "fund_codes": ["000001", "000002", ...]
        }

        响应:
        {
            "000001": {
                "fund_code": "000001",
                "fund_name": "华夏成长",
                "estimate_nav": "1.2345",
                "estimate_growth": "1.23",
                "estimate_time": "2026-02-11T14:30:00Z",
                "latest_nav": "1.2200",
                "from_cache": true
            },
            ...
        }
        """
        fund_codes = request.data.get('fund_codes', [])
        ttl_minutes = config.get('estimate_cache_ttl', 5)  # 从配置读取 TTL

        if not fund_codes:
            return Response({'error': '缺少 fund_codes 参数'}, status=status.HTTP_400_BAD_REQUEST)

        # 查询数据库
        funds = Fund.objects.filter(fund_code__in=fund_codes)
        fund_map = {f.fund_code: f for f in funds}

        results = {}
        need_fetch = []  # 需要从数据源获取的基金

        # 检查缓存
        now = timezone.now()
        for code in fund_codes:
            fund = fund_map.get(code)
            if not fund:
                results[code] = {'error': '基金不存在'}
                continue

            # 检查缓存是否有效
            if (fund.estimate_nav and fund.estimate_time and
                (now - fund.estimate_time).total_seconds() < ttl_minutes * 60):
                # 缓存命中
                results[code] = {
                    'fund_code': code,
                    'fund_name': fund.fund_name,
                    'estimate_nav': str(fund.estimate_nav),
                    'estimate_growth': str(fund.estimate_growth) if fund.estimate_growth else None,
                    'estimate_time': fund.estimate_time.isoformat(),
                    'latest_nav': str(fund.latest_nav) if fund.latest_nav else None,
                    'latest_nav_date': fund.latest_nav_date.isoformat() if fund.latest_nav_date else None,
                    'from_cache': True
                }
            else:
                # 缓存失效，需要重新获取
                need_fetch.append(code)

        # 从数据源获取
        if need_fetch:
            source = SourceRegistry.get_source('eastmoney')

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(source.fetch_estimate, code): code
                          for code in need_fetch}

                for future in as_completed(futures):
                    code = futures[future]
                    try:
                        data = future.result()
                        fund = fund_map.get(code)

                        if fund and data:
                            # 更新数据库
                            fund.estimate_nav = data.get('estimate_nav')
                            fund.estimate_growth = data.get('estimate_growth')
                            fund.estimate_time = timezone.now()
                            fund.save(update_fields=['estimate_nav', 'estimate_growth', 'estimate_time'])

                            results[code] = {
                                'fund_code': code,
                                'fund_name': fund.fund_name,
                                'estimate_nav': str(data.get('estimate_nav')),
                                'estimate_growth': str(data.get('estimate_growth')),
                                'estimate_time': fund.estimate_time.isoformat(),
                                'latest_nav': str(fund.latest_nav) if fund.latest_nav else None,
                                'latest_nav_date': fund.latest_nav_date.isoformat() if fund.latest_nav_date else None,
                                'from_cache': False
                            }
                    except Exception as e:
                        results[code] = {
                            'fund_code': code,
                            'error': f'获取估值失败: {str(e)}'
                        }

        return Response(results)

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def batch_update_nav(self, request):
        """
        批量更新基金净值

        请求体:
        {
            "fund_codes": ["000001", "000002", ...]
        }

        响应:
        {
            "000001": {
                "fund_code": "000001",
                "latest_nav": "1.2200",
                "latest_nav_date": "2026-02-11"
            },
            ...
        }
        """
        fund_codes = request.data.get('fund_codes', [])

        if not fund_codes:
            return Response({'error': '缺少 fund_codes 参数'}, status=status.HTTP_400_BAD_REQUEST)

        # 查询数据库
        funds = Fund.objects.filter(fund_code__in=fund_codes)
        fund_map = {f.fund_code: f for f in funds}

        results = {}
        source = SourceRegistry.get_source('eastmoney')

        # 并发获取净值
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(source.fetch_realtime_nav, code): code
                      for code in fund_codes if code in fund_map}

            for future in as_completed(futures):
                code = futures[future]
                try:
                    data = future.result()
                    fund = fund_map.get(code)

                    if fund and data:
                        # 更新数据库
                        fund.latest_nav = data.get('nav')
                        fund.latest_nav_date = data.get('nav_date')
                        fund.save(update_fields=['latest_nav', 'latest_nav_date'])

                        results[code] = {
                            'fund_code': code,
                            'latest_nav': str(data.get('nav')),
                            'latest_nav_date': data.get('nav_date').isoformat() if data.get('nav_date') else None,
                        }
                except Exception as e:
                    results[code] = {
                        'fund_code': code,
                        'error': f'获取净值失败: {str(e)}'
                    }

        return Response(results)

    @action(detail=False, methods=['post'])
    def query_nav(self, request):
        """
        查询持仓操作净值

        POST /api/funds/query_nav/
        {
            "fund_code": "000001",
            "operation_date": "2024-01-15",
            "before_15": true
        }

        响应：
        {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "nav": "1.2345",
            "nav_date": "2024-01-14",
            "source": "history"  // 或 "latest"
        }
        """
        from datetime import timedelta
        from .utils.trading_calendar import get_last_trading_day

        serializer = QueryNavSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fund_code = serializer.validated_data['fund_code']
        operation_date = serializer.validated_data['operation_date']
        before_15 = serializer.validated_data['before_15']

        # 1. 获取基金
        fund = get_object_or_404(Fund, fund_code=fund_code)

        # 2. 计算查询日期
        if before_15:
            query_date = get_last_trading_day(operation_date - timedelta(days=1))
        else:
            query_date = get_last_trading_day(operation_date)

        # 3. 查询历史净值
        nav_history = FundNavHistory.objects.filter(
            fund=fund,
            nav_date=query_date
        ).first()

        if nav_history:
            return Response({
                'fund_code': fund_code,
                'fund_name': fund.fund_name,
                'nav': str(nav_history.unit_nav),
                'nav_date': str(nav_history.nav_date),
                'source': 'history'
            })

        # 4. 如果没有历史净值，尝试从数据源同步
        from .services.nav_history import sync_nav_history
        import logging

        logger = logging.getLogger(__name__)

        try:
            logger.info(f'尝试同步 {fund_code} 在 {query_date} 的净值')
            count = sync_nav_history(fund_code, query_date, query_date)
            logger.info(f'同步完成，新增/更新 {count} 条记录')

            # 再次查询
            nav_history = FundNavHistory.objects.filter(
                fund=fund,
                nav_date=query_date
            ).first()

            if nav_history:
                logger.info(f'同步后查询成功：{fund_code} {query_date} = {nav_history.unit_nav}')
                return Response({
                    'fund_code': fund_code,
                    'fund_name': fund.fund_name,
                    'nav': str(nav_history.unit_nav),
                    'nav_date': str(nav_history.nav_date),
                    'source': 'synced'
                })
            else:
                logger.warning(f'同步后仍未找到数据：{fund_code} {query_date}')
        except Exception as e:
            logger.warning(f'同步净值失败：{fund_code} {query_date}, 错误：{e}', exc_info=True)

        # 5. fallback 到 Fund.latest_nav
        if fund.latest_nav:
            return Response({
                'fund_code': fund_code,
                'fund_name': fund.fund_name,
                'nav': str(fund.latest_nav),
                'nav_date': str(fund.latest_nav_date) if fund.latest_nav_date else None,
                'source': 'latest'
            })

        # 6. 没有数据
        return Response(
            {'error': '净值数据未找到'},
            status=status.HTTP_404_NOT_FOUND
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def sync(self, request):
        """同步基金列表（管理员）"""
        source = SourceRegistry.get_source('eastmoney')
        if not source:
            return Response(
                {'error': '数据源 eastmoney 未注册'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            funds = source.fetch_fund_list()

            created_count = 0
            updated_count = 0

            for fund_data in funds:
                fund, created = Fund.objects.update_or_create(
                    fund_code=fund_data['fund_code'],
                    defaults={
                        'fund_name': fund_data['fund_name'],
                        'fund_type': fund_data['fund_type'],
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            return Response({
                'created': created_count,
                'updated': updated_count,
                'total': len(funds)
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AccountViewSet(viewsets.ModelViewSet):
    """账户 ViewSet"""

    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """只返回当前用户的账户（优化查询）"""
        queryset = Account.objects.filter(user=self.request.user)

        # 优化：预加载子账户和持仓数据
        queryset = queryset.prefetch_related(
            'children',  # 预加载子账户
            'children__positions',  # 预加载子账户的持仓
            'children__positions__fund',  # 预加载持仓的基金
            'positions',  # 预加载自己的持仓
            'positions__fund',  # 预加载持仓的基金
        )

        return queryset

    def perform_create(self, serializer):
        """创建账户时自动设置用户"""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get'])
    def positions(self, request, pk=None):
        """获取账户的所有持仓"""
        account = self.get_object()
        positions = Position.objects.filter(account=account).select_related('fund')
        serializer = PositionSerializer(positions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def delete_info(self, request, pk=None):
        """获取账户删除信息（用于前端确认对话框）"""
        from decimal import Decimal
        import logging

        logger = logging.getLogger(__name__)
        account = self.get_object()

        # 检查是否为默认账户
        if account.is_default:
            return Response({
                'can_delete': False,
                'is_default': True,
                'message': '默认账户不能删除',
                'children_count': 0,
                'positions_count': 0,
                'total_cost': '0.00',
            })

        # 统计子账户数量
        children_count = account.children.count()

        # 统计持仓数量和总成本（包括子账户的持仓）
        all_account_ids = [account.id]
        if children_count > 0:
            all_account_ids.extend(account.children.values_list('id', flat=True))

        positions = Position.objects.filter(account_id__in=all_account_ids)
        positions_count = positions.count()
        total_cost = positions.aggregate(
            total=models.Sum('holding_cost')
        )['total'] or Decimal('0')

        logger.info(
            f"Account delete info: user={request.user.username}, "
            f"account={account.name}, children={children_count}, "
            f"positions={positions_count}, cost={total_cost}"
        )

        return Response({
            'can_delete': True,
            'is_default': False,
            'message': '',
            'children_count': children_count,
            'positions_count': positions_count,
            'total_cost': str(total_cost),
        })

    def destroy(self, request, *args, **kwargs):
        """删除账户（增加安全检查和日志）"""
        import logging

        logger = logging.getLogger(__name__)
        account = self.get_object()

        # 检查是否为默认账户
        if account.is_default:
            logger.warning(
                f"Attempt to delete default account: user={request.user.username}, "
                f"account={account.name}"
            )
            return Response(
                {'detail': '默认账户不能删除'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 记录删除操作日志
        children_count = account.children.count()
        positions_count = Position.objects.filter(
            account__in=[account.id] + list(account.children.values_list('id', flat=True))
        ).count()

        logger.info(
            f"Deleting account: user={request.user.username}, "
            f"account={account.name}, children={children_count}, "
            f"positions={positions_count}"
        )

        # 执行删除
        return super().destroy(request, *args, **kwargs)


class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    """持仓 ViewSet"""

    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """只返回当前用户的持仓"""
        queryset = Position.objects.filter(account__user=self.request.user)

        # 按账户过滤
        account_id = self.request.query_params.get('account')
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        # 按基金过滤
        fund_code = self.request.query_params.get('fund_code')
        if fund_code:
            queryset = queryset.filter(fund__fund_code=fund_code)

        return queryset

    def list(self, request, *args, **kwargs):
        """持仓列表（不分页）"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def recalculate(self, request):
        """重算持仓（管理员）"""
        account_id = request.data.get('account_id')
        recalculate_all_positions(account_id=account_id)
        return Response({'message': '重算完成'})

    @action(detail=True, methods=['delete'])
    def clear(self, request, pk=None):
        """清空持仓（删除所有操作流水）"""
        import logging

        logger = logging.getLogger(__name__)
        position = self.get_object()

        account_id = position.account.id
        fund_id = position.fund.id

        # 删除所有操作流水
        operations = PositionOperation.objects.filter(
            account_id=account_id,
            fund_id=fund_id
        )
        operation_count = operations.count()
        operations.delete()

        logger.info(
            f"Cleared position: user={request.user.username}, "
            f"account={position.account.name}, fund={position.fund.fund_code}, "
            f"operations_deleted={operation_count}"
        )

        # 删除操作后会自动触发持仓重算（通过 signal）
        # 持仓会变为 0 份额或被删除
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        获取账户历史市值

        GET /api/positions/history/?account_id=xxx&days=30

        响应:
        [
            {'date': '2026-02-01', 'value': 10000.00, 'cost': 9500.00},
            {'date': '2026-02-02', 'value': 10200.00, 'cost': 9500.00},
            ...
        ]
        """
        from .services.position_history import calculate_account_history

        account_id = request.query_params.get('account_id')
        days = int(request.query_params.get('days', 30))

        if not account_id:
            return Response(
                {'error': '缺少 account_id 参数'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 验证账户归属
        account = get_object_or_404(Account, id=account_id, user=request.user)

        # 只支持子账户
        if account.parent is None:
            return Response(
                {'error': '暂不支持父账户历史查询'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 计算历史市值
        result = calculate_account_history(account_id, days)

        return Response(result)


class PositionOperationViewSet(viewsets.ModelViewSet):
    """持仓操作 ViewSet"""

    serializer_class = PositionOperationSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """删除操作需要管理员权限"""
        if self.action in ['destroy', 'batch_delete']:
            return [IsAdminUser()]
        return super().get_permissions()

    def get_queryset(self):
        """只返回当前用户的操作（管理员可以看所有）"""
        if self.request.user.is_staff:
            queryset = PositionOperation.objects.all()
        else:
            queryset = PositionOperation.objects.filter(account__user=self.request.user)

        # 按账户过滤
        account_id = self.request.query_params.get('account')
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        # 按基金过滤
        fund_code = self.request.query_params.get('fund_code')
        if fund_code:
            queryset = queryset.filter(fund__fund_code=fund_code)

        return queryset

    def list(self, request, *args, **kwargs):
        """操作流水列表（不分页）"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def batch_delete(self, request):
        """批量删除操作（管理员）"""
        import logging
        import uuid

        logger = logging.getLogger(__name__)
        operation_ids = request.data.get('operation_ids', [])

        if not operation_ids:
            return Response(
                {'error': '操作 ID 列表不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 转换为 UUID 对象
        try:
            uuid_list = [uuid.UUID(op_id) if isinstance(op_id, str) else op_id for op_id in operation_ids]
        except (ValueError, AttributeError) as e:
            return Response(
                {'error': f'无效的操作 ID: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 查询要删除的操作
        operations = PositionOperation.objects.filter(id__in=uuid_list)
        deleted_count = operations.count()

        # 记录日志
        logger.info(
            f"Batch deleting operations: user={request.user.username}, "
            f"count={deleted_count}, ids={operation_ids}"
        )

        # 删除操作（会自动触发持仓重算）
        operations.delete()

        return Response({
            'deleted_count': deleted_count,
            'message': f'成功删除 {deleted_count} 条操作记录'
        })


class WatchlistViewSet(viewsets.ModelViewSet):
    """自选列表 ViewSet"""

    serializer_class = WatchlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """只返回当前用户的自选列表"""
        return Watchlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """创建自选列表时自动设置用户"""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def items(self, request, pk=None):
        """添加基金到自选"""
        watchlist = self.get_object()
        fund_code = request.data.get('fund_code')

        if not fund_code:
            return Response(
                {'error': '基金代码不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            fund = Fund.objects.get(fund_code=fund_code)
        except Fund.DoesNotExist:
            return Response(
                {'error': '基金不存在'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 检查是否已存在
        if WatchlistItem.objects.filter(watchlist=watchlist, fund=fund).exists():
            return Response(
                {'error': '基金已在自选列表中'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 获取最大 order
        from django.db.models import Max
        max_order = WatchlistItem.objects.filter(watchlist=watchlist).aggregate(
            max_order=Max('order')
        )['max_order'] or -1

        item = WatchlistItem.objects.create(
            watchlist=watchlist,
            fund=fund,
            order=max_order + 1
        )

        return Response(
            {'id': item.id, 'fund_code': fund.fund_code},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['delete'], url_path='items/(?P<fund_code>[^/.]+)')
    def remove_item(self, request, pk=None, fund_code=None):
        """从自选移除基金"""
        watchlist = self.get_object()

        try:
            fund = Fund.objects.get(fund_code=fund_code)
            item = WatchlistItem.objects.get(watchlist=watchlist, fund=fund)
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (Fund.DoesNotExist, WatchlistItem.DoesNotExist):
            return Response(
                {'error': '基金不在自选列表中'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['put'])
    def reorder(self, request, pk=None):
        """重新排序自选列表"""
        watchlist = self.get_object()

        # 处理 JSON 和 form data 两种格式
        if hasattr(request.data, 'lists'):
            # QueryDict (form data) - 使用 lists() 获取完整的列表
            fund_codes = dict(request.data.lists()).get('fund_codes', [])
        else:
            # 普通 dict (JSON)
            fund_codes = request.data.get('fund_codes', [])

        if not fund_codes:
            return Response(
                {'error': '基金代码列表不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 更新排序
        for index, fund_code in enumerate(fund_codes):
            try:
                fund = Fund.objects.get(fund_code=fund_code)
                WatchlistItem.objects.filter(
                    watchlist=watchlist,
                    fund=fund
                ).update(order=index)
            except Fund.DoesNotExist:
                pass

        return Response({'message': '排序已更新'})


class SourceViewSet(viewsets.ViewSet):
    """数据源 ViewSet"""

    permission_classes = [AllowAny]

    def list(self, request):
        """列出所有数据源"""
        sources = SourceRegistry.list_sources()
        return Response([{'name': name} for name in sources])

    @action(detail=True, methods=['get'], url_path='accuracy')
    def accuracy(self, request, pk=None):
        """获取数据源整体准确率"""
        source_name = pk
        days = int(request.query_params.get('days', 100))

        # 获取最近 N 天的准确率记录（按记录数量，不按日期）
        records = EstimateAccuracy.objects.filter(
            source_name=source_name,
            error_rate__isnull=False
        ).order_by('-estimate_date')[:days]

        if not records.exists():
            return Response({
                'avg_error_rate': 0,
                'record_count': 0
            })

        total_error = sum(r.error_rate for r in records)
        count = len(records)

        return Response({
            'avg_error_rate': total_error / count if count > 0 else 0,
            'record_count': count
        })


class UserViewSet(viewsets.ViewSet):
    """用户 ViewSet"""

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        """用户注册"""
        # 检查是否允许注册
        if not config.get('allow_register', False):
            return Response(
                {'error': '注册未开放'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # 生成 JWT token
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)

            return Response({
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                }
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='me/summary', permission_classes=[IsAuthenticated])
    def summary(self, request):
        """获取用户资产汇总"""
        user = request.user

        # 统计账户数
        account_count = Account.objects.filter(user=user).count()

        # 统计持仓数和总成本
        positions = Position.objects.filter(account__user=user)
        position_count = positions.count()
        total_cost = sum(p.holding_cost for p in positions)

        # 计算总市值和总盈亏
        total_value = Decimal('0')
        total_pnl = Decimal('0')

        for position in positions:
            if position.fund.latest_nav:
                value = position.fund.latest_nav * position.holding_share
                total_value += value
                total_pnl += position.pnl

        return Response({
            'account_count': account_count,
            'position_count': position_count,
            'total_cost': total_cost,
            'total_value': total_value,
            'total_pnl': total_pnl,
        })


class FundNavHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """基金历史净值 ViewSet（只读）"""

    queryset = FundNavHistory.objects.all()
    serializer_class = FundNavHistorySerializer
    permission_classes = []  # 不需要认证

    def get_queryset(self):
        queryset = super().get_queryset()

        # 按基金代码过滤
        fund_code = self.request.query_params.get('fund_code')
        if fund_code:
            queryset = queryset.filter(fund__fund_code=fund_code)

        # 按日期范围过滤
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            queryset = queryset.filter(nav_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(nav_date__lte=end_date)

        return queryset

    @action(detail=False, methods=['post'])
    def batch_query(self, request):
        """
        批量查询历史净值

        POST /api/nav-history/batch_query/
        {
            "fund_codes": ["000001", "000002"],
            "start_date": "2024-01-01",  // 可选
            "end_date": "2024-12-31",    // 可选
            "nav_date": "2024-06-01"     // 可选，查询单日
        }
        """
        fund_codes = request.data.get('fund_codes', [])
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        nav_date = request.data.get('nav_date')

        if not fund_codes:
            return Response(
                {'error': '缺少 fund_codes 参数'},
                status=status.HTTP_400_BAD_REQUEST
            )

        results = {}
        for fund_code in fund_codes:
            queryset = FundNavHistory.objects.filter(fund__fund_code=fund_code)

            # 单日查询
            if nav_date:
                queryset = queryset.filter(nav_date=nav_date)
            else:
                # 时间段查询
                if start_date:
                    queryset = queryset.filter(nav_date__gte=start_date)
                if end_date:
                    queryset = queryset.filter(nav_date__lte=end_date)

            serializer = self.get_serializer(queryset, many=True)
            results[fund_code] = serializer.data

        return Response(results)

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """
        同步历史净值

        权限规则：
        - 同步 ≤15 个基金：不需要管理员权限
        - 同步 >15 个基金：需要管理员权限

        POST /api/nav-history/sync/
        {
            "fund_codes": ["000001", "000002"],
            "start_date": "2024-01-01",  // 可选
            "end_date": "2024-12-31",    // 可选
        }
        """
        from .services.nav_history import batch_sync_nav_history
        from datetime import datetime

        fund_codes = request.data.get('fund_codes', [])
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if not fund_codes:
            return Response(
                {'error': '缺少 fund_codes 参数'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 权限检查：超过 15 个基金需要管理员权限
        if len(fund_codes) > 15:
            if not request.user.is_authenticated or not request.user.is_staff:
                return Response(
                    {'error': '同步超过 15 个基金需要管理员权限'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # 转换日期格式
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        results = batch_sync_nav_history(fund_codes, start_date, end_date)

        return Response(results)
