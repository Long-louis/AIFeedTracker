#!/bin/bash
# 监控服务日志和凭证文件

echo "开始监控服务状态..."
echo "按 Ctrl+C 停止监控"
echo ""

while true; do
    clear
    echo "=== 最新日志 (最后 15 行) ==="
    tail -15 /tmp/service_test.log
    echo ""
    echo "=== 凭证文件状态 ==="
    if [ -f /Users/macbookair/code/AIFeedTracker/data/bilibili_auth.json ]; then
        echo "✅ bilibili_auth.json 存在"
        echo "文件大小: $(wc -c < /Users/macbookair/code/AIFeedTracker/data/bilibili_auth.json) 字节"
        echo "最后修改: $(stat -f "%Sm" /Users/macbookair/code/AIFeedTracker/data/bilibili_auth.json)"
        
        # 检查是否有 SESSDATA
        if grep -q "SESSDATA" /Users/macbookair/code/AIFeedTracker/data/bilibili_auth.json 2>/dev/null; then
            echo "✅ 包含 SESSDATA 凭证"
        else
            echo "⚠️ 未包含 SESSDATA"
        fi
    else
        echo "❌ bilibili_auth.json 不存在"
    fi
    echo ""
    echo "$(date '+%H:%M:%S') - 等待 3 秒后刷新..."
    sleep 3
done
