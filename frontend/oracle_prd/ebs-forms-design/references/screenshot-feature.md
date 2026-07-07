# 功能截图与批量截图

通过全局工具栏提供截图、批量截图、生成功能文档功能。

## 前置条件

在 `<head>` 中添加 html2canvas；Markdown 格式导出需额外添加 JSZip：

```html
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<!-- Markdown 格式（ZIP）需要：-->
<script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>
```

## 方式：全局工具栏按钮（唯一推荐方式）

截取当前正在查看的整个功能面板（含标题栏、内容区、状态栏），不跳转、不弹窗，直接触发下载。
按钮放在全局工具栏。

**不要**做成导航栏菜单页面——用户明确拒绝此方式。截图功能应始终在全局工具栏上直接操作。

```html
<button class="tb-btn" onclick="captureCurrentScreenshot()">📸 功能截图</button>
<button class="tb-btn" onclick="batchScreenshot()">📚 批量截图</button>
<button class="tb-btn" onclick="generateDesignDoc()">📝 生成功能文档</button>
```

## 单次截图

截取整个 `.view-panel`（标题栏 + 内容区 + 状态栏），不含导航栏和四周空白。

```javascript
function captureCurrentScreenshot() {
  var target = document.querySelector('.view-panel');
  if (!target) { showMsg('未找到功能面板'); return; }
  var title = document.getElementById('viewTitleText') ? document.getElementById('viewTitleText').textContent.trim() : '界面';
  var now = new Date();
  var ds = now.getFullYear() + pad(now.getMonth()+1) + pad(now.getDate());
  var ts = pad(now.getHours()) + pad(now.getMinutes()) + pad(now.getSeconds());
  var fn = '原型_' + title + '_' + ds + '_' + ts + '.png';
  showMsg('正在截图...');
  html2canvas(target, {
    scale: 2, useCORS: true,
    backgroundColor: '#F0F0F0',
    logging: false, allowTaint: true,
    width: target.scrollWidth, height: target.scrollHeight
  }).then(function(canvas) {
    var link = document.createElement('a');
    link.download = fn;
    link.href = canvas.toDataURL('image/png');
    link.click();
    showMsg('✅ 截图已保存: ' + fn);
  }).catch(function(err) { showMsg('截图失败'); });
}

function pad(n) { return ('0' + n).slice(-2); }
```

## 批量截图 — 完整实现

### 动态 tab 列表（代替手动填写）

```javascript
var batchTabList = [];
var tabs = document.querySelectorAll('.tab-pane');
tabs.forEach(function(t) {
  if (t.id) batchTabList.push({ tabId: t.id, title: t.id });
});
```

### 批量截图入口

```javascript
var docCaptureRunning = false;

function batchScreenshot() {
  if (docCaptureRunning) { showMsg('进行中...'); return; }
  captureTabsAndBuild('batch');
}
```

### 通用遍历引擎（批量/文档共用）

`captureTabsAndBuild(format)` 是批量截图和生成功能文档的核心遍历引擎。它按顺序遍历所有 tab-pane，通过导航树自动点击切换，逐个截图，完成后根据 `format` 调用对应的构建函数。

```javascript
function captureTabsAndBuild(format) {
  docCaptureRunning = true;
  var results = [];
  var total = batchTabList.length;
  var idx = 0;

  function next() {
    if (idx >= total) {
      // 全部截图完成，根据格式调用构建函数
      if (format === 'batch') {
        buildBatchDoc(results);
      } else if (format === 'md') {
        buildMarkdownDoc(results);
      } else {
        buildWordDoc(results);
      }
      docCaptureRunning = false;
      return;
    }

    var item = batchTabList[idx];
    // 通过导航树节点自动切换 tab
    var navItem = document.querySelector(
      '.tree-leaf[onclick*="' + item.tabId + '"], ' +
      '.tree-root-item[onclick*="' + item.tabId + '"]'
    );
    if (navItem) navItem.click();

    setTimeout(function() {
      var panel = document.querySelector('.view-panel');
      if (!panel) { idx++; next(); return; }
      showMsg('截取 (' + (idx+1) + '/' + total + '): ' + item.title);

      html2canvas(panel, {
        scale: 2, useCORS: true,
        backgroundColor: '#F0F0F0',
        logging: false, allowTaint: true,
        width: panel.scrollWidth, height: panel.scrollHeight
      }).then(function(canvas) {
        results.push({
          title: item.title,
          desc: item.title + '功能界面',
          dataUrl: canvas.toDataURL('image/png')
        });
        idx++;
        next();
      }).catch(function() { idx++; next(); });
    }, 500); // 500ms 等待 tab 切换动画/渲染完成
  }

  next();
}
```

### 构建批量截图 Word 文档

```javascript
function buildBatchDoc(results) {
  var now = new Date();
  var ds = now.getFullYear() + pad(now.getMonth()+1) + pad(now.getDate());
  var html = '<html><head><meta charset="UTF-8"><title>批量截图</title></head><body style="font-family:宋体;">';
  results.forEach(function(r) {
    html += '<h2>' + r.title + '</h2>';
    if (r.dataUrl) html += '<div><img src="' + r.dataUrl + '" style="width:650px;"></div>';
    html += '<br style="page-break-after:always;">';
  });
  html += '</body></html>';
  var blob = new Blob([html], { type: 'application/msword;charset=utf-8' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = '批量截图_' + ds + '.docx';
  link.click();
  showMsg('✅ 批量截图完成');
}
```

## 一键导出功能设计文档

结合截图 + 功能说明，一键生成功能设计文档。

### 交互方式

点击"📝 生成功能文档"按钮 → 弹出格式选择弹窗（.docx / .md）→ 用户选格式 → 自动遍历截图 → 生成文档。

### 格式选择弹窗

```javascript
function generateDesignDoc() {
  showModal('modalGeneric');
  document.getElementById('modalGenTitle').textContent = '📝 选择导出格式';
  document.getElementById('modalGenBody').innerHTML =
    '<div style="font-size:10pt;line-height:1.8;padding:10px 0;">' +
    '<p>请选择功能设计文档的导出格式：</p>' +
    '<div style="display:flex;gap:12px;margin-top:16px;justify-content:center;">' +
    '<button class="btn btn-primary" onclick="closeModal(\'modalGeneric\');captureTabsAndBuild(\'doc\')" ' +
    'style="padding:8px 24px;min-height:40px;font-size:11pt;">📄 Word 文档 (.docx)</button>' +
    '<button class="btn" onclick="closeModal(\'modalGeneric\');captureTabsAndBuild(\'md\')" ' +
    'style="padding:8px 24px;min-height:40px;font-size:11pt;">📝 Markdown 文档 (.md)</button>' +
    '</div>' +
    '<p style="margin-top:12px;color:#666;text-align:center;">两种格式均包含全部功能界面的截图和功能说明</p>' +
    '</div>';
}
```

### Markdown 文档构建（ZIP 输出）

```javascript
function buildMarkdownDoc(results) {
  var now = new Date();
  var ds = now.getFullYear() + pad(now.getMonth()+1) + pad(now.getDate());
  var folderName = '功能设计文档_' + ds;

  var md = '# 功能设计文档\n\n**日期：** ' + now.toLocaleDateString('zh-CN') + '\n\n---\n\n';
  results.forEach(function(r, i) {
    md += '### ' + (i+1) + '. ' + r.title + '\n\n' + r.desc + '\n\n';
    if (r.dataUrl) md += '![image](images/' + r.title + '.png)\n\n';
  });

  var zip = new JSZip();
  zip.file(folderName + '.md', md);
  var imgFolder = zip.folder('images');
  results.forEach(function(r) {
    if (r.dataUrl) {
      var b64 = r.dataUrl.split(',')[1];
      imgFolder.file(r.title + '.png', b64, { base64: true });
    }
  });
  zip.generateAsync({ type: 'blob' }).then(function(blob) {
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = folderName + '.zip';
    link.click();
    showMsg('✅ Markdown文档已生成');
  });
}
```

### Word 文档构建（Word兼容HTML，内嵌base64图片）

```javascript
function buildWordDoc(results) {
  var now = new Date();
  var ds = now.getFullYear() + pad(now.getMonth()+1) + pad(now.getDate());
  var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" ' +
    'xmlns:w="urn:schemas-microsoft-com:office:word" ' +
    'xmlns="http://www.w3.org/TR/REC-html40">' +
    '<head><meta charset="UTF-8"><title>功能设计文档</title>' +
    '<style>' +
    'body{font-family:宋体;font-size:11pt;margin:50px;}' +
    'h1{text-align:center;font-size:20pt;color:#2D82C3;}' +
    'h2{font-size:14pt;color:#2D6EB0;margin-top:25px;}' +
    'table{width:100%;border-collapse:collapse;}' +
    'th,td{border:1px solid #A0A0A0;padding:4px 8px;}' +
    'img{width:650px;}' +
    '.page-break{page-break-after:always;}' +
    '</style></head><body>';
  html += '<h1>功能设计文档</h1>';
  html += '<p style="text-align:center;">日期: ' + now.toLocaleDateString('zh-CN') + '</p>';
  results.forEach(function(r, i) {
    html += '<h3>' + (i+1) + '. ' + r.title + '</h3>';
    if (r.dataUrl) html += '<div><img src="' + r.dataUrl + '"></div>';
    html += '<div style="background:#F8FAFC;border:1px solid #B0C4DE;padding:10px;margin:8px 0;">' +
      '<b>功能说明：</b><br>' + r.desc + '</div>';
    if (i < results.length - 1) html += '<br class="page-break">';
  });
  html += '</body></html>';
  var blob = new Blob([html], { type: 'application/msword;charset=utf-8' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = '功能设计文档_' + ds + '.docx';
  link.click();
  showMsg('✅ Word文档已生成');
}
```

## 图标坑点

截图时，使用 `url('https://www.oracle.com/favicon.ico')` 的图标会因为 CORS 限制无法被 html2canvas 加载，导致截图中图标空白。

**解决方案**：使用 base64 内嵌的 Oracle favicon（skill 中 `assets/orcale_favicon.png`）。

```css
.view-title-icon {
  width: 20px; height: 20px;
  background: url('data:image/png;base64,...') no-repeat center;
  background-size: contain;
  flex-shrink: 0;
}
```

```html
<span class="view-title-icon"></span>
```

其他 `background: url(...)` 图标也要检查是否可能被 CORS 阻塞。

## 关键要点

- **截取目标**：`.view-panel`（完整功能面板，含标题栏+内容区+状态栏），不含导航栏
- **截图范围**：`target.scrollWidth x target.scrollHeight`
- **背景色**：`#F0F0F0`（窗口容器底色）
- **倍率**：`scale: 2` 高清输出
- **文件名**：单次 `{原型名}_{功能名称}_{YYYYMMDD}_{HHMMSS}.png`，批量 `{原型名}_批量截图_{YYYYMMDD}.docx`
- **截图按钮始终在全局工具栏**，不放在导航栏或功能界面中
- **不跳转页面** — 直接截取当前正在查看的界面，无需切换到截图页面
- **批量截图/功能文档** 使用 `.docx`（Word兼容HTML），不依赖 docx.js 外部库
- **功能文档 Markdown 格式** 输出为 ZIP（`.md` + `images/` 目录），需引入 JSZip；避免 base64 内嵌图片导致文件过大
- **图标** 使用 base64 内嵌的 Oracle favicon，避免外部 URL 因 CORS 无法截取
- **输入框文字定位** html2canvas 渲染原生 `<input>` 元素时可能出现文字底部对齐或显示不全。给输入框加 `line-height: 20px; vertical-align: middle; box-sizing: border-box;` 确保文字垂直居中
- **状态栏截图干净** 状态栏左侧（`.status-left`）HTML 中直接设为空字符串，`showMsg()` 不写入 status-left。消息反馈仅通过底部 toast 浮层（2秒自动消失）。截图时无需临时清空操作。
