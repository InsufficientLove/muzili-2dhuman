# 20250825_update: 允许通过构建参数切换基础镜像以绕过受限镜像源
# 默认使用 python:3.11-slim，可在构建时覆盖为可访问的镜像域
ARG PY_IMAGE=python:3.11-slim
FROM ${PY_IMAGE}

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn python-multipart && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu  # 20250825_update: 安装CPU版Torch

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p video_data website temp checkpoint

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"] 