#!/bin/bash

# Fundval 构建脚本（交互式）

set -e

echo "=========================================="
echo "    Fundval 项目构建向导"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查依赖
check_dependencies() {
    echo "检查依赖..."

    if ! command -v node &> /dev/null; then
        echo -e "${RED}✗ Node.js 未安装${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Node.js 已安装: $(node --version)${NC}"

    if ! command -v npm &> /dev/null; then
        echo -e "${RED}✗ npm 未安装${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ npm 已安装: $(npm --version)${NC}"

    if ! command -v uv &> /dev/null; then
        echo -e "${RED}✗ uv 未安装${NC}"
        echo "请访问 https://docs.astral.sh/uv/ 安装 uv"
        exit 1
    fi
    echo -e "${GREEN}✓ uv 已安装: $(uv --version)${NC}"

    echo ""
}

# 构建前端
build_frontend() {
    echo "=========================================="
    echo "1. 构建前端"
    echo "=========================================="

    read -p "是否构建前端？(Y/n): " build_fe
    build_fe=${build_fe:-Y}

    if [[ $build_fe =~ ^[Yy]$ ]]; then
        echo "进入前端目录..."
        cd frontend

        echo "安装依赖..."
        npm install

        echo "构建前端..."
        npm run build

        if [ -d "dist" ]; then
            echo -e "${GREEN}✓ 前端构建完成${NC}"
        else
            echo -e "${RED}✗ 前端构建失败${NC}"
            exit 1
        fi

        cd ..
    else
        echo "跳过前端构建"
    fi
    echo ""
}

# 初始化数据库
init_database() {
    echo "=========================================="
    echo "2. 初始化数据库"
    echo "=========================================="

    read -p "是否需要初始化数据库？(Y/n): " init_db
    init_db=${init_db:-Y}

    if [[ ! $init_db =~ ^[Yy]$ ]]; then
        echo "跳过数据库初始化"
        cd backend
        # 确保 config.json 存在
        if [ ! -f "config.json" ]; then
            echo -e "${YELLOW}⚠ config.json 不存在，请手动创建${NC}"
        fi
        cd ..
        echo ""
        return
    fi

    cd backend

    # 配置监听端口
    echo ""
    read -p "Django 服务监听端口 (默认: 8000): " server_port
    server_port=${server_port:-8000}

    # 选择数据库类型
    echo ""
    echo "请选择数据库类型："
    echo "  1) SQLite（默认，适合开发和小规模部署）"
    echo "  2) PostgreSQL（推荐生产环境）"
    echo ""
    read -p "请选择 (1/2): " db_choice
    db_choice=${db_choice:-1}

    if [ "$db_choice" = "2" ]; then
        echo ""
        echo "配置 PostgreSQL..."
        read -p "数据库主机 (默认: localhost): " db_host
        db_host=${db_host:-localhost}

        read -p "数据库端口 (默认: 5432): " db_port
        db_port=${db_port:-5432}

        read -p "数据库名称 (默认: fundval): " db_name
        db_name=${db_name:-fundval}

        read -p "数据库用户: " db_user
        read -sp "数据库密码: " db_password
        echo ""

        # 检查 PostgreSQL 是否可连接
        echo "测试数据库连接..."
        if command -v psql &> /dev/null; then
            if PGPASSWORD="$db_password" psql -h "$db_host" -p "$db_port" -U "$db_user" -d postgres -c "SELECT 1" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ 数据库连接成功${NC}"

                # 检查数据库是否存在
                db_exists=$(PGPASSWORD="$db_password" psql -h "$db_host" -p "$db_port" -U "$db_user" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db_name'")

                if [ "$db_exists" != "1" ]; then
                    echo "创建数据库 $db_name..."
                    PGPASSWORD="$db_password" psql -h "$db_host" -p "$db_port" -U "$db_user" -d postgres -c "CREATE DATABASE $db_name;"
                    echo -e "${GREEN}✓ 数据库创建成功${NC}"
                else
                    echo -e "${YELLOW}数据库 $db_name 已存在${NC}"
                fi
            else
                echo -e "${RED}✗ 数据库连接失败${NC}"
                echo "请检查数据库配置和权限"
                exit 1
            fi
        else
            echo -e "${YELLOW}⚠ psql 未安装，跳过数据库创建检查${NC}"
        fi

        # 更新 config.json
        echo "更新配置文件..."
        cat > config.json << JSON_EOF
{
  "port": $server_port,
  "db_type": "postgresql",
  "db_config": {
    "host": "$db_host",
    "port": $db_port,
    "name": "$db_name",
    "user": "$db_user",
    "password": "$db_password"
  },
  "allow_register": false,
  "system_initialized": false,
  "debug": false,
  "estimate_cache_ttl": 5
}
JSON_EOF
        echo -e "${GREEN}✓ 配置文件已更新${NC}"
    else
        echo "使用 SQLite 数据库"

        # 检查数据库是否存在
        if [ -f "db.sqlite3" ]; then
            echo -e "${YELLOW}数据库文件已存在${NC}"
            read -p "是否重新创建数据库？(y/N): " recreate_db
            recreate_db=${recreate_db:-N}

            if [[ $recreate_db =~ ^[Yy]$ ]]; then
                echo "备份现有数据库..."
                cp db.sqlite3 "db.sqlite3.backup.$(date +%Y%m%d_%H%M%S)"
                echo -e "${GREEN}✓ 数据库已备份${NC}"

                echo "删除现有数据库..."
                rm -f db.sqlite3
            fi
        fi

        # 确保 config.json 存在
        if [ ! -f "config.json" ]; then
            cat > config.json << JSON_EOF
{
  "port": $server_port,
  "db_type": "sqlite",
  "db_config": {
    "name": "db.sqlite3"
  },
  "allow_register": false,
  "system_initialized": false,
  "debug": false,
  "estimate_cache_ttl": 5
}
JSON_EOF
            echo -e "${GREEN}✓ 配置文件已创建${NC}"
        fi
    fi

    echo ""
    read -p "是否执行数据库迁移？(Y/n): " run_migrate
    run_migrate=${run_migrate:-Y}

    if [[ $run_migrate =~ ^[Yy]$ ]]; then
        echo "执行数据库迁移..."
        uv run python manage.py migrate
        echo -e "${GREEN}✓ 数据库迁移完成${NC}"
    else
        echo "跳过数据库迁移"
    fi

    # 检查是否需要创建超级用户
    echo ""
    read -p "是否需要创建管理员账户？(Y/n): " create_admin
    create_admin=${create_admin:-Y}

    if [[ $create_admin =~ ^[Yy]$ ]]; then
        echo "创建管理员账户..."
        uv run python manage.py createsuperuser
    fi

    cd ..
    echo ""
}

# 收集静态文件
collect_static() {
    echo "=========================================="
    echo "3. 收集静态文件"
    echo "=========================================="

    cd backend

    echo "收集静态文件..."
    uv run python manage.py collectstatic --noinput
    echo -e "${GREEN}✓ 静态文件收集完成${NC}"

    cd ..
    echo ""
}

# 生成启动脚本
generate_scripts() {
    echo "=========================================="
    echo "4. 生成启动脚本"
    echo "=========================================="

    echo "生成 start.sh 和 stop.sh..."
    # 这些脚本会在后面单独创建
    echo -e "${GREEN}✓ 启动脚本已准备${NC}"
    echo ""
}

# 主流程
main() {
    check_dependencies
    build_frontend
    init_database
    collect_static
    generate_scripts

    echo "=========================================="
    echo "    构建完成！"
    echo "=========================================="
    echo ""
    echo "下一步："
    echo "  1. 启动服务: ./start.sh"
    echo "  2. 停止服务: ./stop.sh"

    # 读取实际端口
    if [ -f "backend/config.json" ]; then
        ACTUAL_PORT=$(python3 -c "import json; print(json.load(open('backend/config.json')).get('port', 8000))" 2>/dev/null || echo "8000")
    else
        ACTUAL_PORT="8000"
    fi

    echo "  3. 访问应用: http://localhost:$ACTUAL_PORT"
    echo ""
}

main
