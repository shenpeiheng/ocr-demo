# 全局工具栏

在导航栏和功能面板上方增加一条横跨全宽的工具栏。**每个原型必需添加此工具栏**，提供截图、批量截图、生成功能文档、缩放、全屏、帮助等全局功能。

## 结构位置

工具栏放在 `.window` 内部、`.main-container` 上方：

```
.window
  .global-toolbar   ← 这里
  .main-container
    .nav-panel  .view-panel
```

## CSS

```css
.global-toolbar {
  display: flex;
  align-items: center;
  background: #E0E4E8;
  border-bottom: 1px solid #A0A0A0;
  padding: 0 12px;
  height: 32px;
  flex-shrink: 0;
  gap: 4px;
  user-select: none;
}
.global-toolbar .tb-label {
  font-size: 9pt;
  color: #555;
  margin-right: 8px;
  font-weight: bold;
}
.global-toolbar .tb-divider {
  width: 1px;
  height: 18px;
  background: #B0B8C0;
  margin: 0 6px;
}
.global-toolbar .tb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 2px 8px;
  height: 26px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  cursor: pointer;
  font-size: 9pt;
  font-family: inherit;
  color: #333;
  white-space: nowrap;
}
.global-toolbar .tb-btn:hover { background: #D2E4F3; border-color: #2D6EB0; }
.global-toolbar .tb-btn:active { background: #C4D8E8; }

/* 折叠/展开按钮 */
.global-toolbar .tb-toggle {
  font-size: 8pt; padding: 2px 6px; min-width: 24px;
  background: #D0D4D8; border-color: #A0A0A0;
}
.global-toolbar .tb-toggle:hover { background: #C0C8D0; }

/* 折叠状态 */
.global-toolbar.collapsed .tb-label,
.global-toolbar.collapsed .tb-btn:not(.tb-toggle),
.global-toolbar.collapsed .tb-divider { display: none; }
.global-toolbar.collapsed { height: 28px; padding: 0 4px; justify-content: flex-end; }
.global-toolbar.collapsed .tb-toggle { background: transparent; border-color: transparent; }
.global-toolbar.collapsed .tb-toggle:hover { background: #D2E4F3; border-color: #2D6EB0; }
```

## HTML 示例

```html
<div class="window">
  <div class="global-toolbar">
    <span class="tb-label">🔧 工具</span>
    <button class="tb-btn" onclick="captureCurrentScreenshot()">📸 功能截图</button>
    <button class="tb-btn" onclick="batchScreenshot()">📚 批量截图</button>
    <button class="tb-btn" onclick="generateDesignDoc()">📝 生成功能文档</button>
    <span class="tb-divider"></span>
    <button class="tb-btn" onclick="zoomPage(1.1)">🔍 放大</button>
    <button class="tb-btn" onclick="zoomPage(0.9)">🔍 缩小</button>
    <button class="tb-btn" onclick="resetZoom()">↺ 重置</button>
    <span class="tb-divider"></span>
    <button class="tb-btn" onclick="toggleFullscreen()">⛶ 全屏</button>
    <button class="tb-btn" onclick="toggleFocus()">🎯 聚焦</button>
    <span class="tb-divider"></span>
    <button class="tb-btn" onclick="showHelp()">❓ 帮助</button>
    <span style="flex:1;"></span>
    <button class="tb-btn tb-toggle" onclick="toggleToolbar()" title="折叠/展开工具栏">▲</button>
  </div>
  <div class="main-container">...</div>
</div>
```

## JavaScript 实现

### 工具栏折叠/展开

```javascript
let toolbarCollapsed = false;
function toggleToolbar() {
  toolbarCollapsed = !toolbarCollapsed;
  document.querySelector('.global-toolbar').classList.toggle('collapsed', toolbarCollapsed);
  const btn = document.querySelector('.tb-toggle');
  btn.textContent = toolbarCollapsed ? '▼' : '▲';
}
```

### 缩放

```javascript
let currentZoom = 1;
function zoomPage(factor) {
  currentZoom = Math.min(Math.max(currentZoom * factor, 0.5), 2);
  document.querySelector('.window').style.transform = `scale(${currentZoom})`;
  document.querySelector('.window').style.transformOrigin = 'top center';
  showMsg(`缩放: ${Math.round(currentZoom * 100)}%`);
}
function resetZoom() {
  currentZoom = 1;
  document.querySelector('.window').style.transform = 'scale(1)';
  document.querySelector('.window').style.transformOrigin = 'top center';
  showMsg('缩放已重置');
}
```

### 全屏

```javascript
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().then(() => showMsg('全屏模式'))
      .catch(() => showMsg('全屏不可用，请通过浏览器菜单操作'));
  } else {
    document.exitFullscreen();
    showMsg('已退出全屏');
  }
}
```

### 帮助

```javascript
function showHelp() {
  showModal('modalGeneric');
  document.getElementById('modalGenTitle').textContent = '❓ 帮助 — 原型名称';
  document.getElementById('modalGenBody').innerHTML = '...';
}
```

### 生成功能文档（弹窗选择格式）

```javascript
function generateDesignDoc() {
  showModal('modalGeneric');
  document.getElementById('modalGenTitle').textContent = '📝 选择导出格式';
  document.getElementById('modalGenBody').innerHTML = `
    <div style="font-size:10pt;line-height:1.8;padding:10px 0;">
      <p>请选择功能设计文档的导出格式：</p>
      <div style="display:flex;gap:12px;margin-top:16px;justify-content:center;">
        <button class="btn btn-primary" onclick="closeModal('modalGeneric');startDocCapture('doc')">
          📄 Word 文档 (.docx)
        </button>
        <button class="btn" onclick="closeModal('modalGeneric');startDocCapture('md')">
          📝 Markdown 文档 (.md)
        </button>
      </div>
      <p style="margin-top:12px;color:#666;text-align:center;">两种格式均包含全部功能界面的截图和功能说明</p>
    </div>`;
}
function startDocCapture(format) {
  // 遍历 docTabList（包含 tabId, title, desc），逐个截图
  // 完成后 format==='md' ? buildMarkdownDoc(results) : buildWordDoc(results)
}
```

详见 `references/screenshot-feature.md` 中的完整实现。

### 聚焦模式

聚焦模式将 `.view-panel` 居中放大弹出，其他区域（导航栏、工具栏、状态栏）虚化隐藏，适合演示场景。

**CSS**：

```css
.focus-overlay {
  display: none; position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.55); z-index: 9998;
}
.focus-overlay.active { display: block; }
body.focus-mode .window { position: relative; z-index: 9999; }
body.focus-mode .view-panel {
  position: fixed; z-index: 10000;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%) scale(1.05);
  width: 90vw; max-width: 1200px; max-height: 90vh;
  margin: 0;
  box-shadow: 0 0 40px rgba(0,0,0,0.5);
  border-color: #2D82C3;
}
body.focus-mode .nav-panel,
body.focus-mode .global-toolbar,
body.focus-mode .view-status-bar { opacity: 0; pointer-events: none; }
body.focus-mode .window { background: transparent; border-color: transparent; box-shadow: none; }
body.focus-mode { padding: 0; background: transparent; }
```

**HTML**（放在 `<body>` 开头、`.window` 上方）：

```html
<div class="focus-overlay" id="focusOverlay"></div>
```

**JavaScript**：

// 聚焦模式（使用全局 click + ESC）
var focusMode = false;
document.addEventListener('click', function(e) {
  // 陷阱1：排除聚焦按钮自身的点击 —— 按钮 onclick 调用 toggleFocus() 后设置 data-focus-exit，
  //        click 冒泡到 document 会立即退出。e.target.closest('.tb-btn') + onclick 含 toggleFocus 则跳过。
  var btn = e.target.closest ? e.target.closest('.tb-btn') : null;
  if (btn && btn.getAttribute('onclick') && btn.getAttribute('onclick').indexOf('toggleFocus') !== -1) return;
  // 陷阱2：点击面板内部不退出，仅点击外部（背景/遮罩）退出
  if (focusMode && e.target.closest && e.target.closest('.view-panel')) return;
  if (document.body.hasAttribute('data-focus-exit') && focusMode) toggleFocus();
});
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && document.body.hasAttribute('data-focus-exit') && focusMode) toggleFocus();
});
function toggleFocus() {
  focusMode = !focusMode;
  document.body.classList.toggle('focus-mode', focusMode);
  document.getElementById('focusOverlay').classList.toggle('active', focusMode);
  showMsg(focusMode ? '🎯 聚焦模式 — 按 ESC 或再次点击按钮退出' : '已退出聚焦模式');
  if (focusMode) document.body.setAttribute('data-focus-exit', '1');
  else document.body.removeAttribute('data-focus-exit');
}
```

## 注意事项

- **聚焦退出** 不要用 overlay.onclick，view-panel 的 z-index 高于 overlay，点击面板区域时事件不会传递到 overlay。必须用全局 document click 事件 + `data-focus-exit` 标记控制
- 缩放使用 CSS `transform: scale()` 变换 `.window` 容器，缩放中心为 `top center`
- 缩放范围限制在 50%~200%
- 全屏使用标准 Fullscreen API，需要用户手势触发（`click` 事件已满足）
- 缩放/全屏/截图操作后通过 `showMsg()` 状态栏反馈
- 帮助弹窗复用通用 `modalGeneric` 模态框
- 截图功能详见 `references/screenshot-feature.md`
- 生成功能文档的截图遍历与批量截图逻辑相同，区别在于生成的是图文混合文档而非纯截图集合
- 生成功能文档的 Word 格式用 `.docx` 扩展名，内容为 Word兼容HTML
