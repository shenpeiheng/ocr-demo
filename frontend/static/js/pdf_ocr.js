/**
 * PDF OCR识别系统 - 主JavaScript文件
 */

// 全局变量
const API_BASE_URL = ''; // 使用相对路径，因为前端和后端在同一个服务中
let currentFile = null;
let currentResults = null;
let processingStartTime = null;
let currentPage = 1;
let totalPages = 0;
let pdfImages = []; // 存储PDF转换后的图像URL
let scale = 1.0;

// DOM元素
const fileInput = document.getElementById('fileInput');
const selectFileBtn = document.getElementById('selectFileBtn');
const uploadBtn = document.getElementById('uploadBtn');
const processBtn = document.getElementById('processBtn');
const uploadArea = document.getElementById('uploadArea');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const pdfPages = document.getElementById('pdfPages');
const pdfSettings = document.getElementById('pdfSettings');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const statusUpload = document.getElementById('statusUpload');
const statusConvert = document.getElementById('statusConvert');
const statusProcess = document.getElementById('statusProcess');
const statusResults = document.getElementById('statusResults');
const pagesProgress = document.getElementById('pagesProgress');
const pagesProgressFill = document.getElementById('pagesProgressFill');
const pagesProgressText = document.getElementById('pagesProgressText');
const pdfSummary = document.getElementById('pdfSummary');
const pdfTotalPages = document.getElementById('pdfTotalPages');
const totalItems = document.getElementById('totalItems');
const avgConfidence = document.getElementById('avgConfidence');
const processingTime = document.getElementById('processingTime');
const pagesSummary = document.getElementById('pagesSummary');
const pagesSummaryBody = document.getElementById('pagesSummaryBody');
const textResultsBody = document.getElementById('textResultsBody');
const coordinateResultsBody = document.getElementById('coordinateResultsBody');
const visualizationPlaceholder = document.getElementById('visualizationPlaceholder');
const visualizationCanvas = document.getElementById('visualizationCanvas');
const exportExcelBtn = document.getElementById('exportExcelBtn');
const exportJsonBtn = document.getElementById('exportJsonBtn');
const exportImagesBtn = document.getElementById('exportImagesBtn');
const pageSelect = document.getElementById('pageSelect');
const prevPageBtn = document.getElementById('prevPageBtn');
const nextPageBtn = document.getElementById('nextPageBtn');
const prevImageBtn = document.getElementById('prevImageBtn');
const nextImageBtn = document.getElementById('nextImageBtn');
const currentPageDisplay = document.getElementById('currentPageDisplay');
const zoomInBtn = document.getElementById('zoomInBtn');
const zoomOutBtn = document.getElementById('zoomOutBtn');
const zoomResetBtn = document.getElementById('zoomResetBtn');
const downloadImageBtn = document.getElementById('downloadImageBtn');

// 处理设置元素
const dpiSetting = document.getElementById('dpiSetting');
const pagesSetting = document.getElementById('pagesSetting');
const languageSetting = document.getElementById('languageSetting');
const extractDirectText = document.getElementById('extractDirectText');

// 初始化函数
function init() {
    console.log('PDF OCR识别系统初始化...');
    
    // 绑定事件监听器
    bindEvents();
    
    // 初始化标签页
    initTabs();
    
    console.log('PDF OCR系统初始化完成');
}

// 绑定事件
function bindEvents() {
    // 选择文件按钮
    selectFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
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
    exportImagesBtn.addEventListener('click', exportImages);
    
    // 拖放功能
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    
    // 点击上传区域选择文件
    uploadArea.addEventListener('click', (e) => {
        if (e.target === selectFileBtn || selectFileBtn.contains(e.target)) {
            return;
        }
        fileInput.click();
    });
    
    // 页面导航按钮
    prevPageBtn.addEventListener('click', () => navigatePage(-1));
    nextPageBtn.addEventListener('click', () => navigatePage(1));
    prevImageBtn.addEventListener('click', () => navigateImage(-1));
    nextImageBtn.addEventListener('click', () => navigateImage(1));
    
    // 页面选择变化
    pageSelect.addEventListener('change', handlePageSelectChange);
    
    // 缩放控制
    zoomInBtn.addEventListener('click', () => zoomImage(1.2));
    zoomOutBtn.addEventListener('click', () => zoomImage(0.8));
    zoomResetBtn.addEventListener('click', () => resetZoom());
    downloadImageBtn.addEventListener('click', downloadCurrentImage);
    
    // 侧边栏按钮
    document.getElementById('pdfInfoBtn')?.addEventListener('click', showPdfInfo);
    document.getElementById('extractTextBtn')?.addEventListener('click', extractPdfText);
    document.getElementById('convertImagesBtn')?.addEventListener('click', convertToImages);
    document.getElementById('batchProcessBtn')?.addEventListener('click', showBatchProcess);
    document.getElementById('exportExcelBtnSide')?.addEventListener('click', () => exportResults('excel'));
    document.getElementById('exportJsonBtnSide')?.addEventListener('click', () => exportResults('json'));
    document.getElementById('exportImagesBtnSide')?.addEventListener('click', exportImages);
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
            
            // 根据标签页类型更新内容
            if (currentResults) {
                if (tabId === 'visualization') {
                    updateVisualization();
                } else if (tabId === 'pageResults') {
                    updatePageResultsTable();
                }
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
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showError('不支持的文件类型。请选择PDF文件。');
        return;
    }
    
    // 检查文件大小（最大50MB）
    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
        showError('文件太大。最大支持50MB。');
        return;
    }
    
    currentFile = file;
    
    // 显示文件信息
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    pdfPages.textContent = '正在获取...';
    
    // 显示文件信息区域
    fileInfo.style.display = 'grid';
    pdfSettings.style.display = 'block';
    
    // 启用上传按钮
    uploadBtn.disabled = false;
    processBtn.disabled = true;
    
    // 更新进度状态
    updateProgress(0, '选择PDF文件完成，准备上传');
    updateStatus('upload', 'active');
    updateStatus('convert', 'inactive');
    updateStatus('process', 'inactive');
    updateStatus('results', 'inactive');
    
    // 重置结果区域
    resetResults();
    
    // 尝试获取PDF页数信息
    getPdfPageCount(file);
}

// 获取PDF页数
function getPdfPageCount(file) {
    // 这里可以添加客户端PDF页数检测
    // 目前我们只是显示一个占位符，实际页数将在上传后从服务器获取
    pdfPages.textContent = '上传后获取';
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
        updateProgress(30, '正在上传PDF文件到服务器');
        
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
        
        // 获取PDF信息
        const pdfInfoResponse = await fetch(`${API_BASE_URL}/api/pdf/info/${data.filename}`);
        if (pdfInfoResponse.ok) {
            const pdfInfoData = await pdfInfoResponse.json();
            if (pdfInfoData.success) {
                const pageCount = pdfInfoData.pdf_info.total_pages || 0;
                pdfPages.textContent = pageCount > 0 ? pageCount : '未知';
                totalPages = pageCount;
                
                // 更新页面设置的最大值
                if (pageCount > 0) {
                    pagesSetting.max = Math.min(pageCount, 50);
                    pagesSetting.value = Math.min(10, pageCount);
                }
            }
        }
        
        // 更新进度
        updateProgress(50, 'PDF文件上传成功，准备转换处理');
        updateStatus('upload', 'completed');
        updateStatus('convert', 'active');
        
        // 启用处理按钮
        processBtn.disabled = false;
        
        showSuccess('PDF文件上传成功！');
        
    } catch (error) {
        console.error('上传错误:', error);
        showError(`上传失败: ${error.message}`);
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 重新上传';
        updateProgress(0, '上传失败');
    } finally {
        uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 上传PDF';
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
        processBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 处理中...';
        updateProgress(60, '正在转换PDF为图像');
        updateStatus('convert', 'active');
        
        // 显示页面处理进度
        pagesProgress.style.display = 'block';
        updatePagesProgress(0, 0);
        
        // 获取处理参数
        const maxPages = parseInt(pagesSetting.value) || 10;
        const dpi = parseInt(dpiSetting.value) || 200;
        const lang = languageSetting.value || 'ch';
        
        // 发送处理请求
        const response = await fetch(`${API_BASE_URL}/api/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filename: currentFile.serverFilename,
                max_pages: maxPages,
                dpi: dpi,
                lang: lang
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
        updateStatus('convert', 'completed');
        updateStatus('process', 'completed');
        updateStatus('results', 'active');
        
        // 显示结果
        displayResults(data);
        
        // 更新进度完成
        updateProgress(100, '处理完成！');
        updateStatus('results', 'completed');
        updatePagesProgress(maxPages, maxPages);
        
        // 启用导出按钮
        exportExcelBtn.disabled = false;
        exportJsonBtn.disabled = false;
        exportImagesBtn.disabled = false;
        
        showSuccess('PDF识别完成！');
        
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
    if (!currentResults || !currentResults.combined_results) {
        showError('没有识别结果');
        return;
    }
    
    const combinedResults = currentResults.combined_results;
    const processingTimeMs = Date.now() - processingStartTime;
    
    // 显示PDF摘要
    pdfSummary.style.display = 'grid';
    pagesSummary.style.display = 'block';
    
    // 更新PDF信息
    const pdfInfo = currentResults.pdf_info || {};
    pdfTotalPages.textContent = pdfInfo.total_pages || 0;
    
    // 更新摘要信息
    totalItems.textContent = combinedResults.total_items || 0;
    
    // 计算平均置信度
    const textItems = combinedResults.text_items || [];
    const avgConf = textItems.length > 0
        ? textItems.reduce((sum, item) => sum + (item.confidence || 0), 0) / textItems.length
        : 0;
    avgConfidence.textContent = textItems.length > 0 ? `${(avgConf * 100).toFixed(1)}%` : '0%';
    
    // 更新处理时间
    processingTime.textContent = `${(processingTimeMs / 1000).toFixed(2)}s`;
    
    // 更新页面摘要
    updatePagesSummary();
    
    // 更新文本内容表格
    updateTextResultsTable(textItems);
    
    // 更新坐标表格
    updateCoordinateTable(textItems);
    
    // 更新页面选择器
    updatePageSelector();
    
    // 更新可视化
    updateVisualization();
    
    // 加载PDF页面图像
    loadPdfImages();
}

// 更新页面摘要
function updatePagesSummary() {
    if (!currentResults || !currentResults.pages_summary) {
        return;
    }
    
    const pagesSummaryData = currentResults.pages_summary;
    pagesSummaryBody.innerHTML = '';
    
    pagesSummaryData.forEach(page => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${page.page_number}</td>
            <td>${page.total_items || 0}</td>
            <td>${page.processing_time || 0}</td>
            <td><span class="status-badge ${page.success ? 'success' : 'error'}">${page.success ? '成功' : '失败'}</span></td>
            <td>
                <button class="btn-small btn-view-page" data-page="${page.page_number}">
                    <i class="fas fa-eye"></i> 查看
                </button>
                <button class="btn-small btn-jump-to-page" data-page="${page.page_number}" title="跳转到该页面">
                    <i class="fas fa-external-link-alt"></i>
                </button>
            </td>
        `;
        pagesSummaryBody.appendChild(row);
    });
    
    // 绑定查看页面按钮事件
    document.querySelectorAll('.btn-view-page').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const pageNum = parseInt(e.target.closest('button').getAttribute('data-page'));
            viewPageDetails(pageNum);
        });
    });
    
    // 绑定跳转到页面按钮事件
    document.querySelectorAll('.btn-jump-to-page').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const pageNum = parseInt(e.target.closest('button').getAttribute('data-page'));
            jumpToPage(pageNum);
        });
    });
}

// 跳转到指定页面
function jumpToPage(pageNum) {
    if (pageNum < 1 || pageNum > totalPages) {
        showError('无效的页码');
        return;
    }
    
    // 切换到按页面查看标签页
    const pageResultsTab = document.querySelector('.tab-btn[data-tab="pageResults"]');
    if (pageResultsTab) {
        pageResultsTab.click();
    }
    
    // 设置页面选择器
    currentPage = pageNum;
    pageSelect.value = pageNum;
    
    // 更新表格
    updatePageResultsTable();
    updateCurrentPageDisplay();
    
    showSuccess(`已跳转到第 ${pageNum} 页`);
}

// 更新文本结果表格
function updateTextResultsTable(textItems) {
    textResultsBody.innerHTML = '';
    
    if (textItems.length === 0) {
        textResultsBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-message">没有识别到文本内容</td>
            </tr>
        `;
        return;
    }
    
    textItems.forEach((item, index) => {
        const confidenceClass = getConfidenceClass(item.confidence);
        const confidencePercent = (item.confidence * 100).toFixed(1);
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.page || 1}</td>
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
                <td colspan="7" class="empty-message">暂无坐标信息</td>
            </tr>
        `;
        return;
    }
    
    textItems.forEach((item, index) => {
        const location = item.location || {};
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.page || 1}</td>
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

// 更新页面选择器
function updatePageSelector() {
    if (!currentResults || !currentResults.pdf_info) {
        return;
    }
    
    const totalPages = currentResults.pdf_info.total_pages || 0;
    pageSelect.innerHTML = '<option value="all">所有页面</option>';
    
    for (let i = 1; i <= totalPages; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = `第 ${i} 页`;
        pageSelect.appendChild(option);
    }
}

// 加载PDF页面图像
async function loadPdfImages() {
    if (!currentFile || !currentFile.serverFilename) {
        return;
    }
    
    try {
        // 获取PDF图像列表
        const response = await fetch(`${API_BASE_URL}/api/pdf/images/list/${currentFile.serverFilename}`);
        if (!response.ok) {
            console.warn('无法获取PDF图像列表');
            return;
        }
        
        const data = await response.json();
        if (data.success && data.images && data.images.length > 0) {
            // 保存图像URL到全局变量
            pdfImages = data.images.map(img => img.url);
            totalPages = data.images.length;
            
            // 更新页面显示
            updateCurrentPageDisplay();
            
            // 如果当前在可视化标签页，显示第一页
            const activeTab = document.querySelector('.tab-btn.active');
            if (activeTab && activeTab.getAttribute('data-tab') === 'visualization') {
                showCurrentPageImage();
            }
        }
    } catch (error) {
        console.error('加载PDF图像失败:', error);
    }
}

// 显示当前页面图像
function showCurrentPageImage() {
    if (pdfImages.length === 0 || currentPage < 1 || currentPage > pdfImages.length) {
        visualizationPlaceholder.style.display = 'flex';
        visualizationCanvas.style.display = 'none';
        return;
    }
    
    const imageUrl = pdfImages[currentPage - 1];
    const canvas = visualizationCanvas;
    const ctx = canvas.getContext('2d');
    
    // 创建图像对象
    const img = new Image();
    img.onload = function() {
        // 设置画布尺寸
        canvas.width = img.width * scale;
        canvas.height = img.height * scale;
        
        // 清除画布
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 绘制图像
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        
        // 显示画布，隐藏占位符
        visualizationPlaceholder.style.display = 'none';
        canvas.style.display = 'block';
        
        // 如果有OCR结果，可以在图像上绘制边界框
        if (currentResults && currentResults.combined_results && currentResults.combined_results.text_items) {
            drawBoundingBoxes(ctx, img, currentPage);
        }
    };
    
    img.onerror = function() {
        console.error('加载图像失败:', imageUrl);
        visualizationPlaceholder.style.display = 'flex';
        canvas.style.display = 'none';
    };
    
    img.src = imageUrl;
}

// 在图像上绘制OCR边界框
function drawBoundingBoxes(ctx, originalImg, pageNum) {
    if (!currentResults || !currentResults.combined_results || !currentResults.combined_results.text_items) {
        return;
    }
    
    const textItems = currentResults.combined_results.text_items;
    const pageItems = textItems.filter(item => item.page === pageNum);
    
    // 计算缩放比例
    const scaleX = canvas.width / originalImg.width;
    const scaleY = canvas.height / originalImg.height;
    
    // 绘制每个文本项的边界框
    pageItems.forEach(item => {
        const location = item.location || {};
        const left = (location.left || 0) * scaleX;
        const top = (location.top || 0) * scaleY;
        const width = (location.width || 0) * scaleX;
        const height = (location.height || 0) * scaleY;
        
        // 根据置信度设置颜色
        let color = '#ff0000'; // 低置信度
        if (item.confidence >= 0.8) {
            color = '#00ff00'; // 高置信度
        } else if (item.confidence >= 0.5) {
            color = '#ffff00'; // 中等置信度
        }
        
        // 绘制边界框
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(left, top, width, height);
        
        // 绘制置信度标签
        ctx.fillStyle = color;
        ctx.font = '12px Arial';
        ctx.fillText(`${(item.confidence * 100).toFixed(1)}%`, left, Math.max(top - 5, 10));
    });
}

// 更新当前页面显示
function updateCurrentPageDisplay() {
    currentPageDisplay.textContent = `页面: ${currentPage}/${pdfImages.length}`;
    
    // 更新页面选择器选项
    pageSelect.innerHTML = '<option value="all">所有页面</option>';
    for (let i = 1; i <= pdfImages.length; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = `第 ${i} 页`;
        if (i === currentPage) {
            option.selected = true;
        }
        pageSelect.appendChild(option);
    }
}

// 更新可视化
function updateVisualization() {
    // 如果当前在可视化标签页，显示图像
    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab && activeTab.getAttribute('data-tab') === 'visualization') {
        showCurrentPageImage();
    } else {
        visualizationPlaceholder.style.display = 'flex';
        visualizationCanvas.style.display = 'none';
    }
}

// 页面导航
function navigatePage(delta) {
    if (!currentResults || pdfImages.length === 0) {
        return;
    }
    
    const newPage = currentPage + delta;
    if (newPage < 1 || newPage > pdfImages.length) {
        return;
    }
    
    currentPage = newPage;
    updateCurrentPageDisplay();
    
    // 更新按页面查看的表格
    updatePageResultsTable();
}

function navigateImage(delta) {
    if (pdfImages.length === 0) {
        return;
    }
    
    const newPage = currentPage + delta;
    if (newPage < 1 || newPage > pdfImages.length) {
        return;
    }
    
    currentPage = newPage;
    updateCurrentPageDisplay();
    showCurrentPageImage();
}

function handlePageSelectChange() {
    const selectedPage = parseInt(pageSelect.value);
    if (selectedPage === currentPage || isNaN(selectedPage)) {
        return;
    }
    
    if (selectedPage === 0) { // "all" 选项
        // 显示所有页面（在按页面查看标签页中）
        currentPage = 1;
        updatePageResultsTable();
    } else {
        currentPage = selectedPage;
        
        // 根据当前激活的标签页执行不同操作
        const activeTab = document.querySelector('.tab-btn.active');
        if (activeTab) {
            const tabId = activeTab.getAttribute('data-tab');
            if (tabId === 'pageResults') {
                updatePageResultsTable();
            } else if (tabId === 'visualization') {
                showCurrentPageImage();
            }
        }
    }
    
    updateCurrentPageDisplay();
}

function zoomImage(factor) {
    scale *= factor;
    // 限制缩放范围
    scale = Math.max(0.1, Math.min(scale, 5.0));
    
    // 更新可视化
    showCurrentPageImage();
}

function resetZoom() {
    scale = 1.0;
    // 更新可视化
    showCurrentPageImage();
}

function downloadCurrentImage() {
    if (pdfImages.length === 0 || currentPage < 1 || currentPage > pdfImages.length) {
        showError('没有可下载的图像');
        return;
    }
    
    const imageUrl = pdfImages[currentPage - 1];
    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = `page_${currentPage}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showSuccess(`第 ${currentPage} 页图像下载开始`);
}

// PDF工具函数
function showPdfInfo() {
    if (!currentResults || !currentResults.pdf_info) {
        showError('没有PDF信息');
        return;
    }
    
    const pdfInfo = currentResults.pdf_info;
    const info = `
        <strong>总页数:</strong> ${pdfInfo.total_pages || 0}<br>
        <strong>文件大小:</strong> ${formatFileSize(pdfInfo.file_size || 0)}<br>
        <strong>创建时间:</strong> ${pdfInfo.creation_date || '未知'}<br>
        <strong>修改时间:</strong> ${pdfInfo.modification_date || '未知'}<br>
        <strong>作者:</strong> ${pdfInfo.author || '未知'}<br>
        <strong>标题:</strong> ${pdfInfo.title || '未知'}
    `;
    
    showModal('PDF信息', info);
}

function extractPdfText() {
    showNotification('PDF文本提取功能开发中', 'info');
}

function convertToImages() {
    showNotification('PDF转图像功能开发中', 'info');
}

function showBatchProcess() {
    showNotification('批量处理功能开发中', 'info');
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

function exportImages() {
    showNotification('图像导出功能开发中', 'info');
}

// 更新按页面查看的表格
function updatePageResultsTable() {
    if (!currentResults || !currentResults.combined_results || !currentResults.combined_results.text_items) {
        return;
    }
    
    const textItems = currentResults.combined_results.text_items;
    const pageResultsBody = document.getElementById('pageResultsBody');
    
    if (!pageResultsBody) {
        return;
    }
    
    pageResultsBody.innerHTML = '';
    
    // 获取当前页面的项目
    let itemsToShow = [];
    if (pageSelect.value === 'all') {
        // 显示所有页面的项目
        itemsToShow = textItems;
    } else {
        // 显示指定页面的项目
        const selectedPage = parseInt(pageSelect.value) || currentPage;
        itemsToShow = textItems.filter(item => item.page === selectedPage);
    }
    
    if (itemsToShow.length === 0) {
        pageResultsBody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-message">该页面没有识别结果</td>
            </tr>
        `;
        return;
    }
    
    // 添加项目到表格
    itemsToShow.forEach((item, index) => {
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
        
        pageResultsBody.appendChild(row);
    });
    
    // 绑定按钮事件
    document.querySelectorAll('#pageResultsBody .btn-view').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const index = parseInt(e.target.closest('button').getAttribute('data-index'));
            const selectedPage = parseInt(pageSelect.value) || currentPage;
            const pageItems = textItems.filter(item => item.page === selectedPage);
            if (pageItems[index]) {
                viewItemDetails(pageItems[index]);
            }
        });
    });

    document.querySelectorAll('#pageResultsBody .btn-copy').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const text = e.target.closest('button').getAttribute('data-text');
            copyToClipboard(text);
            showSuccess('文本已复制到剪贴板');
        });
    });
}

// 查看项目详情
function viewItemDetails(item) {
    const location = item.location || {};
    const details = `
        <strong>文本内容:</strong> ${escapeHtml(item.text)}<br>
        <strong>置信度:</strong> ${(item.confidence * 100).toFixed(1)}%<br>
        <strong>类型:</strong> ${item.type}<br>
        <strong>页码:</strong> ${item.page || 1}<br>
        <strong>位置:</strong> X=${location.left}, Y=${location.top}<br>
        <strong>尺寸:</strong> ${location.width}×${location.height} 像素
    `;
    
    showModal('识别项详情', details);
}

function viewPageDetails(pageNum) {
    // 获取该页面的详细信息
    if (!currentResults || !currentResults.combined_results || !currentResults.combined_results.text_items) {
        showModal(`第 ${pageNum} 页详情`, '该页面没有识别结果');
        return;
    }
    
    const textItems = currentResults.combined_results.text_items;
    const pageItems = textItems.filter(item => item.page === pageNum);
    
    let details = `<strong>第 ${pageNum} 页识别结果</strong><br><br>`;
    
    if (pageItems.length === 0) {
        details += '该页面没有识别到文本内容。';
    } else {
        details += `<strong>识别项数:</strong> ${pageItems.length}<br>`;
        
        // 计算该页面的平均置信度
        const avgConf = pageItems.reduce((sum, item) => sum + (item.confidence || 0), 0) / pageItems.length;
        details += `<strong>平均置信度:</strong> ${(avgConf * 100).toFixed(1)}%<br><br>`;
        
        details += '<strong>文本内容预览:</strong><br>';
        pageItems.slice(0, 5).forEach((item, i) => {
            details += `${i + 1}. ${escapeHtml(item.text.substring(0, 50))}${item.text.length > 50 ? '...' : ''}<br>`;
        });
        
        if (pageItems.length > 5) {
            details += `... 还有 ${pageItems.length - 5} 项`;
        }
    }
    
    showModal(`第 ${pageNum} 页详情`, details);
}

// 工具函数
function updateProgress(percent, text) {
    progressFill.style.width = `${percent}%`;
    progressText.textContent = text;
}

function updateStatus(stage, state) {
    const statusElement = {
        upload: statusUpload,
        convert: statusConvert,
        process: statusProcess,
        results: statusResults
    }[stage];
    
    if (!statusElement) return;
    
    // 获取父元素（status-step）和图标元素
    const statusStep = statusElement.closest('.status-step');
    const iconElement = statusStep ? statusStep.querySelector('.step-icon i') : null;
    
    if (!statusStep || !iconElement) return;
    
    // 移除所有状态类
    statusStep.classList.remove('active', 'completed', 'error');
    iconElement.classList.remove('fa-check-circle', 'fa-times-circle', 'fa-circle', 'fa-spinner', 'fa-spin');
    
    switch (state) {
        case 'active':
            statusStep.classList.add('active');
            iconElement.classList.add('fa-spinner', 'fa-spin');
            break;
        case 'completed':
            statusStep.classList.add('completed');
            iconElement.classList.add('fa-check-circle');
            break;
        case 'error':
            statusStep.classList.add('error');
            iconElement.classList.add('fa-times-circle');
            break;
        default:
            iconElement.classList.add('fa-circle');
    }
}

function updatePagesProgress(current, total) {
    const percent = total > 0 ? (current / total) * 100 : 0;
    pagesProgressFill.style.width = `${percent}%`;
    pagesProgressText.textContent = `${current}/${total} 页`;
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
    pdfSummary.style.display = 'none';
    pagesSummary.style.display = 'none';
    pdfTotalPages.textContent = '0';
    totalItems.textContent = '0';
    avgConfidence.textContent = '0%';
    processingTime.textContent = '0s';
    
    // 重置表格
    textResultsBody.innerHTML = `
        <tr>
            <td colspan="6" class="empty-message">暂无识别结果</td>
        </tr>
    `;
    
    coordinateResultsBody.innerHTML = `
        <tr>
            <td colspan="7" class="empty-message">暂无坐标信息</td>
        </tr>
    `;
    
    // 重置可视化
    visualizationPlaceholder.style.display = 'flex';
    visualizationCanvas.style.display = 'none';
    
    // 禁用导出按钮
    exportExcelBtn.disabled = true;
    exportJsonBtn.disabled = true;
    exportImagesBtn.disabled = true;
    
    // 清除当前结果
    currentResults = null;
    pdfImages = [];
    currentPage = 1;
    totalPages = 0;
    scale = 1.0;
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
