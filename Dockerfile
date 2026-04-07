# syntax=docker/dockerfile:1
# 构建阶段：安装依赖
FROM python:3.11-slim-bullseye AS builder

WORKDIR /app

# 替换 Debian 系统源为清华源（适配 bullseye 版本）
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list

# 安装编译工具（加速源码包构建）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install --no-cache-dir uv -i https://mirrors.aliyun.com/pypi/simple/

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 配置 uv 使用国内镜像源
ENV UV_HTTP_TIMEOUT=600
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV UV_TRUSTED_HOST=mirrors.aliyun.com

# 使用缓存挂载安装依赖（显式指定镜像源）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --index-url https://mirrors.aliyun.com/pypi/simple/

# 运行阶段：精简镜像
FROM python:3.11-slim-bullseye

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

# 从构建阶段复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p data log

# 设置权限
RUN chmod +x /app/main.py

# 设置默认命令
CMD ["python", "main.py", "--mode", "service"]
