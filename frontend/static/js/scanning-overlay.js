/**
 * 扫描动画遮罩工具
 */

function showScanningOverlay(container) {
    const element = typeof container === 'string' ? document.querySelector(container) : container;
    if (!element) return;

    element.style.position = 'relative';

    let overlay = element.querySelector('.scanning-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'scanning-overlay';
        overlay.innerHTML = `
            <div class="scanning-content">
                <div class="scanning-animation">
                    <div class="scan-line"></div>
                </div>
                <div class="scanning-text">
                    正在识别中<span class="scanning-dots"></span>
                </div>
            </div>
        `;
        element.appendChild(overlay);
    }

    overlay.classList.add('active');
}

function hideScanningOverlay(container) {
    const element = typeof container === 'string' ? document.querySelector(container) : container;
    if (!element) return;

    const overlay = element.querySelector('.scanning-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}
