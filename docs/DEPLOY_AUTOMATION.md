# 本地部署指南

使用本地脚本直接部署到服务器。

---

## 一次性准备（服务器）

### 1) 安装 Docker 与 Compose

```bash
# 参考：https://docs.docker.com/engine/install/
```

### 2) 克隆仓库并配置 Deploy Key

```bash
ssh <你的服务器>
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
cd /opt/aifeedtracker/deploy
cp .env.example .env
nano .env
```

必填字段：
- `FEISHU_TEMPLATE_ID`
- `AI_API_KEY`
- `AI_SERVICE`

---

## 日常使用

### 更新代码/配置（本地脚本部署）
推荐使用仓库内的部署脚本（`scripts/deploy.sh` 与 `scripts/commit-and-deploy.sh`）：

- `./scripts/deploy.sh`：将本地 `.env`（如果存在）通过 `scp` 同步到服务器，然后 SSH 执行 `git pull`、`docker compose build`、`docker compose up -d` 完成部署。
- `./scripts/commit-and-deploy.sh "提交信息"`：一键提交、push 并触发 `deploy.sh`，适合常规工作流。

使用示例：

1. 本地修改代码或配置文件（包括 `data/*.json` 与本地 `.env`）
2. 提交并部署（推荐）：

```bash
./scripts/commit-and-deploy.sh "更新配置"
```

或手动分步骤：

```bash
git push
./scripts/deploy.sh
```

**安全说明**：`.env` 不应加入 Git（仍然在 `.gitignore` 中），脚本会通过 `scp` 将本地 `.env` 复制到服务器；请确保本地机器安全。

### 手动重启服务
```bash
ssh huaweicloud
cd /opt/aifeedtracker/deploy
docker compose restart
```

### 查看日志
```bash
ssh huaweicloud
cd /opt/aifeedtracker/deploy
docker compose logs -f
```

### 回滚到旧版本
```bash
ssh huaweicloud
cd /opt/aifeedtracker
git log --oneline  # 查看提交历史
git reset --hard <某个旧提交的hash>
cd deploy
docker compose build
docker compose up -d
```

---

## 常见问题

### 1) 为什么不用镜像仓库（GHCR）？

对于个人单服务器场景，直接在服务器构建更简单：
- ✅ 不需要配置 PAT 和镜像仓库登录
- ✅ 不需要管理镜像版本和标签
- ✅ 流程更直观易懂

镜像仓库适合"一次构建、多处部署"的团队/生产场景。

### 2) 配置文件会泄露吗？

不会。你的仓库是私有的，且：
- `.env`（包含 API 密钥）仍然在 `.gitignore` 中，不会进入 Git
- `data/*.json`（业务配置）进入 Git 但仅在私有仓库中可见

### 3) 服务器构建会很慢吗？

首次构建约 2-3 分钟。之后 Docker 会缓存镜像层，增量构建通常 30 秒内完成。
