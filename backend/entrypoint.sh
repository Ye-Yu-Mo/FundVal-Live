#!/bin/bash
set -e

echo "=========================================="
echo "  Fundval Backend Starting"
echo "=========================================="

# 等待数据库就绪
echo "Waiting for database..."
while ! pg_isready -h ${POSTGRES_HOST:-db} -p ${POSTGRES_PORT:-5432} -U $POSTGRES_USER > /dev/null 2>&1; do
    sleep 1
done
echo "✓ Database ready"

# 运行数据库迁移
echo "Running migrations..."
python manage.py migrate --noinput
echo "✓ Migrations complete"

# 收集静态文件
echo "Collecting static files..."
python manage.py collectstatic --noinput
echo "✓ Static files collected"

# 检查系统初始化状态
echo "=========================================="
python manage.py check_bootstrap
echo "=========================================="

# 首次启动自动同步基金数据
echo "Checking fund data..."
python manage.py sync_funds --if-empty
echo "✓ Fund data check complete"

# 启动应用
exec "$@"
