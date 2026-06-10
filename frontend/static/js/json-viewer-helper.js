/**
 * JSON 可视化辅助函数
 * 统一处理所有页面的 JSON 树形展示
 */

function displayJSON(elementId, data) {
    const element = document.getElementById(elementId);
    if (!element) return;

    // 清空元素
    element.innerHTML = '';

    // 如果是字符串，尝试解析
    let jsonData = data;
    if (typeof data === 'string') {
        try {
            jsonData = JSON.parse(data);
        } catch (e) {
            element.textContent = data;
            return;
        }
    }

    // 使用 jquery.json-viewer 插件
    if (typeof $ !== 'undefined' && $.fn.jsonViewer) {
        $(element).jsonViewer(jsonData, {collapsed: false, withQuotes: true});
    } else {
        // 降级：使用格式化的 JSON 字符串
        element.textContent = JSON.stringify(jsonData, null, 2);
    }
}

function clearJSON(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '';
    }
}
