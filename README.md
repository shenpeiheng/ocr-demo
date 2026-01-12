# OCR工业图片识别系统

一个完整的工业图纸OCR识别系统，支持上传工业图纸图片，识别图片上的内容并输出坐标和内容，提供Excel和JSON格式下载，同时提供可视化界面。

## 功能特性

- 🖼️ **图片上传**: 支持PNG、JPG、JPEG、BMP、TIFF、GIF格式
- 🔍 **OCR识别**: 集成百度OCR API，支持高精度工业图纸识别
- 📊 **坐标提取**: 自动提取文本位置坐标（X, Y, 宽度, 高度）
- 📁 **多格式导出**: 支持Excel（.xlsx）和JSON格式导出
- 🎨 **可视化展示**: 在图片上标注识别区域，直观显示识别结果
- 📈 **数据分析**: 提供识别统计信息（置信度、数量、处理时间等）
- 🖥️ **现代化界面**: 响应式设计，支持拖放上传

## 系统架构

```
ocr-demo/
├── backend/             # 后端API服务（包含前端静态文件服务）
│   ├── app.py           # Flask主应用（整合前端页面服务）
│   ├── ocr_processor.py # OCR处理器（百度OCR集成）
│   ├── config.py        # 配置文件
│   ├── run.py           # 启动脚本
│   └── requirements.txt # Python依赖
├── frontend/            # 前端静态文件
│   ├── index.html       # 主页面
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css # 样式文件
│   │   └── js/
│   │       └── main.js   # JavaScript逻辑
│   └── uploads/         # 文件上传目录
├── Dockerfile           # 容器化构建文件（整合前后端）
├── docker-compose.yml   # 容器编排配置
├── .dockerignore        # Docker忽略文件
└── README.md            # 项目文档
```

## Docker部署

### 1. 使用Docker Compose（推荐）

#### 1.1 启动服务
```bash
# 启动服务（后台运行）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 1.2 使用构建脚本
```bash
# Windows系统
build.bat

# Linux/macOS系统
chmod +x build.sh
./build.sh
```

### 2. 使用Docker直接运行

#### 2.1 构建镜像
```bash
docker build -t ocr-industrial-demo:latest .
```

#### 2.2 运行容器
```bash
# 基本运行
docker run -p 5000:5000 --name ocr-demo ocr-industrial-demo

# 带数据持久化
docker run -p 5000:5000 \
  -v ./frontend/uploads:/app/frontend/uploads \
  --name ocr-demo \
  ocr-industrial-demo

# 带环境变量配置
docker run -p 5000:5000 \
  -v ./frontend/uploads:/app/frontend/uploads \
  -v ./.env:/app/.env \
  --name ocr-demo \
  ocr-industrial-demo
```

#### 2.3 访问应用
容器启动后，在浏览器中访问：
```
http://localhost:5000
```

### 3. Dockerfile说明

#### 3.1 基础镜像
- 使用Python 3.9-slim作为基础镜像
- 包含必要的系统依赖（libgl1-mesa-glx等用于OpenCV）

#### 3.2 构建优化
- 多阶段构建减少镜像大小
- 使用Python虚拟环境
- 缓存依赖安装

#### 3.3 健康检查
- 自动健康检查确保服务可用性
- 30秒间隔，3秒超时

### 4. 环境配置

#### 4.1 环境变量
可以通过环境变量或.env文件配置：
```env
# Flask配置
DEBUG=false
PORT=5000
SECRET_KEY=ocr-industrial-production-key

# OCR配置
OCR_USE_MOCK=false
OCR_CONFIDENCE_THRESHOLD=0.5

# 性能优化
OMP_NUM_THREADS=4
NUMEXPR_NUM_THREADS=4
OPENBLAS_NUM_THREADS=4
MKL_NUM_THREADS=4
```

#### 4.2 数据持久化
- 上传目录：`./frontend/uploads` 挂载到容器内
- 配置文件：`.env` 文件挂载到容器内

### 5. 传统部署方式（开发环境）

#### 5.1 环境要求
- Python 3.7+
- Docker 和 Docker Compose（可选，用于容器化部署）
- 百度OCR API密钥（可选，可使用模拟模式）

#### 5.2 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

#### 5.3 配置环境变量
```bash
cd backend
copy .env.example .env
```

#### 5.4 启动服务
```bash
cd backend
python run.py
```

或者直接运行：
```bash
cd backend
python app.py
```

#### 5.5 访问应用
服务启动后，在浏览器中访问：
```
http://localhost:5000
```

**注意**：现在前端页面已整合到后端服务中，无需单独启动前端服务器。

## API接口

### 1. 上传图片
```
POST /api/upload
Content-Type: multipart/form-data
参数: file (图片文件)
```

### 2. 处理图片
```
POST /api/process
Content-Type: application/json
参数: { "filename": "上传的文件名" }
```

### 3. 获取结果
```
GET /api/results/<filename>
```

### 4. 下载Excel结果
```
GET /api/download/excel/<filename>
```

### 5. 下载JSON结果
```
GET /api/download/json/<filename>
```

## 使用说明

### 1. 上传图片
- 点击"选择文件"按钮或拖放图片到上传区域
- 支持最大16MB的图片文件
- 支持PNG、JPG、JPEG、BMP、TIFF、GIF格式

### 2. OCR识别处理
- 点击"上传图片"按钮上传到服务器
- 点击"开始识别"按钮进行OCR处理
- 处理过程包括：图片预处理、OCR识别、坐标提取

### 3. 查看结果
- **文本内容**: 显示识别到的所有文本及其置信度
- **坐标信息**: 显示每个文本的位置坐标（X, Y, 宽度, 高度）
- **可视化**: 在图片上标注识别区域，不同颜色表示不同类型

### 4. 导出结果
- **Excel文件**: 包含序号、坐标、内容、置信度、类型等列
- **JSON文件**: 完整的识别结果，包含所有元数据
- **标注图片**: 带有识别区域标注的图片

## OCR识别技术

### 1. 百度OCR API
- 使用百度AI开放平台的OCR服务
- 支持中英文混合识别
- 高精度文字定位
- 支持表格、表单等复杂格式

### 2. 图像预处理
- 灰度转换
- 自适应阈值二值化
- 降噪处理
- 图像增强

### 3. 工业图纸优化
- 针对工业图纸中的特殊符号进行识别优化
- 支持尺寸标注（Φ、±等符号）
- 支持公差标注识别
- 支持材料说明识别

## 配置选项

### 后端配置（backend/config.py）
- `OCR_USE_MOCK`: 是否使用模拟数据（默认true）
- `OCR_CONFIDENCE_THRESHOLD`: 置信度阈值（默认0.5）
- `PREPROCESS_ENABLED`: 是否启用图像预处理（默认true）
- `OUTPUT_EXCEL_ENABLED`: 是否生成Excel文件（默认true）
- `OUTPUT_JSON_ENABLED`: 是否生成JSON文件（默认true）

### 前端配置（frontend/static/js/main.js）
- `API_BASE_URL`: 后端API地址（整合后使用相对路径''）
- 最大文件大小限制：16MB
- 支持的图片格式：PNG, JPG, JPEG, BMP, TIFF, GIF

### 架构变更说明
- **前后端整合**: 前端静态文件现在由Flask后端直接提供，无需单独的前端服务器
- **简化部署**: 只需启动一个服务即可访问完整应用
- **Docker优化**: 移除了Nginx服务，使用单个容器包含前后端
- **路径调整**: 前端API调用使用相对路径，适应整合后的部署环境

## 开发指南

### 添加新的OCR引擎
1. 在`backend/ocr_processor.py`中创建新的OCR引擎类
2. 实现`process_image`方法
3. 在配置中设置使用的引擎

### 扩展导出格式
1. 在`backend/app.py`的`generate_excel`函数旁添加新的导出函数
2. 添加对应的API端点
3. 在前端添加导出按钮和逻辑

### 添加新的可视化功能
1. 在`frontend/static/js/main.js`的`updateVisualization`函数中扩展
2. 添加新的可视化选项到界面
3. 更新CSS样式

## 性能优化

### 识别准确率优化
1. **图片质量**: 确保上传的图片清晰、光线均匀
2. **预处理参数**: 根据图片类型调整预处理参数
3. **OCR配置**: 调整百度OCR的识别参数（语言类型、识别粒度等）

### 处理速度优化
1. **图片缩放**: 对大图片进行适当缩放
2. **并行处理**: 支持批量图片处理
3. **缓存机制**: 对相同图片的识别结果进行缓存

## 故障排除

### 常见问题

1. **上传失败**
   - 检查文件大小是否超过16MB
   - 检查文件格式是否支持
   - 检查后端服务器是否运行

2. **识别准确率低**
   - 尝试调整图片预处理参数
   - 检查图片质量，确保文字清晰
   - 考虑使用百度OCR的高精度接口

3. **坐标提取错误**
   - 检查OCR返回的位置信息格式
   - 验证图片尺寸是否正确
   - 检查坐标转换逻辑

### 日志查看
后端服务器运行时会在控制台输出详细日志，包括：
- 文件上传信息
- OCR处理进度
- 错误信息
- 性能统计

## 许可证

本项目采用MIT许可证。详见LICENSE文件。

## 贡献指南

1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至项目维护者

## 更新日志

### v1.0.0 (2023-10-15)
- 初始版本发布
- 实现基本OCR识别功能
- 提供Excel和JSON导出
- 实现可视化界面
- 集成百度OCR API

---

**注意**: 本项目为演示用途，实际生产环境需要根据具体需求进行调整和优化。