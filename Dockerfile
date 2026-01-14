# OCR工业图片识别系统 - Dockerfile
# 使用Python 3.9作为基础镜像
FROM python:3.9-slim
# 设置工作目录
WORKDIR /app
# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # 添加PaddlePaddle环境变量
    FLAGS_use_avx=0 \
    FLAGS_use_mkldnn=0 \
    FLAGS_use_cinn=0 \
    OMP_NUM_THREADS=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN /opt/venv/bin/pip install --upgrade pip
RUN /opt/venv/bin/pip install \
        Flask==2.3.3 \
        Flask-CORS==4.0.0 \
        Pillow==10.0.0 \
        openpyxl==3.1.2 \
        numpy==1.26.4 \
        opencv-python==4.6.0.66 \
        python-dotenv==1.0.0 \
        setuptools==70.0.0
RUN /opt/venv/bin/pip install paddlepaddle==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
RUN /opt/venv/bin/pip install paddleocr==3.3.2

# 复制项目文件（包括预下载脚本）
COPY . .

# 预下载PaddleOCR模型（避免首次运行时下载）
RUN echo "预下载PaddleOCR模型..." && \
    mkdir -p /app/.paddleocr && \
    /opt/venv/bin/python backend/preload_ocr_models.py

# 创建必要的目录
RUN mkdir -p frontend/uploads && \
    chmod 755 frontend/uploads && \
    chmod 755 /app/.paddleocr

# 设置环境变量（可以在运行时覆盖）
ENV FLASK_APP=backend/app.py \
    FLASK_ENV=production \
    PORT=5000 \
    DEBUG=false \
    OCR_USE_MOCK=false \
    ENABLE_CORS=true

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["/opt/venv/bin/python", "backend/run.py", "--host", "0.0.0.0", "--port", "5000"]

# 构建说明：
# 1. 构建镜像: docker build -t ocr-industrial-demo .
# 2. 运行容器: docker run -d -p 6102:5000 --name ocr-demo ocr-industrial-demo
# 3. 访问应用: http://localhost:5000