# EBS 3D 雕刻/浮雕表格边框（最终版）

Oracle EBS Forms 风格表格——每个单元格独立 3D 浮雕边框，底色贴近画布。

## 设计原则

| 原则 | 说明 |
|------|------|
| **每格独立 3D** | `border-collapse: separate` 让每个单元格独立显示 inset/outset 边框 |
| **底色融画布** | td 默认底色 `#EAEEF2`（与 view-content 画布一致），可编辑格用 `.editable` 类变白底 |
| **颜色柔和** | 边框颜色贴近画布，不突兀。高光边 ≈ 画布+2阶，阴影边 ≈ 画布-3阶 |
| **浮雕对比** | 上/左亮（高光）、右/下暗（阴影），模拟左上光源 |

## 色值与画布参考

```
view-content 背景 (画布): #EAEEF2
------------------------------
td 高光边 (上/左):     #ECEEF0 (+2)
td 阴影边 (右/下):     #CDD1D6 (-3)
th outset 边框:        #D6DBE2 (-4)
th outset 底边:        #C4CAD2 (-8)
th 渐变 起/止:         #E4E9EF / #D2D8E0
容器 outset 边框:      #DCDFE4 (-6)
```

## 表格容器 (scroll-table)

```css
.scroll-table {
  max-height: 260px; overflow-y: auto; margin-top: 8px;
  border: 2px outset #DCDFE4;
  box-shadow: inset 1px 1px 3px rgba(0,0,0,0.08);
  border-radius: 1px;
}
.scroll-table table {
  width: 100%; font-size: 10pt;
  border-collapse: separate; border-spacing: 0;
}
.scroll-table thead { position: sticky; top: 0; z-index: 1; }
.scroll-table th {
  font-weight: bold; text-align: center; padding: 4px 6px; height: 28px;
  background: linear-gradient(180deg, #E4E9EF 0%, #D2D8E0 100%);
  color: #333; font-size: 9pt;
  border: 1.5px outset #D6DBE2;
  border-bottom: 2px outset #C4CAD2;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}
.scroll-table td {
  padding: 1px 4px; text-align: center; height: 28px; vertical-align: middle;
  background: #EAEEF2;
  border-color: #ECEEF0 #CDD1D6 #CDD1D6 #ECEEF0;
  border-style: inset;
  border-width: 1.5px;
}
.scroll-table td.editable {
  background: #FFFFFF;
}
.scroll-table tr:hover td { background: #E6F2FF; }
.scroll-table tr.selected td { background: #D6E8FF; }
.scroll-table td.num { text-align: right; padding-right: 8px; }
.scroll-table td.left { text-align: left; }
```

## 内联数据表 (data-table)

用于非滚动区的独立信息表格（总览页、表单页等），同样 3D 浮雕风格：

```css
.data-table {
  width: 100%; border-collapse: collapse; font-size: 10pt;
}
.data-table th {
  font-weight: bold; text-align: center; padding: 3px 8px; height: 28px;
  background: linear-gradient(180deg, #E4E9EF 0%, #D2D8E0 100%);
  color: #333; font-size: 9pt;
  border: 1.5px outset #D6DBE2;
  border-bottom: 2px outset #C4CAD2;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}
.data-table td {
  padding: 2px 8px; height: 28px; vertical-align: middle;
  background: #EAEEF2;
  border-color: #ECEEF0 #CDD1D6 #CDD1D6 #ECEEF0;
  border-style: inset;
  border-width: 1.5px;
}
.data-table td.editable {
  background: #FFFFFF;
}
.data-table tr:hover td { background: #E6F2FF; }
.data-table td.num { text-align: right; }
.data-table td.left { text-align: left; }
```

## 原理说明

- **浮雕雕刻效果**：上/左边框亮色（`#ECEEF0`，光源从左上照射），右/下边框深色（`#CDD1D6`，阴影凹陷）。`border-style: inset` 是实现每格独立 3D 感的关键。
- **表头凸雕**：使用 `outset` 边框 + 渐变背景 + `box-shadow: inset 0 1px 0` 内高光，看起来像凸起的标签。
- **数据格平凹**：`inset` 边框让每个格子看起来略微沉入表面。`border-collapse: separate` 保证每格独立渲染立体边框，不合并。
- **可编辑格**：`td.editable` 变白底，与只读格（画布色）形成视觉区分。
- **容器凹槽**：`border: outset` + `inset box-shadow` 让表格区本身有立体外框。
- **底色融画布**：所有 td 默认 `#EAEEF2`，与 view-content 背景无缝衔接，只有 3D 边框提供视觉分割。
