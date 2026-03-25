# Fundval

![GitHub stars](https://img.shields.io/github/stars/Ye-Yu-Mo/FundVal-Live?style=social)
![GitHub views](https://komarev.com/ghpvc/?username=Ye-Yu-Mo&repo=FundVal-Live&color=blue&style=flat-square&label=views)

**盘中基金实时估值与逻辑审计系统**

拒绝黑箱，拒绝情绪化叙事。基于透明的持仓穿透 + 实时行情加权计算 + 硬核数学模型，让基金估值回归数学事实。


试用网址：https://fund.jasxu.dpdns.org/

**警告**：试用环境请勿使用真实持仓数据和 API Key

服务器内存和 CPU 性能较低，仅做使用演示

---

## 加入讨论群组

[issue - 讨论群组](https://github.com/Ye-Yu-Mo/FundVal-Live/issues/41)

## 遇到问题？

**[问题排查手册](docs/问题排查.md)** — 涵盖注册、部署、数据源、持仓计算等常见问题的完整排查指南

## 功能特性

- **实时估值**：基于持仓穿透 + 实时行情加权计算，支持东方财富、养基宝、小倍养基三数据源
- **AI 分析**：接入任意 OpenAI 协议大模型，内置默认提示词模板，支持基金和持仓两个维度分析
- **养基宝集成**：扫码登录、一键导入持仓、实时估值同步
- **小倍养基集成**：手机号 + 短信验证码登录，按账户分组一键导入全部持仓
- **持仓管理**：多账户、父子账户结构，支持买入/卖出流水，自动重算持仓，支持切换默认账户
- **多渠道通知**：基金涨跌幅阈值触发，支持 Webhook（飞书/钉钉/企业微信）和自定义 SMTP 邮件
- **指数基金成分股**：基金详情页展示 Top 10 成分股实时行情，支持场内溢价监控
- **历史净值**：净值走势图，支持 1W / 1M / 3M / 6M / 1Y / ALL 时间范围
- **估值准确率**：记录每日估值误差，统计各数据源准确率
- **自选列表**：自定义基金自选分组
- **数据源偏好**：用户级别数据源切换，偏好持久化


## 快速开始

整个项目分为服务端 客户端两部分

服务端可以使用 Docker 或手动部署

### 最快方式（Docker）

#### 1. 下载配置文件

```bash
# 下载 docker-compose.yml
curl -O https://raw.githubusercontent.com/Ye-Yu-Mo/FundVal-Live/main/docker-compose.yml

# 下载环境变量模板
curl -O https://raw.githubusercontent.com/Ye-Yu-Mo/FundVal-Live/main/.env.example

# 复制为 .env 并修改配置
cp .env.example .env
```

#### 2. 修改配置（可选）

编辑 `.env` 文件，自定义配置：

```bash
# 数据库配置
POSTGRES_DB=fundval
POSTGRES_USER=fundval
POSTGRES_PASSWORD=change_me_in_production  # ⚠️ 生产环境请修改
POSTGRES_PORT=5432
POSTGRES_IMAGE=postgres:16-alpine  # 数据库镜像版本

# Django 配置
SECRET_KEY=change_me_in_production_use_random_string  # ⚠️ 生产环境请修改
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1  # 生产环境添加你的域名

# Redis 配置
REDIS_IMAGE=redis:7-alpine  # Redis 镜像版本
REDIS_URL=redis://redis:6379/0

# 应用配置
ALLOW_REGISTER=false  # 是否允许用户注册

# 前端配置
FRONTEND_PORT=21345  # 前端访问端口
FRONTEND_IMAGE=jasamine/fundval-frontend:latest  # 前端镜像版本

# 后端配置
BACKEND_IMAGE=jasamine/fundval-backend:latest  # 后端镜像版本
GUNICORN_WORKERS=4  # Gunicorn 工作进程数（根据 CPU 核心数调整）

# Celery 配置
CELERY_LOGLEVEL=info  # 日志级别：debug, info, warning, error
```

**性能调优建议**：
- `GUNICORN_WORKERS`：推荐设置为 `(CPU 核心数 × 2) + 1`
- `CELERY_LOGLEVEL`：生产环境建议使用 `warning` 减少日志输出
- 高负载场景可使用 `POSTGRES_IMAGE=postgres:16` 替代 alpine 版本

**自定义数据库端口**（可选）：
如需从宿主机直接访问数据库（调试/备份），需同时修改两处：
1. 在 `.env` 中设置 `POSTGRES_PORT=5432`（或其他端口）
2. 在 `docker-compose.yml` 中取消注释 `db.ports` 配置行

#### 3. 启动服务

```bash
docker-compose up -d
```

#### 4. 访问应用

访问 http://localhost:21345（或你在 `.env` 中配置的端口）

**首次启动**：
- 系统会自动运行数据库迁移
- 自动同步基金数据（需要等待几分钟）
- 控制台会显示 **Bootstrap Key**，用于初始化管理员账户

**查看日志**：

```bash
docker-compose logs -f backend  # 查看后端日志和 Bootstrap Key
```

### 手动部署

#### 必需组件
- **Python**: 3.13+
- **Node.js**: 20+
- **npm**: 9+
- **uv**: Python 包管理器
- **数据库**: SQLite 3.x 或 PostgreSQL 16+

#### 可选组件
- **Redis**: 用于 Celery 任务队列（可选）
- **Nginx**: 生产环境反向代理（推荐）

#### 开始部署

```bash
git clone https://github.com/Ye-Yu-Mo/FundVal-Live.git
cd FundVal-Live
```

运行构建脚本

```bash
chmod +x build.sh
./build.sh
```

依次选择 构建前端，端口号设定，数据库初始化，静态文件收集

```bash
chmod +x start.sh stop.sh
./start.sh
```

### 管理员设置（必读）

启动之后，需要在日志中获取 Bootstrap Key

- Docker 用户：`docker-compose logs backend | grep 'BOOTSTRAP KEY'`
- 手动部署用户：运行 `./start.sh` 即可看到

然后访问 `http://localhost:21345/initialize`（需要换成你自己的 IP + 端口）进行初始化

填入 BOOTSTRAP KEY，配置管理员账户和密码，是否开通注册功能

如果开启注册功能，需要**重新启动后端**

## 技术栈

- **Frontend**: React 19 + Vite + Ant Design + ECharts
- **Backend**: Django 6 + DRF + Celery
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **Platform**: Web + Desktop (Tauri) + Android (Capacitor)

### 客户端

可以通过Web页面直接访问使用，无需客户端

其他版本客户端，需前往 [Releases](https://github.com/Ye-Yu-Mo/FundVal-Live/releases/latest) 下载最新版本：

目前支持

* 安卓客户端
* macOS (ARM64)
* macOS (x86_64)
* Windows
* Linux

## 架构

```mermaid
graph TD
    subgraph Clients["客户端层"]
        Browser["Web Browser"]
        Desktop["Desktop · Tauri"]
        Android["Android · Capacitor"]
    end

    subgraph FE["前端容器 · Nginx"]
        React["React 19 · Ant Design · ECharts"]
    end

    subgraph BE["后端容器 · Gunicorn"]
        Django["Django 6 + DRF\nAPI · Auth · 业务逻辑"]
    end

    subgraph Queue["任务队列 · Celery"]
        Beat["Beat · 定时调度"]
        Worker["Worker · 异步执行"]
    end

    subgraph Store["存储层"]
        PG[("PostgreSQL 16")]
        Redis[("Redis 7")]
    end

    subgraph Ext["外部数据源"]
        EM["东方财富"]
        YJB["养基宝"]
        XBYJ["小倍养基"]
    end

    Browser & Desktop & Android -->|HTTP| FE
    FE -->|静态文件| React
    FE -->|"/api/*"| BE
    BE <-->|读写| PG
    BE <-->|缓存 / Broker| Redis
    Beat -->|任务入队| Redis
    Redis -->|任务分发| Worker
    Worker -->|数据抓取| EM & YJB & XBYJ
    Django -->|按需请求| EM & YJB & XBYJ
```

前端通过 Nginx 反向代理 `/api/` 到后端。Celery Beat 定时触发净值同步，Worker 并发抓取多数据源后写入 PostgreSQL。

### 容器启动流程

Docker 容器启动时，`backend/entrypoint.sh` 会自动执行：

1. 等待数据库就绪
2. 运行数据库迁移 (`migrate`)
3. 收集静态文件 (`collectstatic`)
4. 检查系统初始化状态 (`check_bootstrap`)
5. **自动同步基金数据**（仅在数据库为空时，`sync_funds --if-empty`）
6. 启动应用

如需手动同步基金数据：

```bash
# Docker 环境
docker-compose exec backend python manage.py sync_funds

# 手动部署
cd backend && uv run python manage.py sync_funds
```

## 项目结构

```
fundval/
├── frontend/          # React 前端
├── backend/           # Django 后端
│   ├── api/
│   │   ├── sources/   # 数据源（东方财富、养基宝、小倍养基）
│   │   └── services/  # 业务逻辑（持仓计算、养基宝/小倍养基导入）
│   └── entrypoint.sh  # Docker 启动脚本（自动迁移）
├── docker-compose.yml # Docker 编排
├── start.sh           # 手动部署启动脚本（自动迁移）
└── .github/workflows/ # CI/CD
```


---

## 开源协议

本项目采用 **GNU Affero General Public License v3.0 (AGPL-3.0)** 开源协议。

**这意味着**：
- 你可以自由使用、修改、分发本软件
- 个人使用无需开源你的修改
- 如果你用本项目代码提供网络服务（SaaS），必须开源你的修改
- 衍生作品必须使用相同协议

**为什么选择 AGPL-3.0？**
- 金融工具需要透明度，用户有权知道估值逻辑
- 防止闭源商业化，确保改进回流社区
- 保护开源生态，避免"拿来主义"

详见 [LICENSE](LICENSE) 文件。

---

## 免责声明

本项目提供的数据与分析仅供技术研究使用，不构成任何投资建议。市场有风险，代码无绝对，交易需谨慎。

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Ye-Yu-Mo/FundVal-Live&type=date&legend=top-left)](https://www.star-history.com/#Ye-Yu-Mo/FundVal-Live&type=date&legend=top-left)
