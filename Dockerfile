# TaskFlow 自动化测试框架镜像: 被测系统 + 测试框架一体化
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright

WORKDIR /app

# 国内网络: 将 Debian 官方源替换为阿里云镜像, 避免 apt 下载 502
RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' \
    /etc/apt/sources.list.d/debian.sources

# 先装系统依赖再装 Python 包, 充分利用 Docker 缓存层
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装 Playwright 浏览器内核及系统依赖
RUN playwright install --with-deps chromium

COPY . .

# 默认命令: 运行全部自动化用例
CMD ["python", "run.py", "test"]
