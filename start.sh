#!/bin/bash

# Fundval 启动脚本

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# PID 文件目录
PID_DIR="./pids"
mkdir -p "$PID_DIR"

# 日志目录
LOG_DIR="./logs"
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "    Fundval 服务启动"
echo "=========================================="
echo ""

# 检查服务是否已运行
check_running() {
    local service=$1
    local pid_file="$PID_DIR/$service.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

# 启动 Redis（如果需要）
start_redis() {
    echo "检查 Redis..."
    REDIS_BIN="/Volumes/1T SSD/SynologyDrive/web/FundVal/redis-server"
    if [ -x "$REDIS_BIN" ]; then
        if check_running "redis"; then
            echo -e "${YELLOW}Redis 已在运行${NC}"
        else
            echo "启动 Redis..."
            "$REDIS_BIN" --daemonize yes --pidfile "$PID_DIR/redis.pid" --logfile "$LOG_DIR/redis.log"
            echo -e "${GREEN}✓ Redis 已启动${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Redis 未安装，Celery 功能将不可用${NC}"
    fi
    echo ""
}

# 启动 Celery Worker
start_celery_worker() {
    echo "启动 Celery Worker..."

    if check_running "celery-worker"; then
        echo -e "${YELLOW}Celery Worker 已在运行${NC}"
    else
        cd backend
        nohup /Users/oscar/.local/bin/uv run celery -A fundval worker --loglevel=info \
            --pidfile="../$PID_DIR/celery-worker.pid" \
            > "../$LOG_DIR/celery-worker.log" 2>&1 &
        cd ..
        sleep 2
        echo -e "${GREEN}✓ Celery Worker 已启动${NC}"
    fi
    echo ""
}

# 启动 Celery Beat（定时任务）
start_celery_beat() {
    echo "启动 Celery Beat..."

    if check_running "celery-beat"; then
        echo -e "${YELLOW}Celery Beat 已在运行${NC}"
    else
        cd backend
        nohup /Users/oscar/.local/bin/uv run celery -A fundval beat --loglevel=info \
            --pidfile="../$PID_DIR/celery-beat.pid" \
            --schedule="../$LOG_DIR/celerybeat-schedule" \
            > "../$LOG_DIR/celery-beat.log" 2>&1 &
        cd ..
        sleep 2
        echo -e "${GREEN}✓ Celery Beat 已启动${NC}"
    fi
    echo ""
}

# 启动 Django 服务
start_django() {
    echo "启动 Django 服务..."

    if check_running "django"; then
        echo -e "${YELLOW}Django 服务已在运行${NC}"
    else
        cd backend

        # 从 config.json 读取端口配置
        if [ -f "config.json" ]; then
            SERVER_PORT=$(/Users/oscar/.local/bin/uv run python -c "import json; print(json.load(open('config.json')).get('port', 8000))" 2>/dev/null || echo "8000")
        else
            echo -e "${YELLOW}⚠ config.json 不存在，使用默认端口 8000${NC}"
            SERVER_PORT="8000"
        fi

        echo "监听地址: 0.0.0.0:$SERVER_PORT"

        nohup /Users/oscar/.local/bin/uv run python manage.py runserver "0.0.0.0:$SERVER_PORT" \
            > "../$LOG_DIR/django.log" 2>&1 &
        echo $! > "../$PID_DIR/django.pid"
        cd ..
        sleep 3
        echo -e "${GREEN}✓ Django 服务已启动${NC}"
    fi
    echo ""
}

# 显示服务状态
show_status() {
    echo "=========================================="
    echo "    服务状态"
    echo "=========================================="

    if check_running "redis"; then
        echo -e "Redis:         ${GREEN}运行中${NC}"
    else
        echo -e "Redis:         ${RED}未运行${NC}"
    fi

    if check_running "celery-worker"; then
        echo -e "Celery Worker: ${GREEN}运行中${NC}"
    else
        echo -e "Celery Worker: ${RED}未运行${NC}"
    fi

    if check_running "celery-beat"; then
        echo -e "Celery Beat:   ${GREEN}运行中${NC}"
    else
        echo -e "Celery Beat:   ${RED}未运行${NC}"
    fi

    if check_running "django"; then
        echo -e "Django:        ${GREEN}运行中${NC}"
    else
        echo -e "Django:        ${RED}未运行${NC}"
    fi

    echo ""
}

# 主流程
main() {
    start_redis
    start_celery_worker
    start_celery_beat
    start_django

    show_status

    echo "=========================================="
    echo "    启动完成！"
    echo "=========================================="
    echo ""

    # 读取实际端口
    if [ -f "backend/config.json" ]; then
        ACTUAL_PORT=$(/Users/oscar/.local/bin/uv run python -c "import json; print(json.load(open('backend/config.json')).get('port', 8000))" 2>/dev/null || echo "8000")
    else
        ACTUAL_PORT="8000"
    fi

    echo "访问地址: http://localhost:$ACTUAL_PORT"
    echo ""
    echo "查看日志:"
    echo "  Django:        tail -f $LOG_DIR/django.log"
    echo "  Celery Worker: tail -f $LOG_DIR/celery-worker.log"
    echo "  Celery Beat:   tail -f $LOG_DIR/celery-beat.log"
    echo ""
    echo "停止服务: ./stop.sh"
    echo ""
}

main
