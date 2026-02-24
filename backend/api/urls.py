from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, viewsets

# 创建主路由器
router = DefaultRouter()
router.register(r'funds', viewsets.FundViewSet, basename='fund')
router.register(r'accounts', viewsets.AccountViewSet, basename='account')
router.register(r'positions', viewsets.PositionViewSet, basename='position')
router.register(r'watchlists', viewsets.WatchlistViewSet, basename='watchlist')
router.register(r'sources', viewsets.SourceViewSet, basename='source')
router.register(r'users', viewsets.UserViewSet, basename='user')
router.register(r'nav-history', viewsets.FundNavHistoryViewSet, basename='nav-history')

urlpatterns = [
    # 系统管理
    path('health/', views.health, name='health'),

    # Bootstrap 初始化
    path('admin/bootstrap/verify', views.bootstrap_verify, name='bootstrap_verify'),
    path('admin/bootstrap/initialize', views.bootstrap_initialize, name='bootstrap_initialize'),

    # 认证
    path('auth/login', views.login, name='login'),
    path('auth/refresh', views.refresh_token, name='refresh_token'),
    path('auth/me', views.get_current_user, name='get_current_user'),
    path('auth/password', views.change_password, name='change_password'),

    # 持仓操作（单独路由）
    path('positions/operations/', viewsets.PositionOperationViewSet.as_view({
        'get': 'list',
        'post': 'create'
    })),
    path('positions/operations/batch_delete/', viewsets.PositionOperationViewSet.as_view({
        'post': 'batch_delete'
    })),
    path('positions/operations/<uuid:pk>/', viewsets.PositionOperationViewSet.as_view({
        'get': 'retrieve',
        'delete': 'destroy'
    })),

    # API 路由
    path('', include(router.urls)),
]
