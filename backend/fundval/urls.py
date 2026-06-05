"""
URL configuration for fundval project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.conf import settings
from django.views.static import serve
import os


def serve_frontend(request, path=""):
    """服务前端静态文件"""
    frontend_dir = settings.FRONTEND_BUILD_DIR

    # 如果请求的是文件且存在，直接返回
    file_path = os.path.join(frontend_dir, path)
    if os.path.isfile(file_path):
        return serve(request, path, document_root=frontend_dir)

    # 否则返回 index.html（用于 SPA 路由）
    return serve(request, "index.html", document_root=frontend_dir)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # 前端路由（catch-all，必须放在最后）
    re_path(r"^(?!api/)(?P<path>.*)$", serve_frontend, name="frontend"),
]
