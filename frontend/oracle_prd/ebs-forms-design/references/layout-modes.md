# EBS 原型布局模式

## 模式A — 窗口式（带全局标题栏）

适合 7 个以上功能模块的完整 EBS Forms 模拟。

```css
body {
  background: #D0D0D0;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 30px;
}
.window {
  width: 1300px;
  max-width: 100%;
  background: #E8E8E8;
  border: 1px solid #A0A0A0;
  box-shadow: 4px 4px 12px rgba(0,0,0,0.25);
  display: flex;
  flex-direction: column;
  max-height: 95vh;
  min-height: 500px;
}
.main-container { display: flex; flex: 1; overflow: hidden; }
.title-bar { background: #2D82C3; }
.nav-panel { width: 210px; }
.nav-title { background: #2D6EB0; padding: 6px 10px; }
.view-panel { margin: 6px; }
.view-title-bar { background: #2D82C3; min-height: 28px; }
```

结构：`body > .window > .title-bar + .main-container`

字体：body 12pt，导航栏 14px。

## 模式B — 独立式（无全局标题栏）

```css
body {
  background: #D0D0D0;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 30px;
}
.window {
  width: 1300px;
  max-width: 100%;
  background: #E8E8E8;
  border: 1px solid #A0A0A0;
  box-shadow: 4px 4px 12px rgba(0,0,0,0.25);
  display: flex;
  flex-direction: column;
  max-height: 95vh;
  min-height: 500px;
}
.main-container { display: flex; flex: 1; overflow: hidden; }
.nav-panel { width: 210px; }
.nav-title { background: #2D6EB0; padding: 6px 10px; }
.view-panel { flex: 1; margin: 0 6px; border: 1px solid #A0A0A0; }
.view-title-bar { background: #2D82C3; min-height: 28px; }
```

结构：`body > .window > .main-container > .nav-panel + .view-panel`

关键差异：`view-panel { margin: 0 6px }` 无 margin-top，nav-title 与 view-title-bar 顶部对齐。无全局 title-bar。

## 全局工具栏（可选）

两种模式都可在 `.window` 内、`.main-container` 上方增加工具栏：

```
.window
  .global-toolbar    ← 新增
  .title-bar         ← 仅模式A
  .main-container
```

详见 `references/global-toolbar.md`。

## 通用注意事项

- 两种模式均用 `.window` 包裹，body 居中留白
- 模态框等放在 `.window` 之外

## 按钮交互模式

### C1 描述模式

按钮点击 → 说明弹窗（📌 业务逻辑 + 🖱️ 交互逻辑）。适合需求确认阶段。

### C2 动作模式

按钮直接模拟操作（查询、生成、发送等）。适合演示测试阶段。
