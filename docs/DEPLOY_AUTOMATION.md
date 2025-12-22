# 服务器部署指南

本项目使用 **systemd 原生运行**（非 Docker），部署于 `huaweicloud` 服务器。

---

## 一次性准备（服务器）

### 1) 安装 uv 和 Python

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### 2) 克隆仓库并配置 Deploy Key

```bash
ssh huaweicloud
cd /opt
git clone git@github.com:Long-louis/AIFeedTracker-private.git aifeedtracker
cd aifeedtracker

# 生成 Deploy Key
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy_key -N ""
cat ~/.ssh/github_deploy_key.pub
# 复制公钥，添加到 GitHub 仓库 Settings → Deploy keys

# 配置 Git 使用该密钥
git config core.sshCommand "ssh -i ~/.ssh/github_deploy_key"
```

### 3) 创建环境配置

```bash
cd /opt/aifeedtracker
cp env.example .env
nano .env
```

必填字段：`FEISHU_TEMPLATE_ID`、`AI_API_KEY`、`AI_SERVICE` 等。

### 4) 安装依赖

```bash
cd /opt/aifeedtracker
uv sync --frozen
```

### 5) 配置 systemd 服务

```bash
sudo cp deploy/aifeedtracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aifeedtracker
sudo systemctl start aifeedtracker
```

---

## 日常使用

### 更新代码（最常用）

```bash
./scripts/deploy-native.sh
```

脚本会：推送代码 → 服务器 git pull → 重启服务。只需几秒钟。

### 查看实时日志

```bash
ssh huaweicloud 'sudo journalctl -u aifeedtracker -f'
```

### 重启/停止服务

```bash
ssh huaweicloud 'sudo systemctl restart aifeedtracker'
ssh huaweicloud 'sudo systemctl stop aifeedtracker'
```

### 更新创作者配置（热重载）

1. 本地修改 `data/bilibili_creators.json`
2. `git commit && git push private main`
3. `ssh huaweicloud 'cd /opt/aifeedtracker && git pull'`
4. 等待 10 秒，服务自动重载（无需重启）

---

## 回滚

```bash
ssh huaweicloud
cd /opt/aifeedtracker
git log --oneline
git reset --hard <旧提交hash>
sudo systemctl restart aifeedtracker
```
