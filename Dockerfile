# 使用 Python 3.11 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 替换 Debian 系统源为清华源（适配 bullseye 版本）
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bullseye-updates main contrib non-free" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bullseye-security main contrib non-free" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 uv (Python 包管理器)
RUN pip install uv -i https://mirrors.aliyun.com/pypi/simple/

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装项目依赖
RUN uv sync --frozen

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p data log

# 设置权限
RUN chmod +x /app/main.py

# 设置默认命令
CMD ["uv", "run", "python", "main.py", "--mode", "service"]