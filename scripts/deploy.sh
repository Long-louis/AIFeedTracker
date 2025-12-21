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

# 2. 同步代码到服务器
echo "📦 拉取最新代码..."
ssh "$SERVER" << EOF
set -euo pipefail
cd "$DEPLOY_PATH"
git pull origin main
EOF

# 3. 构建并重启服务
echo "🔨 构建并重启服务..."
ssh "$SERVER" << EOF
set -euo pipefail
cd "$DEPLOY_PATH/deploy"
docker compose build --no-cache
docker compose up -d --remove-orphans
docker image prune -f
echo "✅ 部署完成！"
EOF

echo ""
echo "🎉 部署成功！查看日志："
echo "   ssh $SERVER 'cd $DEPLOY_PATH/deploy && docker compose logs -f'"
