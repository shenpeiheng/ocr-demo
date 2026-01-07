/**
 * OCR工业图片识别系统 - 主JavaScript文件
 */

// 全局变量
const API_BASE_URL = 'http://localhost:5000';
let currentFile = null;
let currentResults = null;
let processingStartTime = null;

// DOM元素
const fileInput = document.getElementById('fileInput');
const selectFileBtn = document.getElementById('selectFileBtn');
const uploadBtn = document.getElementById('uploadBtn');
const processBtn = document.getElementById('processBtn');
const uploadArea = document.getElementById('uploadArea');
const imagePreview = document.getElementById('imagePreview');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const imageDimensions = document.getElementById('imageDimensions');
const uploadStatus = document.getElementById('uploadStatus');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const statusUpload = document.getElementById('statusUpload');
const statusProcess = document.getElementById('statusProcess');
const statusResults = document.getElementById('statusResults');
const totalItems = document.getElementById('totalItems');
const avgConfidence = document.getElementById('avgConfidence');
const dimensionCount = document.getElementById('dimensionCount');
const processingTime = document.getElementById('processingTime');
const textResultsBody = document.getElementById('textResultsBody');
const coordinateResultsBody = document.getElementById('coordinateResultsBody');
const visualizationPlaceholder = document.getElementById('visualizationPlaceholder');
const visualizationCanvas = document.getElementById('visualizationCanvas');
const exportExcelBtn = document.getElementById('exportExcelBtn');
const exportJsonBtn = document.getElementById('exportJsonBtn');
const exportImageBtn = document.getElementById('exportImageBtn');
const apiUrl = document.getElementById('apiUrl');

// 初始化函数
function init() {
    console.log('OCR工业图片识别系统初始化...');
    
    // 绑定事件监听器
    bindEvents();
    
    // 初始化标签页
    initTabs();
    
    // 更新API URL显示
    apiUrl.textContent = `${API_BASE_URL}/api/results/`;
    
    console.log('系统初始化完成');
}

// 绑定事件
function bindEvents() {
    // 选择文件按钮 - 阻止事件冒泡
    selectFileBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // 阻止事件冒泡到uploadArea
        fileInput.click();
    });
    
    // 文件输入变化
    fileInput.addEventListener('change', handleFileSelect);
    
    // 上传按钮
    uploadBtn.addEventListener('click', handleUpload);
    
    // 处理按钮
    processBtn.addEventListener('click', handleProcess);
    
    // 导出按钮
    exportExcelBtn.addEventListener('click', () => exportResults('excel'));
    exportJsonBtn.addEventListener('click', () => exportResults('json'));
    exportImageBtn.addEventListener('click', exportAnnotatedImage);
    
    // 拖放功能
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    
    // 点击上传区域选择文件 - 排除按钮区域
    uploadArea.addEventListener('click', (e) => {
        // 如果点击的是选择文件按钮，不触发上传区域点击事件
        if (e.target === selectFileBtn || selectFileBtn.contains(e.target)) {
            return;
        }
        fileInput.click();
    });
}

// 初始化标签页
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // 更新按钮状态
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // 显示对应的标签页内容
            document.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.remove('active');
            });
            
            document.getElementById(tabId).classList.add('active');
            
            // 如果是可视化标签页且已有结果，更新可视化
            if (tabId === 'visualization' && currentResults) {
                updateVisualization();
            }
        });
    });
}

// 处理文件选择
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    previewFile(file);
}

// 处理拖放
function handleDragOver(event) {
    event.preventDefault();
    uploadArea.classList.add('drag-over');
}

function handleDragLeave(event) {
    event.preventDefault();
    uploadArea.classList.remove('drag-over');
}

function handleDrop(event) {
    event.preventDefault();
    uploadArea.classList.remove('drag-over');
    
    const file = event.dataTransfer.files[0];
    if (!file) return;
    
    // 更新文件输入
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;
    
    previewFile(file);
}

// 预览文件
function previewFile(file) {
    // 检查文件类型
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp', 'image/tiff', 'image/gif'];
    if (!validTypes.includes(file.type)) {
        showError('不支持的文件类型。请选择图片文件（PNG, JPG, BMP, TIFF, GIF）。');
        return;
    }
    
    // 检查文件大小（最大16MB）
    const maxSize = 16 * 1024 * 1024; // 16MB
    if (file.size > maxSize) {
        showError('文件太大。最大支持16MB。');
        return;
    }
    
    currentFile = file;
    
    // 显示文件信息
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    uploadStatus.textContent = '等待上传';
    uploadStatus.className = 'status-waiting';
    
    // 预览图片
    const reader = new FileReader();
    reader.onload = function(e) {
        imagePreview.src = e.target.result;
        
        // 获取图片尺寸
        const img = new Image();
        img.onload = function() {
            imageDimensions.textContent = `${this.width} × ${this.height} 像素`;
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
    
    // 显示文件信息区域
    fileInfo.style.display = 'grid';
    
    // 启用上传按钮
    uploadBtn.disabled = false;
    processBtn.disabled = true;
    
    // 更新进度状态
    updateProgress(0, '选择文件完成，准备上传');
    updateStatus('upload', 'active');
    updateStatus('process', 'inactive');
    updateStatus('results', 'inactive');
    
    // 重置结果区域
    resetResults();
}

// 处理上传
async function handleUpload() {
    if (!currentFile) {
        showError('请先选择文件');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', currentFile);
    
    try {
        // 更新UI状态
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 上传中...';
        updateProgress(30, '正在上传文件到服务器');
        
        // 发送上传请求
        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`上传失败: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || '上传失败');
        }
        
        // 更新文件信息
        currentFile.serverFilename = data.filename;
        uploadStatus.textContent = '上传成功';
        uploadStatus.className = 'status-success';
        
        // 更新进度
        updateProgress(50, '文件上传成功，准备识别处理');
        updateStatus('upload', 'completed');
        updateStatus('process', 'active');
        
        // 启用处理按钮
        processBtn.disabled = false;
        
        showSuccess('文件上传成功！');
        
    } catch (error) {
        console.error('上传错误:', error);
        showError(`上传失败: ${error.message}`);
        uploadStatus.textContent = '上传失败';
        uploadStatus.className = 'status-error';
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 重新上传';
        updateProgress(0, '上传失败');
    } finally {
        uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 上传图片';
    }
}

// 处理OCR识别
async function handleProcess() {
    if (!currentFile || !currentFile.serverFilename) {
        showError('请先上传文件');
        return;
    }
    
    processingStartTime = Date.now();
    
    try {
        // 更新UI状态
        processBtn.disabled = true;
        processBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 识别中...';
        updateProgress(70, '正在进行OCR识别处理');
        
        // 发送处理请求
        const response = await fetch(`${API_BASE_URL}/api/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filename: currentFile.serverFilename
            })
        });
        
        if (!response.ok) {
            throw new Error(`处理失败: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || '处理失败');
        }
        
        // 保存结果
        currentResults = data.results;
        
        // 更新进度
        updateProgress(90, '识别完成，正在生成结果');
        updateStatus('process', 'completed');
        updateStatus('results', 'active');
        
        // 显示结果
        displayResults(data);
        
        // 更新进度完成
        updateProgress(100, '处理完成！');
        updateStatus('results', 'completed');
        
        // 启用导出按钮
        exportExcelBtn.disabled = false;
        exportJsonBtn.disabled = false;
        exportImageBtn.disabled = false;
        
        showSuccess('图片识别完成！');
        
    } catch (error) {
        console.error('处理错误:', error);
        showError(`识别失败: ${error.message}`);
        updateProgress(0, '识别失败');
        updateStatus('process', 'error');
    } finally {
        processBtn.innerHTML = '<i class="fas fa-cogs"></i> 开始识别';
    }
}

// 显示结果
function displayResults(data) {
    if (!currentResults || !currentResults.text_items) {
        showError('没有识别结果');
        return;
    }
    
    const textItems = currentResults.text_items;
    const processingTimeMs = Date.now() - processingStartTime;
    
    // 更新摘要信息
    totalItems.textContent = textItems.length;
    
    // 计算平均置信度
    const avgConf = textItems.reduce((sum, item) => sum + (item.confidence || 0), 0) / textItems.length;
    avgConfidence.textContent = `${(avgConf * 100).toFixed(1)}%`;
    
    // 计算尺寸标注数量
    const dimensionItems = textItems.filter(item => item.type === 'dimension');
    dimensionCount.textContent = dimensionItems.length;
    
    // 更新处理时间
    processingTime.textContent = `${(processingTimeMs / 1000).toFixed(2)}s`;
    
    // 更新文本内容表格
    updateTextResultsTable(textItems);
    
    // 更新坐标表格
    updateCoordinateTable(textItems);
    
    // 更新可视化
    updateVisualization();
    
    // 更新API URL
    apiUrl.textContent = `${API_BASE_URL}/api/results/${currentFile.serverFilename}`;
}

// 更新文本结果表格
function updateTextResultsTable(textItems) {
    textResultsBody.innerHTML = '';
    
    if (textItems.length === 0) {
        textResultsBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-message">没有识别到文本内容</td>
            </tr>
        `;
        return;
    }
    
    textItems.forEach((item, index) => {
        const confidenceClass = getConfidenceClass(item.confidence);
        const confidencePercent = (item.confidence * 100).toFixed(1);
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${escapeHtml(item.text)}</td>
            <td class="${confidenceClass}">${confidencePercent}%</td>
            <td><span class="badge badge-${item.type}">${item.type}</span></td>
            <td>
                <button class="btn-small btn-view" data-index="${index}" title="查看详情">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="btn-small btn-copy" data-text="${escapeHtml(item.text)}" title="复制文本">
                    <i class="fas fa-copy"></i>
                </button>
            </td>
        `;
        
        textResultsBody.appendChild(row);
    });
    
    // 绑定按钮事件
    document.querySelectorAll('.btn-view').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const index = parseInt(e.target.closest('button').getAttribute('data-index'));
            viewItemDetails(textItems[index]);
        });
    });
    
    document.querySelectorAll('.btn-copy').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const text = e.target.closest('button').getAttribute('data-text');
            copyToClipboard(text);
            showSuccess('文本已复制到剪贴板');
        });
    });
}

// 更新坐标表格
function updateCoordinateTable(textItems) {
    coordinateResultsBody.innerHTML = '';
    
    if (textItems.length === 0) {
        coordinateResultsBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-message">没有坐标信息</td>
            </tr>
        `;
        return;
    }
    
    textItems.forEach((item, index) => {
        const location = item.location || {};
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${location.left || 0}</td>
            <td>${location.top || 0}</td>
            <td>${location.width || 0}</td>
            <td>${location.height || 0}</td>
            <td>${escapeHtml(item.text)}</td>
        `;
        
        coordinateResultsBody.appendChild(row);
    });
}

// 更新可视化
function updateVisualization() {
    if (!currentResults || !currentResults.text_items || !imagePreview.src) {
        return;
    }
    
    // 隐藏占位符，显示画布
    visualizationPlaceholder.style.display = 'none';
    visualizationCanvas.style.display = 'block';
    
    const ctx = visualizationCanvas.getContext('2d');
    const img = new Image();
    
    img.onload = function() {
        // 设置画布尺寸
        const maxWidth = 800;
        const maxHeight = 500;
        let width = img.width;
        let height = img.height;
        
        // 按比例缩放
        if (width > maxWidth) {
            height = (maxWidth / width) * height;
            width = maxWidth;
        }
        if (height > maxHeight) {
            width = (maxHeight / height) * width;
            height = maxHeight;
        }
        
        visualizationCanvas.width = width;
        visualizationCanvas.height = height;
        
        // 绘制图片
        ctx.drawImage(img, 0, 0, width, height);
        
        // 绘制识别区域
        const scaleX = width / img.width;
        const scaleY = height / img.height;
        
        currentResults.text_items.forEach(item => {
            const location = item.location || {};
            const x = (location.left || 0) * scaleX;
            const y = (location.top || 0) * scaleY;
            const w = (location.width || 0) * scaleX;
            const h = (location.height || 0) * scaleY;
            
            // 根据类型设置颜色
            let color;
            switch (item.type) {
                case 'dimension': color = '#e74c3c'; break; // 红色
                case 'tolerance': color = '#f39c12'; break; // 橙色
                default: color = '#3498db'; // 蓝色
            }
            
            // 绘制矩形框
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, w, h);
            
            // 绘制背景标签
            ctx.fillStyle = color;
            ctx.fillRect(x, y - 20, Math.min(w, 100), 20);
            
            // 绘制文本
            ctx.fillStyle = 'white';
            ctx.font = '12px Arial';
            ctx.fillText(`#${item.id}`, x + 5, y - 5);
        });
    };
    
    img.src = imagePreview.src;
}

// 导出结果
function exportResults(format) {
    if (!currentFile || !currentFile.serverFilename) {
        showError('没有可导出的结果');
        return;
    }
    
    const url = `${API_BASE_URL}/api/download/${format}/${currentFile.serverFilename}`;
    window.open(url, '_blank');
}

// 导出标注图片
function exportAnnotatedImage() {
    if (!visualizationCanvas || visualizationCanvas.style.display === 'none') {
        showError('没有可导出的标注图片');
        return;
    }
    
    const link = document.createElement('a');
    link.download = `ocr_annotated_${currentFile.name.replace(/\.[^/.]+$/, "")}.png`;
    link.href = visualizationCanvas.toDataURL('image/png');
    link.click();
}

// 查看项目详情
function viewItemDetails(item) {
    const location = item.location || {};
    const details = `
        <strong>文本内容:</strong> ${escapeHtml(item.text)}<br>
        <strong>置信度:</strong> ${(item.confidence * 100).toFixed(1)}%<br>
        <strong>类型:</strong> ${item.type}<br>
        <strong>位置:</strong> X=${location.left}, Y=${location.top}<br>
        <strong>尺寸:</strong> ${location.width}×${location.height} 像素<br>
        <strong>ID:</strong> ${item.id}
    `;
    
    showModal('识别项详情', details);
}

// 工具函数
function updateProgress(percent, text) {
    progressFill.style.width = `${percent}%`;
    progressText.textContent = text;
}

function updateStatus(stage, state) {
    const statusElement = {
        upload: statusUpload,
        process: statusProcess,
        results: statusResults
    }[stage];
    
    if (!statusElement) return;
    
    const icon = statusElement.querySelector('.status-icon');
    
    // 移除所有状态类
    statusElement.classList.remove('active', 'completed', 'error');
    icon.classList.remove('fa-check-circle', 'fa-times-circle', 'fa-circle', 'fa-spinner', 'fa-spin');
    
    switch (state) {
        case 'active':
            statusElement.classList.add('active');
            icon.classList.add('fa-spinner', 'fa-spin');
            break;
        case 'completed':
            statusElement.classList.add('completed');
            icon.classList.add('fa-check-circle');
            break;
        case 'error':
            statusElement.classList.add('error');
            icon.classList.add('fa-times-circle');
            break;
        default:
            icon.classList.add('fa-circle');
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.5) return 'confidence-medium';
    return 'confidence-low';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
}

function showError(message) {
    showNotification(message, 'error');
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showNotification(message, type) {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'error' ? 'exclamation-circle' : 'check-circle'}"></i>
        <span>${message}</span>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;
    
    // 添加到页面
    document.body.appendChild(notification);
    
    // 添加样式
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'error' ? '#e74c3c' : '#2ecc71'};
        color: white;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    // 添加动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
    
    // 关闭按钮事件
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    });
    
    // 自动消失
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }, 5000);
}

function showModal(title, content) {
    // 创建模态框
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>${title}</h3>
                <button class="modal-close"><i class="fas fa-times"></i></button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary modal-ok">确定</button>
            </div>
        </div>
    `;
    
    // 添加到页面
    document.body.appendChild(modal);
    
    // 添加样式
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 2000;
        animation: fadeIn 0.3s ease;
    `;
    
    const modalContent = modal.querySelector('.modal-content');
    modalContent.style.cssText = `
        background: white;
        border-radius: 10px;
        width: 90%;
        max-width: 500px;
        max-height: 80vh;
        overflow: auto;
        animation: scaleIn 0.3s ease;
    `;
    
    // 添加动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes scaleIn {
            from { transform: scale(0.9); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            border-bottom: 1px solid #eaeaea;
        }
        
        .modal-header h3 {
            margin: 0;
            color: #2c3e50;
        }
        
        .modal-close {
            background: none;
            border: none;
            font-size: 1.2rem;
            cursor: pointer;
            color: #7f8c8d;
        }
        
        .modal-body {
            padding: 20px;
            color: #34495e;
            line-height: 1.6;
        }
        
        .modal-footer {
            padding: 15px 20px;
            border-top: 1px solid #eaeaea;
            text-align: right;
        }
    `;
    document.head.appendChild(style);
    
    // 关闭事件
    const closeModal = () => {
        modal.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        }, 300);
    };
    
    modal.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.querySelector('.modal-ok').addEventListener('click', closeModal);
    
    // 点击背景关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
}

function resetResults() {
    // 重置摘要
    totalItems.textContent = '0';
    avgConfidence.textContent = '0%';
    dimensionCount.textContent = '0';
    processingTime.textContent = '0s';
    
    // 重置表格
    textResultsBody.innerHTML = `
        <tr>
            <td colspan="5" class="empty-message">暂无识别结果</td>
        </tr>
    `;
    
    coordinateResultsBody.innerHTML = `
        <tr>
            <td colspan="6" class="empty-message">暂无坐标信息</td>
        </tr>
    `;
    
    // 重置可视化
    visualizationPlaceholder.style.display = 'flex';
    visualizationCanvas.style.display = 'none';
    
    // 禁用导出按钮
    exportExcelBtn.disabled = true;
    exportJsonBtn.disabled = true;
    exportImageBtn.disabled = true;
    
    // 清除当前结果
    currentResults = null;
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);