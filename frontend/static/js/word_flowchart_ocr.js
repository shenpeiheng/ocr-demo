/**
 * Word flowchart OCR batch page.
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
const MAX_WORD_FILE_SIZE = 64 * 1024 * 1024;
const SAMPLE_WORD_DOC = {
    name: 'ERP_Blueprint_FlowCharts_Only.docx',
    path: 'flow/ERP_Blueprint_FlowCharts_Only.docx'
};

let selectedWord = {
    useSample: true,
    file: null,
    name: SAMPLE_WORD_DOC.name,
    size: 0,
    path: SAMPLE_WORD_DOC.path
};
let currentTaskId = null;
let currentBatchId = null;
let currentTask = null;
let pollTimer = null;
let processingStartTime = null;
let activeTab = 'status';
let isProcessingTask = false;
let processingMode = '';
let selectedImageKeys = new Set();
let selectionTaskId = null;
let selectionFileSignature = '';
let hasEditedSelection = false;

const wordUploadArea = document.getElementById('wordUploadArea');
const wordFileInput = document.getElementById('wordFileInput');
const selectWordBtn = document.getElementById('selectWordBtn');
const sampleWordBtn = document.getElementById('sampleWordBtn');
const clearWordBtn = document.getElementById('clearWordBtn');
const wordDocCard = document.getElementById('wordDocCard');
const processWordBtn = document.getElementById('processWordBtn');
const startSelectedBtn = document.getElementById('startSelectedBtn');
const wordLoadingIndicator = document.getElementById('wordLoadingIndicator');
const wordStatsCard = document.getElementById('wordStatsCard');
const totalImages = document.getElementById('totalImages');
const processedImages = document.getElementById('processedImages');
const successImages = document.getElementById('successImages');
const failedImages = document.getElementById('failedImages');
const wordRowCount = document.getElementById('wordRowCount');
const wordProcessingTime = document.getElementById('wordProcessingTime');
const wordResultMeta = document.getElementById('wordResultMeta');
const wordStatusBody = document.getElementById('wordStatusBody');
const wordResultsBody = document.getElementById('wordResultsBody');
const wordFlowchartTabs = document.getElementById('wordFlowchartTabs');
const statusTabCount = document.getElementById('statusTabCount');
const resultTabCount = document.getElementById('resultTabCount');
const selectAllWordImages = document.getElementById('selectAllWordImages');
const retryFailedBtn = document.getElementById('retryFailedBtn');
const exportWordExcelBtn = document.getElementById('exportWordExcelBtn');
const exportWordJsonBtn = document.getElementById('exportWordJsonBtn');

function init() {
    bindEvents();
    renderSelectedWord();
    resetTaskView();
}

function bindEvents() {
    selectWordBtn.addEventListener('click', function(event) {
        event.stopPropagation();
        wordFileInput.click();
    });

    wordFileInput.addEventListener('change', function(event) {
        const file = (event.target.files || [])[0];
        if (file) {
            setUploadedWord(file);
        }
        wordFileInput.value = '';
    });

    wordUploadArea.addEventListener('click', function(event) {
        if (event.target === selectWordBtn || selectWordBtn.contains(event.target)) {
            return;
        }
        wordFileInput.click();
    });

    wordUploadArea.addEventListener('dragover', function(event) {
        event.preventDefault();
        wordUploadArea.classList.add('drag-over');
    });

    wordUploadArea.addEventListener('dragleave', function(event) {
        event.preventDefault();
        wordUploadArea.classList.remove('drag-over');
    });

    wordUploadArea.addEventListener('drop', function(event) {
        event.preventDefault();
        wordUploadArea.classList.remove('drag-over');
        const file = (event.dataTransfer.files || [])[0];
        if (file) {
            setUploadedWord(file);
        }
    });

    sampleWordBtn.addEventListener('click', useSampleWord);
    clearWordBtn.addEventListener('click', useSampleWord);
    processWordBtn.addEventListener('click', startWordProcess);
    startSelectedBtn.addEventListener('click', startSelectedImages);
    retryFailedBtn.addEventListener('click', retryFailedImages);

    if (selectAllWordImages) {
        selectAllWordImages.addEventListener('change', function(event) {
            toggleAllWordImages(event.target.checked);
        });
    }

    wordStatusBody.addEventListener('change', function(event) {
        const checkbox = event.target.closest('.word-file-checkbox');
        if (!checkbox || checkbox.id === 'selectAllWordImages') {
            return;
        }
        updateSelectedImage(checkbox.dataset.fileKey, checkbox.checked);
    });

    exportWordExcelBtn.addEventListener('click', function() {
        downloadResult('excel');
    });

    exportWordJsonBtn.addEventListener('click', function() {
        downloadResult('json');
    });

    wordFlowchartTabs.addEventListener('click', function(event) {
        const tabButton = event.target.closest('[data-word-tab]');
        if (!tabButton) {
            return;
        }
        activeTab = tabButton.getAttribute('data-word-tab') || 'status';
        renderActiveTab();
    });
}

function setUploadedWord(file) {
    const validation = validateWordFile(file);
    if (!validation.valid) {
        showError(validation.message);
        return;
    }

    selectedWord = {
        useSample: false,
        file: file,
        name: file.name,
        size: file.size,
        path: ''
    };
    stopPolling();
    resetTaskView();
    renderSelectedWord();
}

function useSampleWord() {
    selectedWord = {
        useSample: true,
        file: null,
        name: SAMPLE_WORD_DOC.name,
        size: 0,
        path: SAMPLE_WORD_DOC.path
    };
    stopPolling();
    resetTaskView();
    renderSelectedWord();
}

function validateWordFile(file) {
    if (!/\.docx$/i.test(file.name || '')) {
        return { valid: false, message: '仅支持DOCX格式Word文档' };
    }

    if (file.size > MAX_WORD_FILE_SIZE) {
        return { valid: false, message: `${file.name} 超过 64MB，请拆分或压缩后再上传` };
    }

    return { valid: true };
}

function renderSelectedWord() {
    const sourceLabel = selectedWord.useSample ? '示例文件' : '本地上传';
    const sizeText = selectedWord.useSample ? '默认文档' : formatFileSize(selectedWord.size);

    if (sampleWordBtn) {
        sampleWordBtn.classList.toggle('selected', selectedWord.useSample);
    }

    wordDocCard.innerHTML = `
        <div class="word-doc-icon"><i class="fas fa-file-word"></i></div>
        <div class="word-doc-info">
            <div class="word-doc-name" title="${escapeHtml(selectedWord.name)}">${escapeHtml(selectedWord.name)}</div>
            <div class="word-doc-meta">
                <span><i class="fas fa-tag"></i> ${escapeHtml(sourceLabel)}</span>
                <span><i class="fas fa-hdd"></i> ${escapeHtml(sizeText)}</span>
                ${selectedWord.path ? `<span><i class="fas fa-folder"></i> ${escapeHtml(selectedWord.path)}</span>` : ''}
            </div>
        </div>
    `;
}

async function startWordProcess() {
    if (!selectedWord.useSample && !selectedWord.file) {
        showError('请先选择Word文档');
        return;
    }

    stopPolling();
    resetTaskView();
    setProcessingState(true, 'extract');
    processingStartTime = Date.now();

    const formData = new FormData();
    if (selectedWord.useSample) {
        formData.append('use_sample', 'true');
    } else {
        formData.append('file', selectedWord.file);
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/flowchart/word/process`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json().catch(function() {
            return {};
        });

        if (!response.ok || !data.success) {
            throw new Error(data.error || `任务启动失败: ${response.status}`);
        }

        currentTaskId = data.task_id;
        currentBatchId = data.batch_id;
        wordResultMeta.innerHTML = '<span><i class="fas fa-spinner fa-spin"></i> 正在提取Word中的流程图图片</span>';
        pollTaskStatus();
        pollTimer = setInterval(pollTaskStatus, 2000);
    } catch (error) {
        console.error('Word流程图图片提取失败:', error);
        setProcessingState(false);
        showError(`图片提取失败: ${error.message}`);
    }
}

async function startSelectedImages() {
    if (!currentTaskId || !currentTask || currentTask.status !== 'ready') {
        showError('请先提取Word中的流程图图片');
        return;
    }

    const selectedFiles = getSelectedWordFiles();
    if (!selectedFiles.length) {
        showError('请至少勾选一张图片后再开始检测');
        return;
    }

    stopPolling();
    setProcessingState(true, 'start');
    processingStartTime = Date.now();
    activeTab = 'status';
    renderActiveTab();

    try {
        const response = await fetch(`${API_BASE_URL}/api/flowchart/word/start/${encodeURIComponent(currentTaskId)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filenames: selectedFiles.map(function(fileResult) {
                    return fileResult.filename;
                })
            })
        });
        const data = await response.json().catch(function() {
            return {};
        });

        if (!response.ok || !data.success) {
            throw new Error(data.error || `检测启动失败: ${response.status}`);
        }

        currentBatchId = data.batch_id || currentBatchId;
        wordResultMeta.innerHTML = '<span><i class="fas fa-spinner fa-spin"></i> 正在调用模型识别已勾选图片</span>';
        pollTaskStatus();
        pollTimer = setInterval(pollTaskStatus, 2000);
    } catch (error) {
        console.error('Word流程图检测启动失败:', error);
        setProcessingState(false);
        updateDownloadButtons(currentTask);
        showError(`检测启动失败: ${error.message}`);
    }
}

async function retryFailedImages() {
    if (!currentTaskId) {
        showError('暂无可重试的任务');
        return;
    }

    const failedCount = Number((currentTask && currentTask.failed_images) || 0);
    if (!failedCount) {
        showError('当前任务没有失败图片需要重试');
        return;
    }

    stopPolling();
    setProcessingState(true, 'retry');
    processingStartTime = Date.now();

    try {
        const response = await fetch(`${API_BASE_URL}/api/flowchart/word/retry/${encodeURIComponent(currentTaskId)}`, {
            method: 'POST'
        });
        const data = await response.json().catch(function() {
            return {};
        });

        if (!response.ok || !data.success) {
            throw new Error(data.error || `重试启动失败: ${response.status}`);
        }

        currentBatchId = data.batch_id || currentBatchId;
        wordResultMeta.innerHTML = '<span><i class="fas fa-spinner fa-spin"></i> 正在重试失败图片</span>';
        pollTaskStatus();
        pollTimer = setInterval(pollTaskStatus, 2000);
    } catch (error) {
        console.error('Word流程图失败图片重试启动失败:', error);
        setProcessingState(false);
        updateDownloadButtons(currentTask);
        showError(`重试启动失败: ${error.message}`);
    }
}

async function pollTaskStatus() {
    if (!currentTaskId) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/flowchart/word/status/${encodeURIComponent(currentTaskId)}`);
        const task = await response.json().catch(function() {
            return {};
        });

        if (!response.ok) {
            throw new Error(task.error || `读取任务状态失败: ${response.status}`);
        }

        renderTask(task);

        if (task.status === 'ready') {
            stopPolling();
            setProcessingState(false);
            renderTask(task);
            updateDownloadButtons(task);
            updateSelectionControls();
            showNotification(`已提取 ${task.total_images || 0} 张图片，请勾选后开始检测`, 'info');
        } else if (task.status === 'completed') {
            stopPolling();
            setProcessingState(false);
            updateDownloadButtons(task);
            const failedCount = Number(task.failed_images || 0);
            if (failedCount > 0) {
                showNotification(`处理完成，成功 ${task.successful_images || 0} 张，失败 ${failedCount} 张`, 'info');
            } else {
                showSuccess('Word流程图批量识别完成');
            }
        } else if (task.status === 'failed') {
            stopPolling();
            setProcessingState(false);
            updateDownloadButtons(task);
            showError(task.message || 'Word流程图批量识别失败');
        }
    } catch (error) {
        console.error('读取Word流程图任务状态失败:', error);
        stopPolling();
        setProcessingState(false);
        showError(`读取任务状态失败: ${error.message}`);
    }
}

function renderTask(task) {
    currentTask = task;
    currentBatchId = task.batch_id || currentBatchId;
    const files = Array.isArray(task.files) ? task.files : [];
    const rows = task.results && Array.isArray(task.results.rows) ? task.results.rows : [];
    const total = Number(task.total_images || files.length || 0);
    const processed = Number(task.processed_images || getProcessedCount(files));
    const success = Number(task.successful_images || files.filter(function(item) { return item.success === true; }).length);
    const failed = Number(task.failed_images || files.filter(function(item) { return item.success === false; }).length);
    const totalRows = Number(task.total_rows || rows.length || 0);

    syncSelectionFromTask(task, files);
    totalImages.textContent = total;
    processedImages.textContent = processed;
    successImages.textContent = success;
    failedImages.textContent = failed;
    wordRowCount.textContent = totalRows;
    wordProcessingTime.textContent = getTaskElapsedTime(task);
    statusTabCount.textContent = total || files.length || 0;
    resultTabCount.textContent = totalRows;

    if (wordStatsCard) {
        wordStatsCard.style.display = 'block';
    }

    renderStatusRows(files, total);
    renderResultRows(rows);
    renderTaskMeta(task, processed, total, success, failed, totalRows);
    updateDownloadButtons(task);
    updateSelectionControls();
}

function renderTaskMeta(task, processed, total, success, failed, totalRows) {
    const icon = task.status === 'completed'
        ? 'check-circle'
        : task.status === 'failed'
            ? 'times-circle'
            : task.status === 'ready'
                ? 'tasks'
                : 'spinner fa-spin';
    const message = task.message || '等待处理';
    const selectedCount = task.status === 'ready'
        ? selectedImageKeys.size
        : Number(task.selected_images || 0);
    const progressTotal = selectedCount || total || 0;
    wordResultMeta.innerHTML = `
        <span><i class="fas fa-${icon}"></i> ${escapeHtml(message)}</span>
        <span>进度 ${processed}/${progressTotal}</span>
        <span>已选 ${selectedCount} 张</span>
        <span>成功 ${success} 张</span>
        <span>失败 ${failed} 张</span>
        <span>流程节点 ${totalRows} 条</span>
    `;
}

function renderStatusRows(files, totalImagesCount) {
    if (!files.length) {
        wordStatusBody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-message">${totalImagesCount ? '正在提取图片，请稍候' : '暂无处理任务'}</td>
            </tr>
        `;
        return;
    }

    const canSelect = canEditSelection();
    wordStatusBody.innerHTML = files.map(function(fileResult, index) {
        const status = normalizeStatus(fileResult);
        const statusLabel = getStatusLabel(status);
        const rowCount = Number(fileResult.total_rows || 0);
        const errorText = status === 'failed' ? (fileResult.error || '识别失败') : '';
        const timeText = fileResult.processing_time ? `${fileResult.processing_time}s` : '-';
        const imageIndex = fileResult.image_index || index + 1;
        const filename = fileResult.original_filename || fileResult.filename || `图片${imageIndex}`;
        const fileKey = getFileKey(fileResult);
        const checked = isWordFileSelected(fileResult);
        const checkboxTitle = canSelect ? '选择该图片参与识别' : '当前状态不可修改选择';

        return `
            <tr>
                <td class="status-select-cell">
                    <input
                        type="checkbox"
                        class="word-file-checkbox"
                        data-file-key="${escapeHtml(fileKey)}"
                        ${checked ? 'checked' : ''}
                        ${canSelect ? '' : 'disabled'}
                        title="${escapeHtml(checkboxTitle)}"
                    >
                </td>
                <td class="status-index-cell">${escapeHtml(imageIndex)}</td>
                <td class="status-source-cell" title="${escapeHtml(filename)}">${escapeHtml(filename)}</td>
                <td><span class="word-status-badge ${status}">${escapeHtml(statusLabel)}</span></td>
                <td>${rowCount}</td>
                <td>${escapeHtml(timeText)}</td>
                <td class="status-error-cell" title="${escapeHtml(errorText)}">${escapeHtml(errorText || '-')}</td>
            </tr>
        `;
    }).join('');
}

function renderResultRows(rows) {
    if (!rows.length) {
        wordResultsBody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-message">暂无识别结果</td>
            </tr>
        `;
        return;
    }

    wordResultsBody.innerHTML = rows.map(function(row) {
        return `
            <tr>
                <td class="flowchart-id-cell">${escapeHtml(row['图片序号'] || '-')}</td>
                <td class="word-source-image-cell" title="${escapeHtml(row['来源图片'] || '')}">${escapeHtml(row['来源图片'] || '-')}</td>
                <td class="flowchart-group-cell">${escapeHtml(row['流程'] || '-')}</td>
                <td class="flowchart-note-cell">${escapeHtml(row['流程说明'] || '-')}</td>
                <td class="flowchart-id-cell">${escapeHtml(row['流程ID'] || '-')}</td>
                <td class="flowchart-description-cell">${escapeHtml(row['流程描述'] || '-')}</td>
                <td>${escapeHtml(row['操作方式'] || '-')}</td>
                <td>${escapeHtml(row['部门'] || '-')}</td>
            </tr>
        `;
    }).join('');
}

function normalizeStatus(fileResult) {
    if (fileResult.success === true || fileResult.status === 'success') {
        return 'success';
    }
    if (fileResult.success === false || fileResult.status === 'failed') {
        return 'failed';
    }
    if (fileResult.status === 'running') {
        return 'running';
    }
    if (fileResult.status === 'skipped' || fileResult.selected === false) {
        return 'skipped';
    }
    return 'pending';
}

function getStatusLabel(status) {
    const labels = {
        success: '成功',
        failed: '失败',
        running: '处理中',
        skipped: '未选择',
        pending: '待检测'
    };
    return labels[status] || '待检测';
}

function getProcessedCount(files) {
    return files.filter(function(item) {
        return normalizeStatus(item) === 'success' || normalizeStatus(item) === 'failed';
    }).length;
}

function syncSelectionFromTask(task, files) {
    const taskId = task.task_id || currentTaskId;
    const fileSignature = files.map(getFileKey).join('|');
    if (selectionTaskId === taskId && (hasEditedSelection || selectionFileSignature === fileSignature)) {
        return;
    }

    selectedImageKeys = new Set();
    files.forEach(function(fileResult) {
        if (fileResult.selected !== false && normalizeStatus(fileResult) !== 'skipped') {
            selectedImageKeys.add(getFileKey(fileResult));
        }
    });
    selectionTaskId = taskId;
    selectionFileSignature = fileSignature;
    hasEditedSelection = false;
}

function getFileKey(fileResult) {
    return String(fileResult.filename || fileResult.image_index || fileResult.original_filename || '');
}

function isWordFileSelected(fileResult) {
    const key = getFileKey(fileResult);
    if (currentTask && currentTask.status === 'ready') {
        return selectedImageKeys.has(key);
    }
    return fileResult.selected !== false && normalizeStatus(fileResult) !== 'skipped';
}

function canEditSelection() {
    return Boolean(currentTask && currentTask.status === 'ready' && !isProcessingTask);
}

function getSelectedWordFiles() {
    if (!currentTask || !Array.isArray(currentTask.files)) {
        return [];
    }

    return currentTask.files.filter(function(fileResult) {
        return selectedImageKeys.has(getFileKey(fileResult));
    });
}

function updateSelectedImage(fileKey, checked) {
    if (!canEditSelection() || !fileKey) {
        return;
    }

    if (checked) {
        selectedImageKeys.add(fileKey);
    } else {
        selectedImageKeys.delete(fileKey);
    }
    hasEditedSelection = true;
    updateSelectionControls();
    renderTaskMeta(
        currentTask,
        Number(currentTask.processed_images || getProcessedCount(currentTask.files || [])),
        Number(currentTask.total_images || (currentTask.files || []).length || 0),
        Number(currentTask.successful_images || 0),
        Number(currentTask.failed_images || 0),
        Number(currentTask.total_rows || 0)
    );
}

function toggleAllWordImages(checked) {
    if (!canEditSelection() || !currentTask || !Array.isArray(currentTask.files)) {
        updateSelectionControls();
        return;
    }

    currentTask.files.forEach(function(fileResult) {
        const key = getFileKey(fileResult);
        if (!key) {
            return;
        }
        if (checked) {
            selectedImageKeys.add(key);
        } else {
            selectedImageKeys.delete(key);
        }
    });

    hasEditedSelection = true;
    renderStatusRows(currentTask.files, Number(currentTask.total_images || currentTask.files.length || 0));
    updateSelectionControls();
    renderTaskMeta(
        currentTask,
        Number(currentTask.processed_images || getProcessedCount(currentTask.files || [])),
        Number(currentTask.total_images || currentTask.files.length || 0),
        Number(currentTask.successful_images || 0),
        Number(currentTask.failed_images || 0),
        Number(currentTask.total_rows || 0)
    );
}

function updateSelectionControls() {
    const files = currentTask && Array.isArray(currentTask.files) ? currentTask.files : [];
    const canSelect = canEditSelection();
    const selectableCount = files.length;
    const selectedCount = canSelect
        ? selectedImageKeys.size
        : files.filter(function(fileResult) {
            return isWordFileSelected(fileResult);
        }).length;

    if (selectAllWordImages) {
        selectAllWordImages.disabled = !canSelect || !selectableCount;
        selectAllWordImages.checked = Boolean(selectableCount && selectedCount === selectableCount);
        selectAllWordImages.indeterminate = Boolean(selectedCount > 0 && selectedCount < selectableCount);
    }

    wordStatusBody.querySelectorAll('.word-file-checkbox').forEach(function(checkbox) {
        checkbox.disabled = !canSelect;
    });

    if (startSelectedBtn) {
        const isStarting = isProcessingTask && processingMode === 'start';
        startSelectedBtn.disabled = isProcessingTask || !canSelect || selectedCount === 0;
        startSelectedBtn.innerHTML = isStarting
            ? '<i class="fas fa-spinner fa-spin"></i> 检测中...'
            : `<i class="fas fa-play"></i> 开始检测${canSelect && selectedCount ? `（${selectedCount}）` : ''}`;
    }
}

function getTaskElapsedTime(task) {
    if (task && ['queued', 'running', 'retrying'].includes(task.status) && processingStartTime) {
        return `${((Date.now() - processingStartTime) / 1000).toFixed(1)}s`;
    }

    const resultTime = task.results && task.results.stats ? task.results.stats.processing_time : null;
    if (resultTime) {
        return `${resultTime}s`;
    }

    if (!processingStartTime) {
        return '0s';
    }

    return `${((Date.now() - processingStartTime) / 1000).toFixed(1)}s`;
}

function renderActiveTab() {
    wordFlowchartTabs.querySelectorAll('[data-word-tab]').forEach(function(button) {
        button.classList.toggle('active', button.getAttribute('data-word-tab') === activeTab);
    });

    document.querySelectorAll('[data-word-pane]').forEach(function(pane) {
        pane.classList.toggle('active', pane.getAttribute('data-word-pane') === activeTab);
    });
}

function setProcessingState(isProcessing, mode) {
    isProcessingTask = isProcessing;
    processingMode = isProcessing ? (mode || '') : '';
    const isRetrying = mode === 'retry';
    const isExtracting = mode === 'extract';
    const isStarting = mode === 'start';
    processWordBtn.disabled = isProcessing;
    processWordBtn.innerHTML = isProcessing
        ? `<i class="fas fa-spinner fa-spin"></i> ${isExtracting ? '提取中...' : '处理中...'}`
        : '<i class="fas fa-images"></i> 提取图片';

    if (retryFailedBtn) {
        retryFailedBtn.innerHTML = isRetrying
            ? '<i class="fas fa-spinner fa-spin"></i> 重试中...'
            : '<i class="fas fa-redo-alt"></i> 重试失败';
    }

    if (wordLoadingIndicator) {
        wordLoadingIndicator.classList.toggle('active', isProcessing);
        const loadingText = wordLoadingIndicator.querySelector('.loading-text');
        if (loadingText) {
            loadingText.textContent = isRetrying
                ? '正在重新调用模型识别失败图片...'
                : isStarting
                    ? '正在调用模型识别已勾选图片...'
                    : '正在提取Word中的流程图图片...';
        }
    }

    if (isProcessing) {
        exportWordExcelBtn.disabled = true;
        exportWordJsonBtn.disabled = true;
    }

    updateRetryButton(currentTask);
    updateSelectionControls();
}

function updateDownloadButtons(task) {
    const isCompleted = task && task.status === 'completed';
    const hasBatch = Boolean((task && task.batch_id) || currentBatchId);
    exportWordExcelBtn.disabled = !(isCompleted && hasBatch);
    exportWordJsonBtn.disabled = !(isCompleted && hasBatch);
    updateRetryButton(task);
    updateSelectionControls();
}

function updateRetryButton(task) {
    if (!retryFailedBtn) {
        return;
    }

    const canRetry = Boolean(
        task
        && currentTaskId
        && ['completed', 'failed'].includes(task.status)
        && Number(task.failed_images || 0) > 0
    );
    retryFailedBtn.disabled = isProcessingTask || !canRetry;
}

function downloadResult(format) {
    if (!currentBatchId) {
        showError('暂无可导出的识别结果');
        return;
    }

    window.open(`${API_BASE_URL}/api/flowchart/word/download/${format}/${encodeURIComponent(currentBatchId)}`, '_blank');
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

function resetTaskView() {
    currentTaskId = null;
    currentBatchId = null;
    currentTask = null;
    activeTab = 'status';
    processingStartTime = null;
    processingMode = '';
    isProcessingTask = false;
    selectedImageKeys = new Set();
    selectionTaskId = null;
    selectionFileSignature = '';
    hasEditedSelection = false;
    statusTabCount.textContent = '0';
    resultTabCount.textContent = '0';
    wordStatusBody.innerHTML = `
        <tr>
            <td colspan="7" class="empty-message">暂无处理任务</td>
        </tr>
    `;
    wordResultsBody.innerHTML = `
        <tr>
            <td colspan="8" class="empty-message">暂无识别结果</td>
        </tr>
    `;
    wordResultMeta.innerHTML = '<span><i class="fas fa-info-circle"></i> 提取图片后可勾选需要识别的流程图</span>';
    if (wordStatsCard) {
        wordStatsCard.style.display = 'none';
    }
    totalImages.textContent = '0';
    processedImages.textContent = '0';
    successImages.textContent = '0';
    failedImages.textContent = '0';
    wordRowCount.textContent = '0';
    wordProcessingTime.textContent = '0s';
    exportWordExcelBtn.disabled = true;
    exportWordJsonBtn.disabled = true;
    retryFailedBtn.disabled = true;
    processWordBtn.disabled = false;
    processWordBtn.innerHTML = '<i class="fas fa-images"></i> 提取图片';
    if (wordLoadingIndicator) {
        wordLoadingIndicator.classList.remove('active');
    }
    updateSelectionControls();
    renderActiveTab();
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
