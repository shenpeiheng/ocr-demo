# OCR工业图片识别系统 - Dockerfile
# 使用Python 3.9作为基础镜像
FROM python:3.9-slim
# 设置工作目录
WORKDIR /app

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
RUN /opt/venv/bin/pip install \
        pdf2image==1.16.3 \
        PyMuPDF==1.23.8 \
        pdfplumber==0.10.3

# 复制项目文件（包括预下载脚本）
COPY . .

# 创建必要的目录
RUN mkdir -p frontend/uploads && \
    chmod 755 frontend/uploads

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["/opt/venv/bin/python", "backend/run.py", "--host", "0.0.0.0", "--port", "5000"]

# 构建说明：
# 1. 构建镜像: docker build -t ocr-industrial-demo .
# 2. 运行容器: docker run -d -p 6102:5000 --name ocr-demo ocr-industrial-demo
# 3. 访问应用: http://localhost:5000