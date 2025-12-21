#!/bin/bash
set -euo pipefail

# 检查是否有提交信息
if [ $# -eq 0 ]; then
    echo "用法: ./scripts/commit-and-deploy.sh \"提交信息\""
    exit 1
fi

COMMIT_MSG="$1"

echo "📝 提交代码..."
git add .
git commit -m "$COMMIT_MSG" || echo "没有需要提交的更改"

echo "⬆️  推送到 GitHub..."
git push

echo ""
./scripts/deploy.sh
