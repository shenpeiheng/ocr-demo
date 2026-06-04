/**
 * Flowchart OCR page.
 */

function getApiBaseUrl() {
    var pathname = window.location.pathname;
    var match = pathname.match(/^(\/proxy\/\d+)/);
    if (match) {
        return match[1];
    }
    return '';
}

const API_BASE_URL = getApiBaseUrl();
const MAX_FILES = 10;
const MAX_FILE_SIZE = 16 * 1024 * 1024;
const VALID_EXTENSIONS = ['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'gif', 'webp'];
const FLOWCHART_COLUMNS = ['流程', '流程说明', '流程ID', '流程描述', '操作方式', '部门'];
const DEFAULT_SAMPLE_IMAGES = [
    { path: 'static/images/demo/flow/1.png', name: '1.png' },
    { path: 'static/images/demo/flow/2.png', name: '2.png' }
];

let selectedFiles = [];
let currentBatchId = null;
let currentResults = null;
let currentResultView = 'all';
let processingStartTime = null;

const fileInput = document.getElementById('fileInput');
const selectFileBtn = document.getElementById('selectFileBtn');
const uploadArea = document.getElementById('uploadArea');
const filePanel = document.getElementById('filePanel');
const fileList = document.getElementById('fileList');
const clearFilesBtn = document.getElementById('clearFilesBtn');
const processBtn = document.getElementById('processBtn');
const ocrLoadingIndicator = document.getElementById('ocrLoadingIndicator');
const ocrStatsCard = document.getElementById('ocrStatsCard');
const imageCount = document.getElementById('imageCount');
const rowCount = document.getElementById('rowCount');
const departmentCount = document.getElementById('departmentCount');
const processingTime = document.getElementById('processingTime');
const flowchartResultsBody = document.getElementById('flowchartResultsBody');
const exportExcelBtn = document.getElementById('exportExcelBtn');
const exportJsonBtn = document.getElementById('exportJsonBtn');
const resultMeta = document.getElementById('resultMeta');
const flowchartResultTabs = document.getElementById('flowchartResultTabs');
const sampleImagesSection = document.getElementById('sampleImagesSection');

function init() {
    bindEvents();
    updateFilePanel();
    resetResults();
    loadDefaultSampleImages();
}

function bindEvents() {
    selectFileBtn.addEventListener('click', function(event) {
        event.stopPropagation();
        fileInput.click();
    });

    fileInput.addEventListener('change', function(event) {
        addFiles(Array.from(event.target.files || []));
        fileInput.value = '';
    });

    uploadArea.addEventListener('click', function(event) {
        if (event.target === selectFileBtn || selectFileBtn.contains(event.target)) {
            return;
        }
        fileInput.click();
    });

    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);

    clearFilesBtn.addEventListener('click', clearFiles);
    processBtn.addEventListener('click', processFlowcharts);
    exportExcelBtn.addEventListener('click', function() {
        downloadResult('excel');
    });
    exportJsonBtn.addEventListener('click', function() {
        downloadResult('json');
    });

    fileList.addEventListener('click', function(event) {
        const removeButton = event.target.closest('[data-remove-file]');
        if (!removeButton) {
            return;
        }
        removeFile(removeButton.getAttribute('data-remove-file'));
    });

    if (sampleImagesSection) {
        sampleImagesSection.addEventListener('click', function(event) {
            const sampleItem = event.target.closest('[data-sample-image]');
            if (!sampleItem) {
                return;
            }
            loadSampleImage(sampleItem.getAttribute('data-sample-image'), sampleItem.getAttribute('data-sample-name'), true);
        });
    }

    if (flowchartResultTabs) {
        flowchartResultTabs.addEventListener('click', function(event) {
            const tabButton = event.target.closest('[data-result-view]');
            if (!tabButton) {
                return;
            }

            currentResultView = tabButton.getAttribute('data-result-view') || 'all';
            renderResultTabs(currentResults || {});
            renderResults(currentResults || {}, currentResultView);
        });
    }
}

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
    addFiles(Array.from(event.dataTransfer.files || []));
}

function addFiles(files, options) {
    const addOptions = options || {};
    if (!files.length) {
        return;
    }

    const availableSlots = MAX_FILES - selectedFiles.length;
    if (availableSlots <= 0) {
        showError(`一次最多支持 ${MAX_FILES} 张流程图图片`);
        return;
    }

    const validFiles = [];
    files.forEach(function(file) {
        const validation = validateFile(file);
        if (!validation.valid) {
            showError(validation.message);
            return;
        }
        if (isDuplicateFile(file)) {
            showNotification(`已跳过重复文件：${file.name}`, 'info');
            return;
        }
        validFiles.push(file);
    });

    const filesToAdd = validFiles.slice(0, availableSlots);
    if (validFiles.length > filesToAdd.length) {
        showNotification(`已达到上限，只添加前 ${filesToAdd.length} 张图片`, 'info');
    }

    filesToAdd.forEach(function(file) {
        const item = {
            id: createFileId(file),
            file: file,
            previewUrl: URL.createObjectURL(file),
            dimensions: '读取中...',
            sourcePath: addOptions.sourcePath || null
        };
        selectedFiles.push(item);
        loadImageDimensions(item);
    });

    if (filesToAdd.length > 0) {
        updateSelectedSamples();
        resetResults();
        updateFilePanel();
    }
}

async function loadDefaultSampleImages() {
    for (const sampleImage of DEFAULT_SAMPLE_IMAGES) {
        await loadSampleImage(sampleImage.path, sampleImage.name, false);
    }
    updateSelectedSamples();
}

async function loadSampleImage(imagePath, imageName, shouldSelect) {
    if (!imagePath) {
        return;
    }

    if (hasSelectedSample(imagePath)) {
        updateSelectedSamples();
        return;
    }

    try {
        const response = await fetch(toStaticUrl(imagePath));
        if (!response.ok) {
            throw new Error(`示例图片加载失败: ${response.status}`);
        }

        const blob = await response.blob();
        const filename = imageName || imagePath.split('/').pop() || 'flowchart.png';
        const file = new File([blob], filename, {
            type: blob.type || 'image/png',
            lastModified: 0
        });

        addFiles([file], { fromSample: true, sourcePath: imagePath });
        if (shouldSelect) {
            updateSelectedSamples();
        }
    } catch (error) {
        console.error('加载流程图示例失败:', error);
        showError('示例图片加载失败，请手动选择流程图图片');
    }
}

function toStaticUrl(path) {
    if (/^https?:\/\//i.test(path) || path.startsWith(API_BASE_URL)) {
        return path;
    }

    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${API_BASE_URL}${normalizedPath}`;
}

function hasSelectedSample(imagePath) {
    return selectedFiles.some(function(item) {
        return item.sourcePath === imagePath;
    });
}

function updateSelectedSamples() {
    if (!sampleImagesSection) {
        return;
    }

    const selectedSamplePaths = new Set(selectedFiles.map(function(item) {
        return item.sourcePath;
    }).filter(Boolean));

    sampleImagesSection.querySelectorAll('[data-sample-image]').forEach(function(item) {
        item.classList.toggle('selected', selectedSamplePaths.has(item.getAttribute('data-sample-image')));
    });
}

function validateFile(file) {
    const extension = getFileExtension(file.name);
    if (!VALID_EXTENSIONS.includes(extension)) {
        return {
            valid: false,
            message: `不支持的图片格式：${file.name}`
        };
    }

    if (file.size > MAX_FILE_SIZE) {
        return {
            valid: false,
            message: `${file.name} 超过 16MB，请压缩后再上传`
        };
    }

    return { valid: true };
}

function isDuplicateFile(file) {
    return selectedFiles.some(function(item) {
        return item.file.name === file.name
            && item.file.size === file.size
            && item.file.lastModified === file.lastModified;
    });
}

function createFileId(file) {
    return `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(16).slice(2)}`;
}

function loadImageDimensions(item) {
    const image = new Image();
    image.onload = function() {
        item.dimensions = `${image.naturalWidth} x ${image.naturalHeight} 像素`;
        updateFilePanel();
    };
    image.onerror = function() {
        item.dimensions = '无法读取尺寸';
        updateFilePanel();
    };
    image.src = item.previewUrl;
}

function updateFilePanel() {
    filePanel.style.display = selectedFiles.length > 0 ? 'block' : 'none';
    processBtn.disabled = selectedFiles.length === 0;

    if (!selectedFiles.length) {
        fileList.innerHTML = '';
        return;
    }

    fileList.innerHTML = selectedFiles.map(function(item, index) {
        return `
            <div class="flowchart-file-item">
                <img class="flowchart-file-thumb" src="${item.previewUrl}" alt="${escapeHtml(item.file.name)}">
                <div class="flowchart-file-meta">
                    <div class="flowchart-file-name" title="${escapeHtml(item.file.name)}">${index + 1}. ${escapeHtml(item.file.name)}</div>
                    <div class="flowchart-file-detail">
                        <span><i class="fas fa-hdd"></i> ${formatFileSize(item.file.size)}</span>
                        <span><i class="fas fa-vector-square"></i> ${escapeHtml(item.dimensions)}</span>
                    </div>
                </div>
                <button type="button" class="flowchart-file-remove" data-remove-file="${escapeHtml(item.id)}" title="移除图片">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    }).join('');
}

function removeFile(fileId) {
    const nextFiles = [];
    selectedFiles.forEach(function(item) {
        if (item.id === fileId) {
            URL.revokeObjectURL(item.previewUrl);
            return;
        }
        nextFiles.push(item);
    });
    selectedFiles = nextFiles;
    updateSelectedSamples();
    resetResults();
    updateFilePanel();
}

function clearFiles() {
    selectedFiles.forEach(function(item) {
        URL.revokeObjectURL(item.previewUrl);
    });
    selectedFiles = [];
    fileInput.value = '';
    updateSelectedSamples();
    resetResults();
    updateFilePanel();
}

async function processFlowcharts() {
    if (!selectedFiles.length) {
        showError('请先选择流程图图片');
        return;
    }

    processingStartTime = Date.now();
    currentBatchId = null;
    currentResults = null;
    const formData = new FormData();
    selectedFiles.forEach(function(item) {
        formData.append('files', item.file);
    });

    try {
        setProcessingState(true);
        const response = await fetch(`${API_BASE_URL}/api/flowchart/process`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json().catch(function() {
            return {};
        });

        if (!response.ok || !data.success) {
            throw new Error(data.error || `识别失败: ${response.status}`);
        }

        currentBatchId = data.batch_id;
        currentResults = data.results || {};
        currentResultView = 'all';

        renderResultTabs(currentResults);
        renderResults(currentResults, currentResultView);
        updateStats(currentResults);
        updateDownloadButtons();

        const failedCount = (currentResults.files || []).filter(function(fileResult) {
            return !fileResult.success;
        }).length;
        if (failedCount > 0) {
            showNotification(`识别完成，${failedCount} 张图片未解析成功`, 'info');
        } else {
            showSuccess('流程图识别完成');
        }
    } catch (error) {
        console.error('流程图识别错误:', error);
        showError(`识别失败: ${error.message}`);
    } finally {
        setProcessingState(false);
    }
}

function setProcessingState(isProcessing) {
    processBtn.disabled = isProcessing || selectedFiles.length === 0;
    processBtn.innerHTML = isProcessing
        ? '<i class="fas fa-spinner fa-spin"></i> 检测中...'
        : '<i class="fas fa-search"></i> 开始检测';

    if (ocrLoadingIndicator) {
        ocrLoadingIndicator.classList.toggle('active', isProcessing);
    }
    if (ocrStatsCard && isProcessing) {
        ocrStatsCard.style.display = 'none';
    }
    if (isProcessing) {
        exportExcelBtn.disabled = true;
        exportJsonBtn.disabled = true;
    } else {
        updateDownloadButtons();
    }
}

function renderResultTabs(results) {
    if (!flowchartResultTabs) {
        return;
    }

    const files = Array.isArray(results.files) ? results.files : [];
    if (files.length <= 1) {
        currentResultView = 'all';
        flowchartResultTabs.style.display = 'none';
        flowchartResultTabs.innerHTML = '';
        return;
    }

    const rows = Array.isArray(results.rows) ? results.rows : [];
    const tabs = [{
        key: 'all',
        label: '全部图片',
        count: rows.length,
        success: true
    }].concat(files.map(function(fileResult, index) {
        const fileRows = Array.isArray(fileResult.rows) ? fileResult.rows : [];
        return {
            key: `file:${fileResult.filename || index}`,
            label: fileResult.original_filename || fileResult.filename || `图片${index + 1}`,
            count: fileRows.length,
            success: fileResult.success !== false,
            error: fileResult.error || ''
        };
    }));

    if (!tabs.some(function(tab) { return tab.key === currentResultView; })) {
        currentResultView = 'all';
    }

    flowchartResultTabs.style.display = 'flex';
    flowchartResultTabs.innerHTML = tabs.map(function(tab) {
        const isActive = tab.key === currentResultView;
        const statusClass = tab.success ? '' : ' is-error';
        return `
            <button type="button"
                class="flowchart-result-tab${isActive ? ' active' : ''}${statusClass}"
                data-result-view="${escapeHtml(tab.key)}"
                title="${escapeHtml(tab.error || tab.label)}">
                <span>${escapeHtml(tab.label)}</span>
                <em>${tab.count}</em>
            </button>
        `;
    }).join('');
}

function renderResults(results, viewKey) {
    const activeView = viewKey || 'all';
    const fileResult = getFileResultByView(results, activeView);
    const rows = activeView === 'all'
        ? (Array.isArray(results.rows) ? results.rows : [])
        : (fileResult && Array.isArray(fileResult.rows) ? fileResult.rows : []);

    if (!rows.length) {
        const emptyText = getEmptyResultText(activeView, fileResult);
        flowchartResultsBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-message">${escapeHtml(emptyText)}</td>
            </tr>
        `;
        resultMeta.innerHTML = `<span><i class="fas fa-info-circle"></i> ${escapeHtml(emptyText)}</span>`;
        return;
    }

    flowchartResultsBody.innerHTML = rows.map(function(row, index) {
        const previous = rows[index - 1] || {};
        const isNewGroup = index === 0
            || row['流程'] !== previous['流程']
            || row['流程说明'] !== previous['流程说明'];
        const canGroup = Boolean(row['流程'] || row['流程说明']);
        const rowspan = isNewGroup && canGroup ? getGroupSpan(rows, index) : 1;
        const groupCells = isNewGroup || !canGroup
            ? `
                <td class="flowchart-group-cell" rowspan="${rowspan}">${escapeHtml(row['流程'] || '-')}</td>
                <td class="flowchart-group-cell flowchart-note-cell" rowspan="${rowspan}">${escapeHtml(row['流程说明'] || '-')}</td>
            `
            : '';

        return `
            <tr>
                ${groupCells}
                <td class="flowchart-id-cell">${escapeHtml(row['流程ID'] || '-')}</td>
                <td class="flowchart-description-cell">${escapeHtml(row['流程描述'] || '-')}</td>
                <td>${escapeHtml(row['操作方式'] || '-')}</td>
                <td>${escapeHtml(row['部门'] || '-')}</td>
            </tr>
        `;
    }).join('');

    const stats = results.stats || {};
    const viewText = activeView === 'all'
        ? `全部图片已解析 ${rows.length} 条流程节点`
        : `${fileResult ? (fileResult.original_filename || fileResult.filename) : '当前图片'} 已解析 ${rows.length} 条流程节点`;
    resultMeta.innerHTML = `
        <span><i class="fas fa-check-circle"></i> ${escapeHtml(viewText)}</span>
        <span>图片 ${stats.successful_images || selectedFiles.length}/${stats.image_count || selectedFiles.length}</span>
    `;
}

function getFileResultByView(results, viewKey) {
    if (!viewKey || viewKey === 'all') {
        return null;
    }

    const files = Array.isArray(results.files) ? results.files : [];
    const targetKey = viewKey.replace(/^file:/, '');
    return files.find(function(fileResult, index) {
        return String(fileResult.filename || index) === targetKey;
    }) || null;
}

function getEmptyResultText(viewKey, fileResult) {
    if (viewKey !== 'all' && fileResult && fileResult.success === false) {
        return fileResult.error || '该图片识别失败，请检查图片清晰度后重试';
    }

    if (viewKey !== 'all') {
        return '该图片未解析到流程节点';
    }

    return '未解析到有效流程节点，请检查图片清晰度后重试';
}

function getGroupSpan(rows, startIndex) {
    const current = rows[startIndex];
    let span = 1;
    for (let index = startIndex + 1; index < rows.length; index += 1) {
        if (rows[index]['流程'] !== current['流程'] || rows[index]['流程说明'] !== current['流程说明']) {
            break;
        }
        span += 1;
    }
    return span;
}

function updateStats(results) {
    const rows = Array.isArray(results.rows) ? results.rows : [];
    const stats = results.stats || {};
    const departments = new Set(rows.map(function(row) {
        return row['部门'];
    }).filter(Boolean));
    const elapsedSeconds = processingStartTime ? ((Date.now() - processingStartTime) / 1000).toFixed(2) : '0.00';

    imageCount.textContent = stats.image_count || selectedFiles.length;
    rowCount.textContent = results.total_rows || rows.length;
    departmentCount.textContent = stats.department_count || departments.size;
    processingTime.textContent = `${stats.processing_time || elapsedSeconds}s`;

    if (ocrStatsCard) {
        ocrStatsCard.style.display = 'block';
    }
}

function updateDownloadButtons() {
    const hasBatch = Boolean(currentBatchId);
    exportExcelBtn.disabled = !hasBatch;
    exportJsonBtn.disabled = !hasBatch;
}

function downloadResult(format) {
    if (!currentBatchId) {
        showError('暂无可导出的识别结果');
        return;
    }

    const safeBatchId = encodeURIComponent(currentBatchId);
    window.open(`${API_BASE_URL}/api/flowchart/download/${format}/${safeBatchId}`, '_blank');
}

function resetResults() {
    currentBatchId = null;
    currentResults = null;
    currentResultView = 'all';
    if (flowchartResultsBody) {
        flowchartResultsBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-message">暂无识别结果</td>
            </tr>
        `;
    }
    if (resultMeta) {
        resultMeta.innerHTML = '<span><i class="fas fa-info-circle"></i> 识别完成后在线预览表格，可直接导出Excel</span>';
    }
    if (flowchartResultTabs) {
        flowchartResultTabs.style.display = 'none';
        flowchartResultTabs.innerHTML = '';
    }
    if (ocrStatsCard) {
        ocrStatsCard.style.display = 'none';
    }
    if (ocrLoadingIndicator) {
        ocrLoadingIndicator.classList.remove('active');
    }
    if (imageCount) imageCount.textContent = '0';
    if (rowCount) rowCount.textContent = '0';
    if (departmentCount) departmentCount.textContent = '0';
    if (processingTime) processingTime.textContent = '0s';
    if (exportExcelBtn) exportExcelBtn.disabled = true;
    if (exportJsonBtn) exportJsonBtn.disabled = true;
}

function getFileExtension(filename) {
    const parts = String(filename || '').toLowerCase().split('.');
    return parts.length > 1 ? parts.pop() : '';
}

function formatFileSize(bytes) {
    if (!bytes) {
        return '0 Bytes';
    }

    const units = ['Bytes', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

function showError(message) {
    showNotification(message, 'error');
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    const icon = type === 'error'
        ? 'exclamation-circle'
        : type === 'success'
            ? 'check-circle'
            : 'info-circle';
    const background = type === 'error'
        ? '#b42346'
        : type === 'success'
            ? '#12805c'
            : '#1f4e79';

    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span>${escapeHtml(message)}</span>
        <button class="notification-close" type="button"><i class="fas fa-times"></i></button>
    `;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        max-width: min(420px, calc(100vw - 40px));
        padding: 12px 14px;
        background: ${background};
        color: #ffffff;
        border-radius: 6px;
        box-shadow: 0 8px 24px rgba(16, 24, 40, 0.16);
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 3000;
        font-size: 13px;
        line-height: 1.4;
    `;

    const closeButton = notification.querySelector('.notification-close');
    closeButton.style.cssText = `
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        margin-left: 4px;
        border: none;
        background: transparent;
        color: #ffffff;
        cursor: pointer;
    `;

    document.body.appendChild(notification);
    closeButton.addEventListener('click', function() {
        removeNotification(notification);
    });

    setTimeout(function() {
        removeNotification(notification);
    }, 4500);
}

function removeNotification(notification) {
    if (notification && notification.parentNode) {
        notification.parentNode.removeChild(notification);
    }
}

document.addEventListener('DOMContentLoaded', init);
