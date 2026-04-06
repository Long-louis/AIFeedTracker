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

# 3. 重启服务（默认不构建）
# 用法: ./scripts/deploy.sh [--build|-b|--rebuild]   （--build 使用缓存构建；--rebuild 强制 no-cache）
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "用法: $0 [--build|-b|--rebuild]"
    exit 0
fi

BUILD_MODE="no-build"
if [ "${1:-}" = "--build" ] || [ "${1:-}" = "-b" ]; then
    BUILD_MODE="build"
fi
if [ "${1:-}" = "--rebuild" ]; then
    BUILD_MODE="rebuild"
fi

echo "🔨 重启服务 (mode=${BUILD_MODE})..."
ssh "$SERVER" << EOF
set -euo pipefail
cd "$DEPLOY_PATH/deploy"

# 启用 BuildKit 以支持缓存挂载
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

if [ "${BUILD_MODE}" = "rebuild" ]; then
    echo "🔧 正在重新构建镜像 (no-cache)..."
    docker compose build --no-cache
fi
if [ "${BUILD_MODE}" = "build" ]; then
    echo "🔧 正在构建镜像 (with cache)..."
    docker compose build
fi
# 默认使用 --no-build 避免触发下载/编译；若 build/rebuild 已执行，则直接 up
if [ "${BUILD_MODE}" = "no-build" ]; then
    docker compose up -d --remove-orphans --no-build
else
    docker compose up -d --remove-orphans
fi
echo "✅ 部署完成！"
EOF

echo ""
echo "🎉 操作完成！查看实时日志："
echo "   ssh $SERVER 'cd $DEPLOY_PATH/deploy && docker compose logs -f'"
