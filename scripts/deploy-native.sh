#!/bin/bash
set -euo pipefail

# ============================================
# 原生部署脚本（不使用 Docker）
# 直接在服务器上用 systemd + uv 运行
# ============================================

SERVER="huaweicloud"
DEPLOY_PATH="/opt/aifeedtracker"
SERVICE_NAME="aifeedtracker"

echo "🚀 开始原生部署..."

# 1. 同步 .env 文件
if [ -f .env ]; then
    echo "📤 同步 .env 文件..."
    scp .env "$SERVER:$DEPLOY_PATH/.env"
else
    echo "⚠️  警告：本地未找到 .env 文件"
fi

# 2. 拉取代码并重启服务
echo "📦 拉取代码并重启服务..."
ssh "$SERVER" << 'EOF'
set -euo pipefail
cd /opt/aifeedtracker

# 拉取最新代码
git pull origin main

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "📥 安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 同步依赖（只在 lock 文件变化时才会下载）
echo "📦 同步依赖..."
uv sync --frozen

# 重启 systemd 服务
echo "🔄 重启服务..."
sudo systemctl restart aifeedtracker

# 检查服务状态
sleep 2
if sudo systemctl is-active --quiet aifeedtracker; then
    echo "✅ 服务已启动"
else
    echo "❌ 服务启动失败，查看日志："
    sudo journalctl -u aifeedtracker -n 20 --no-pager
    exit 1
fi
EOF

echo ""
echo "🎉 部署完成！"
echo ""
echo "常用命令："
echo "  查看日志: ssh $SERVER 'sudo journalctl -u $SERVICE_NAME -f'"
echo "  重启服务: ssh $SERVER 'sudo systemctl restart $SERVICE_NAME'"
echo "  停止服务: ssh $SERVER 'sudo systemctl stop $SERVICE_NAME'"
