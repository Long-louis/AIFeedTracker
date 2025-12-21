#!/bin/bash
set -euo pipefail

# 配置
SERVER="huaweicloud"
DEPLOY_PATH="/opt/aifeedtracker"

echo "🚀 开始部署到服务器..."

# 1. 同步 .env 文件（如果存在）
if [ -f .env ]; then
    echo "📤 同步 .env 文件..."
    scp .env "$SERVER:$DEPLOY_PATH/deploy/.env"
else
    echo "⚠️  警告：本地未找到 .env 文件"
fi

# 2. 同步代码到服务器（配置文件已通过 Git 同步）
echo "📦 拉取最新代码..."
ssh "$SERVER" << EOF
set -euo pipefail
cd "$DEPLOY_PATH"
git pull origin main
EOF

# 3. 构建并重启服务（默认不构建）
# 用法: ./scripts/deploy.sh [--rebuild|--build|-b]   （带 --rebuild 则强制重新构建镜像）
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "用法: $0 [--rebuild|--build|-b]"
    exit 0
fi

REBUILD=false
if [ "${1:-}" = "--rebuild" ] || [ "${1:-}" = "--build" ] || [ "${1:-}" = "-b" ]; then
    REBUILD=true
fi

echo "🔨 重启服务 (rebuild=${REBUILD})..."
ssh "$SERVER" << EOF
set -euo pipefail
cd "$DEPLOY_PATH/deploy"
if [ "${REBUILD}" = "true" ]; then
    echo "🔧 正在重新构建镜像..."
    docker compose build --no-cache
fi
# 默认使用 --no-build 避免触发下载/编译，除非显式请求重建
docker compose up -d --remove-orphans --no-build
docker image prune -f
echo "✅ 部署完成！"
EOF

echo ""
echo "🎉 操作完成！查看实时日志："
echo "   ssh $SERVER 'cd $DEPLOY_PATH/deploy && docker compose logs -f'"
