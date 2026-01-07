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
├── backend/              # 后端API服务
│   ├── app.py           # Flask主应用
│   ├── ocr_processor.py # OCR处理器（百度OCR集成）
│   ├── config.py        # 配置文件
│   ├── run.py           # 启动脚本
│   ├── requirements.txt # Python依赖
│   └── .env.example     # 环境变量示例
├── frontend/            # 前端界面
│   ├── index.html       # 主页面
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css # 样式文件
│   │   └── js/
│   │       └── main.js   # JavaScript逻辑
│   └── uploads/         # 文件上传目录
└── README.md            # 项目文档
```

## 快速开始

### 1. 环境要求

- Python 3.7+
- Node.js（可选，仅用于前端开发）
- 百度OCR API密钥（可选，可使用模拟模式）

### 2. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量示例文件并配置：

```bash
cd backend
copy .env.example .env
```

编辑`.env`文件，配置百度OCR API密钥（如需使用真实OCR）：

```env
# 百度OCR API配置（从百度AI开放平台获取）
BAIDU_APP_ID=your_app_id_here
BAIDU_API_KEY=your_api_key_here
BAIDU_SECRET_KEY=your_secret_key_here
OCR_USE_MOCK=false  # 设置为false以使用真实百度OCR API
```

### 4. 启动后端服务器

```bash
cd backend
python run.py
```

或者直接运行：

```bash
cd backend
python app.py
```

服务器将在 http://localhost:5000 启动。

### 5. 访问前端界面

在浏览器中打开：
```
file:///path/to/ocr-demo/frontend/index.html
```

或者通过Python启动一个简单的HTTP服务器：

```bash
cd frontend
python -m http.server 8000
```

然后在浏览器中访问 http://localhost:8000

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
- `API_BASE_URL`: 后端API地址（默认http://localhost:5000）
- 最大文件大小限制：16MB
- 支持的图片格式：PNG, JPG, JPEG, BMP, TIFF, GIF

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