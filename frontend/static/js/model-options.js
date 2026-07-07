(function () {
    async function applyModelOptions() {
        var selects = document.querySelectorAll('select[data-model-options="true"]');
        if (!selects.length) {
            return;
        }

        try {
            var response = await fetch('/api/llm/config');
            var data = await response.json();
            if (!response.ok || !data.success || !data.models || !data.models.length) {
                console.warn('模型配置接口返回异常，保留静态选项');
                return;
            }

            var defaultModel = data.default_model || (data.models[0] && data.models[0].key);

            selects.forEach(function (select) {
                // 保留用户当前已选中的值（如果有的话）
                var currentValue = select.value || select.getAttribute('data-default-model') || defaultModel;

                // 清空并动态生成 option
                select.innerHTML = '';
                data.models.forEach(function (model) {
                    var option = document.createElement('option');
                    option.value = model.key;
                    option.textContent = model.label || model.key;
                    if (model.key === currentValue) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });

                // 确保默认值生效
                if (select.options.length && !select.querySelector('option[selected]')) {
                    select.options[0].selected = true;
                }

                // 触发 change 事件，通知页面模型列表已就绪
                select.dispatchEvent(new Event('change', { bubbles: true }));
            });
        } catch (error) {
            console.error('加载模型选项配置失败:', error);
        }
    }

    document.addEventListener('DOMContentLoaded', applyModelOptions);
})();
