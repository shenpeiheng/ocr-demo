// Whisper 语音转字幕 - 前端交互脚本

let currentTaskId = null;
let uploadedFile = null;
let taskPollingInterval = null;
let taskCache = {}; // 缓存任务数据

document.addEventListener('DOMContentLoaded', function() {
    checkSystemStatus();
    initUploadArea();
    initProcessButton();
    loadHistoryTasks(); // 加载历史任务
});

async function checkSystemStatus() {
    try {
        const response = await fetch('/api/whisper/status');
        const data = await response.json();
        if (data.success) {
            displaySystemStatus(data.status);
        }
    } catch (error) {
        console.error('获取系统状态失败:', error);
    }
}

function displaySystemStatus(status) {
    const statusDiv = document.getElementById('systemStatus');
    const isReady = status.ready;
    let html = `<div class="status-badge ${isReady ? 'ready' : 'not-ready'}">`;
    if (isReady) {
        html += `<i class="fas fa-check-circle"></i><span>系统就绪</span>`;
    } else {
        html += `<i class="fas fa-exclamation-triangle"></i><span>系统未就绪</span>`;
        if (!status.whisper_available) html += `<span style="margin-left: 10px; font-size: 12px;">Whisper 未安装</span>`;
        if (!status.ffmpeg_available) html += `<span style="margin-left: 10px; font-size: 12px;">FFmpeg 未安装</span>`;
    }
    html += `</div>`;
    statusDiv.innerHTML = html;
}

function initUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    uploadArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragging');
    });
    uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragging'));
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragging');
        if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
    });
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) handleFile(file);
}

async function handleFile(file) {
    uploadedFile = file;
    const uploadArea = document.getElementById('uploadArea');

    // 显示上传进度
    uploadArea.innerHTML = `
        <div class="upload-icon"><i class="fas fa-spinner fa-spin"></i></div>
        <div class="upload-text">正在上传: ${file.name}</div>
        <div class="upload-progress">
            <div class="upload-progress-bar" style="width: 0%"></div>
        </div>
        <div class="upload-hint">0%</div>
    `;

    // 上传文件
    await uploadFileWithProgress(file);
}

async function uploadFileWithProgress(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const xhr = new XMLHttpRequest();

        // 上传进度
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                document.querySelector('.upload-progress-bar').style.width = percent + '%';
                document.querySelector('.upload-hint').textContent = percent + '%';
            }
        });

        // 上传完成
        xhr.addEventListener('load', async () => {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                if (response.success) {
                    currentTaskId = response.task_id;

                    // 显示上传成功，等待用户点击按钮
                    const uploadArea = document.getElementById('uploadArea');
                    uploadArea.innerHTML = `
                        <div class="upload-icon"><i class="fas fa-check-circle" style="color: #67C23A;"></i></div>
                        <div class="upload-text">${file.name}</div>
                        <div class="upload-hint">上传完成，点击"开始处理"按钮</div>
                    `;

                    // 启用处理按钮
                    document.getElementById('btnProcess').disabled = false;
                } else {
                    showUploadError(response.error || '上传失败');
                }
            } else {
                showUploadError('上传失败: ' + xhr.status);
            }
        });

        xhr.addEventListener('error', () => {
            showUploadError('网络错误，上传失败');
        });

        xhr.open('POST', '/api/whisper/upload');
        xhr.send(formData);

    } catch (error) {
        showUploadError('上传失败: ' + error.message);
    }
}

function showUploadError(message) {
    const uploadArea = document.getElementById('uploadArea');
    uploadArea.innerHTML = `
        <div class="upload-icon"><i class="fas fa-exclamation-circle" style="color: #F56C6C;"></i></div>
        <div class="upload-text" style="color: #F56C6C;">${message}</div>
        <div class="upload-hint">请重新选择文件</div>
    `;
}

async function startProcessing() {
    const model = document.getElementById('modelSelect').value;
    const language = document.getElementById('languageSelect').value;

    try {
        const response = await fetch('/api/whisper/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: currentTaskId,
                model: model,
                language: language
            })
        });

        const data = await response.json();
        if (data.success) {
            startPolling(currentTaskId);
        }
    } catch (error) {
        console.error('处理失败:', error);
    }
}

async function uploadFile(file) {
    // 已被 uploadFileWithProgress 替代，保留以防其他地方调用
}

function initProcessButton() {
    document.getElementById('btnProcess').addEventListener('click', async () => {
        if (!currentTaskId) {
            return;
        }

        const model = document.getElementById('modelSelect').value;
        const language = document.getElementById('languageSelect').value;

        try {
            const response = await fetch('/api/whisper/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    task_id: currentTaskId,
                    model: model,
                    language: language
                })
            });

            const data = await response.json();
            if (data.success) {
                document.getElementById('btnProcess').disabled = true;
                startTaskPolling(currentTaskId);
            }
        } catch (error) {
            console.error('处理失败:', error);
        }
    });
}

async function startProcessingOld() {
    // 旧版本，已被新的 startProcessing 替代
    if (!currentTaskId) {
        alert('请先上传文件');
        return;
    }
    const language = document.getElementById('languageSelect').value;
    const model = document.getElementById('modelSelect').value;
    try {
        const response = await fetch('/api/whisper/process', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({task_id: currentTaskId, language: language, model: model})
        });
        const data = await response.json();
        if (data.success) {
            resetUploadArea();
            startTaskPolling(currentTaskId);
            currentTaskId = null;
        } else {
            alert('处理失败: ' + data.error);
        }
    } catch (error) {
        console.error('处理失败:', error);
        alert('处理失败: ' + error.message);
    }
}

function resetUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    uploadArea.innerHTML = `
        <input type="file" id="fileInput" accept="video/*,audio/*" style="display: none;">
        <div class="upload-icon"><i class="fas fa-cloud-upload-alt"></i></div>
        <div class="upload-text">点击或拖拽文件到此处上传</div>
        <div class="upload-hint">支持 MP4、AVI、MOV、MP3、WAV 等格式</div>
    `;

    // 重新绑定事件
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', handleFileSelect);

    document.getElementById('btnProcess').disabled = true;
    uploadedFile = null;
}

function startTaskPolling(taskId) {
    if (taskPollingInterval) clearInterval(taskPollingInterval);
    checkTaskStatus(taskId);
    taskPollingInterval = setInterval(() => checkTaskStatus(taskId), 2000);
}

async function checkTaskStatus(taskId) {
    try {
        const response = await fetch(`/api/whisper/task/${taskId}`);
        const data = await response.json();
        if (data.success) {
            updateTaskDisplay(data.task);
            if (data.task.status === 'completed' || data.task.status === 'failed') {
                clearInterval(taskPollingInterval);
                taskPollingInterval = null;
            }
        }
    } catch (error) {
        console.error('获取任务状态失败:', error);
    }
}

function updateTaskDisplay(task) {
    const taskList = document.getElementById('taskList');
    const emptyState = taskList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    // 缓存任务数据
    taskCache[task.task_id] = task;

    let taskItem = document.getElementById(`task-${task.task_id}`);
    if (!taskItem) {
        taskItem = document.createElement('div');
        taskItem.id = `task-${task.task_id}`;
        taskItem.className = 'task-card';
        taskItem.dataset.filename = task.filename;
        taskList.insertBefore(taskItem, taskList.firstChild);
    }

    // 更新 dataset
    if (task.detected_language) taskItem.dataset.language = task.detected_language;
    if (task.segment_count) taskItem.dataset.segments = task.segment_count;

    let html = `
        <div class="task-header">
            <div class="task-filename">${task.original_filename}</div>
            <div class="task-status ${task.status}">${getStatusText(task.status)}</div>
        </div>
    `;

    if (task.status === 'processing') {
        html += `
            <div class="task-progress">
                <div class="task-progress-bar" style="width: ${task.progress}%"></div>
            </div>
            <div class="task-message">${task.message}</div>
        `;
    } else {
        html += `<div class="task-message">${task.message}</div>`;
    }

    if (task.status === 'completed') {
        html += `
            <div class="task-actions">
                <button class="btn-download" onclick="previewVideo('${task.task_id}')">
                    <i class="fas fa-play"></i> 预览
                </button>
                <button class="btn-download" onclick="openAiSummary('${task.task_id}')">
                    <i class="fas fa-robot"></i> AI纪要
                </button>
                <button class="btn-download" onclick="downloadFile('${task.task_id}', 'srt')">
                    <i class="fas fa-download"></i> SRT
                </button>
                <button class="btn-download" onclick="downloadFile('${task.task_id}', 'txt')">
                    <i class="fas fa-download"></i> TXT
                </button>
                <button class="btn-download" onclick="downloadFile('${task.task_id}', 'json')">
                    <i class="fas fa-download"></i> JSON
                </button>
            </div>
        `;
    }

    taskItem.innerHTML = html;
}

function downloadFile(taskId, fileType) {
    window.open(`/api/whisper/download/${taskId}/${fileType}`, '_blank');
}

function previewVideo(taskId) {
    const task = getCurrentTask(taskId);
    if (!task) {
        alert('任务不存在');
        return;
    }

    // 显示弹窗
    const modal = document.getElementById('videoPreviewModal');
    const videoPlayer = document.getElementById('videoPlayer');

    // 清空现有的 track
    while (videoPlayer.firstChild && videoPlayer.firstChild.tagName === 'TRACK') {
        videoPlayer.removeChild(videoPlayer.firstChild);
    }

    // 设置视频源
    videoPlayer.src = `/uploads/${task.filename}`;

    // 动态创建新的字幕 track，使用 VTT 格式
    const track = document.createElement('track');
    track.kind = 'subtitles';
    track.label = '中文';
    track.srclang = 'zh';
    track.src = `/api/whisper/download/${taskId}/vtt`;
    track.default = true;

    // 插入到 video 元素
    videoPlayer.appendChild(track);

    // 显示弹窗
    modal.classList.add('active');

    // 加载视频并启用字幕
    videoPlayer.load();

    // 确保字幕轨道加载后自动显示
    track.addEventListener('load', function() {
        track.mode = 'showing';
    });

    videoPlayer.addEventListener('loadedmetadata', function() {
        const tracks = videoPlayer.textTracks;
        if (tracks.length > 0) {
            tracks[0].mode = 'showing';
        }
    }, { once: true });
}

function closeVideoPreview() {
    const modal = document.getElementById('videoPreviewModal');
    const videoPlayer = document.getElementById('videoPlayer');

    // 暂停并重置视频
    videoPlayer.pause();
    videoPlayer.currentTime = 0;
    videoPlayer.src = '';

    // 隐藏弹窗
    modal.classList.remove('active');
}

let currentSummaryTaskId = null;

async function openAiSummary(taskId) {
    currentSummaryTaskId = taskId;
    const task = getCurrentTask(taskId);
    if (!task) {
        console.error('任务不存在');
        return;
    }

    const modal = document.getElementById('aiSummaryModal');
    const transcriptContent = document.getElementById('transcriptContent');
    const summaryContent = document.getElementById('summaryContent');

    // 重置内容
    summaryContent.innerHTML = `
        <div class="empty-placeholder">
            <i class="fas fa-robot"></i>
            <p>点击"生成纪要"按钮开始分析</p>
        </div>
    `;
    document.getElementById('btnExportSummary').disabled = true;

    // 加载转录文本
    transcriptContent.innerHTML = '<div class="loading-placeholder">加载中...</div>';

    try {
        const response = await fetch(`/api/whisper/download/${taskId}/txt`);
        const text = await response.text();
        transcriptContent.innerHTML = `<pre style="white-space: pre-wrap; margin: 0; font-family: inherit;">${text}</pre>`;
    } catch (error) {
        transcriptContent.innerHTML = '<div class="empty-placeholder"><p>加载失败</p></div>';
    }

    modal.classList.add('active');
}

function closeAiSummary() {
    const modal = document.getElementById('aiSummaryModal');
    modal.classList.remove('active');
    currentSummaryTaskId = null;
}

async function generateAiSummary() {
    const summaryContent = document.getElementById('summaryContent');
    const btnGenerate = document.getElementById('btnGenerateSummary');
    const aiModel = document.getElementById('aiModelSelect').value;

    btnGenerate.disabled = true;
    btnGenerate.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';

    summaryContent.innerHTML = `
        <div class="loading-placeholder">
            <i class="fas fa-spinner fa-spin"></i>
            <p>AI 正在分析转录内容，请稍候...</p>
        </div>
    `;

    try {
        const response = await fetch('/api/whisper/ai-summary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: currentSummaryTaskId,
                model: aiModel
            })
        });

        const data = await response.json();

        if (data.success) {
            summaryContent.innerHTML = `<div style="white-space: pre-wrap;">${data.summary}</div>`;
            document.getElementById('btnExportSummary').disabled = false;
        } else {
            summaryContent.innerHTML = `
                <div class="empty-placeholder">
                    <i class="fas fa-exclamation-circle" style="color: #F56C6C;"></i>
                    <p style="color: #F56C6C;">生成失败: ${data.error || '未知错误'}</p>
                </div>
            `;
        }
    } catch (error) {
        summaryContent.innerHTML = `
            <div class="empty-placeholder">
                <i class="fas fa-exclamation-circle" style="color: #F56C6C;"></i>
                <p style="color: #F56C6C;">网络错误: ${error.message}</p>
            </div>
        `;
    } finally {
        btnGenerate.disabled = false;
        btnGenerate.innerHTML = '<i class="fas fa-magic"></i> 生成纪要';
    }
}

function exportSummary() {
    const summaryContent = document.getElementById('summaryContent');
    const text = summaryContent.innerText;

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `AI纪要_${currentSummaryTaskId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

function toggleSubtitle() {
    const videoPlayer = document.getElementById('videoPlayer');
    const tracks = videoPlayer.textTracks;
    const button = event.target.closest('.subtitle-toggle');

    if (tracks.length > 0) {
        const track = tracks[0];

        // 使用 disabled 而不是 hidden 来完全禁用字幕
        if (track.mode === 'showing') {
            track.mode = 'disabled';
            button.innerHTML = '<i class="fas fa-closed-captioning"></i> 显示字幕';
        } else {
            track.mode = 'showing';
            button.innerHTML = '<i class="fas fa-closed-captioning"></i> 隐藏字幕';
        }

        console.log('字幕状态:', track.mode);
    } else {
        alert('未找到字幕轨道');
    }
}

function getCurrentTask(taskId) {
    // 从缓存中获取任务数据
    return taskCache[taskId] || null;
}

function getStatusText(status) {
    const statusMap = {
        'uploaded': '已上传',
        'processing': '处理中',
        'completed': '已完成',
        'failed': '失败'
    };
    return statusMap[status] || status;
}

async function loadHistoryTasks() {
    try {
        const response = await fetch('/api/whisper/history');
        const data = await response.json();

        if (data.success && data.tasks && data.tasks.length > 0) {
            const taskList = document.getElementById('taskList');
            const emptyState = taskList.querySelector('.empty-state');
            if (emptyState) emptyState.remove();

            // 缓存所有历史任务
            data.tasks.forEach(task => {
                taskCache[task.task_id] = task;
                updateTaskDisplay(task);
            });
        }
    } catch (error) {
        console.error('加载历史任务失败:', error);
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(2) + ' MB';
    return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB';
}
