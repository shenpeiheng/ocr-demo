# OCR工业图片识别系统 - 部署指南

## 项目概述

OCR工业图片识别系统是一个基于Flask和PaddleOCR的Web应用，用于识别工业图纸中的文字和标注。系统包含前后端，支持图片上传、OCR识别、结果可视化和数据导出。

## 系统架构

- **前端**: HTML/CSS/JavaScript静态页面
- **后端**: Python Flask API服务
- **OCR引擎**: PaddleOCR PP-OCRv5（支持模拟模式）
- **数据库**: 无（文件系统存储）

## 部署方式

### 1. 使用Docker部署（推荐）

#### 构建Docker镜像

```bash
# 构建镜像
docker build -t ocr-industrial-system .

# 运行容器
docker run -d \
  -p 5000:5000 \
  -v ./frontend/uploads:/app/frontend/uploads \
  --name ocr-system \
  ocr-industrial-system
```

#### 使用docker-compose部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 2. 直接运行（开发环境）

#### 环境要求

- Python 3.7+
- pip包管理器
- 系统依赖：gcc, g++, libgl1等

#### 安装步骤

```bash
# 1. 安装系统依赖（Ubuntu/Debian）
sudo apt-get update
sudo apt-get install -y gcc g++ libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1

# 2. 安装Python依赖
cd backend
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑.env文件配置参数

# 4. 启动服务
python run.py
```

## 配置说明

### 环境变量配置

主要环境变量（在`.env`文件中配置）：

```bash
# Flask配置
SECRET_KEY=your-secret-key
DEBUG=false
PORT=5000

# OCR配置
OCR_USE_MOCK=true  # true=使用模拟数据，false=使用真实PaddleOCR
OCR_CONFIDENCE_THRESHOLD=0.5

# 文件上传配置
MAX_CONTENT_LENGTH=16777216  # 16MB
ALLOWED_EXTENSIONS=PNG,JPG,JPEG,BMP,TIFF,GIF

# 百度OCR API配置（如果需要真实OCR）
BAIDU_APP_ID=your_app_id
BAIDU_API_KEY=your_api_key
BAIDU_SECRET_KEY=your_secret_key
```

### Docker配置

#### 端口映射

- `5000`: Flask后端API端口
- `80`: Nginx前端端口（如果使用docker-compose）

#### 数据卷

- `./frontend/uploads`: 上传文件存储目录
- `./backend/.env`: 配置文件（可选）

## 访问应用

### 1. 基础部署

```
前端界面: http://localhost:5000/../frontend/index.html
API文档: http://localhost:5000/
```

### 2. 使用Nginx部署（docker-compose）

```
前端界面: http://localhost
API端点: http://localhost/api/
```

## API接口

### 主要端点

- `GET /` - API信息
- `POST /api/upload` - 上传图片文件
- `POST /api/process` - 处理图片进行OCR识别
- `GET /api/results/<filename>` - 获取识别结果
- `GET /api/download/excel/<filename>` - 下载Excel格式结果
- `GET /api/download/json/<filename>` - 下载JSON格式结果
- `GET /uploads/<filename>` - 访问上传的文件

## 故障排除

### 常见问题

1. **Docker构建失败**
   - 检查网络连接
   - 确保Docker服务正在运行
   - 尝试使用`--no-cache`选项重新构建

2. **OCR识别失败**
   - 检查PaddleOCR依赖是否安装正确
   - 确保系统有足够的内存（PaddleOCR需要较多内存）
   - 尝试使用模拟模式（设置`OCR_USE_MOCK=true`）

3. **文件上传失败**
   - 检查上传目录权限
   - 确认文件大小未超过限制
   - 验证文件格式是否支持

4. **前端无法访问**
   - 检查端口是否正确映射
   - 确认Flask服务正在运行
   - 查看浏览器控制台错误信息

### 日志查看

```bash
# Docker容器日志
docker logs ocr-system

# docker-compose日志
docker-compose logs

# Flask应用日志
查看backend/app.py中的日志输出
```

## 性能优化

### 1. 使用GPU加速（如果可用）

```dockerfile
# 在Dockerfile中启用GPU支持
ENV USE_GPU=true
```

### 2. 调整内存限制

```bash
# 运行容器时增加内存限制
docker run -d \
  --memory=4g \
  --memory-swap=4g \
  -p 5000:5000 \
  ocr-industrial-system
```

### 3. 使用生产级Web服务器

```bash
# 使用gunicorn替代Flask开发服务器
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

## 安全建议

1. **生产环境配置**
   - 设置`DEBUG=false`
   - 使用强随机`SECRET_KEY`
   - 启用HTTPS
   - 配置防火墙规则

2. **文件上传安全**
   - 限制文件类型和大小
   - 对上传文件进行病毒扫描
   - 使用随机文件名避免路径遍历

3. **API安全**
   - 实施API速率限制
   - 添加身份验证（如果需要）
   - 记录所有API请求

## 扩展开发

### 添加新功能

1. **自定义OCR模型**
   - 在`backend/paddle_ocr_processor.py`中修改模型配置
   - 添加新的预处理方法
   - 扩展文本类型识别逻辑

2. **前端功能扩展**
   - 在`frontend/static/js/main.js`中添加JavaScript功能
   - 修改`frontend/static/css/style.css`调整样式
   - 扩展结果可视化功能

3. **API扩展**
   - 在`backend/app.py`中添加新的路由
   - 创建新的数据处理模块
   - 添加数据库支持（如果需要）

## 技术支持

- 查看项目README.md获取基本信息
- 参考代码注释了解具体实现
- 如有问题，检查日志文件获取详细错误信息