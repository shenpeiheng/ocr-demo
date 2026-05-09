/**
 * 公共布局加载器
 * 
 * 将 header、sidebar、footer 的 HTML 直接内联在此文件中，
 * 避免额外的 HTTP 请求导致的页面闪烁。
 * 自动高亮当前页面在侧边栏中对应的菜单项。
 * 
 * 使用方式：在所有页面中通过 <script src="static/js/layout.js"></script> 引入即可。
 * 页面中需要放置以下占位元素：
 *   <div id="header-placeholder"></div>
 *   <div id="sidebar-placeholder"></div>
 *   <div id="footer-placeholder"></div>
 */

(function() {
    'use strict';

    /**
     * 动态获取静态资源基础路径
     * 兼容 VSCode 端口转发代理路径
     */
    function getStaticBaseUrl() {
        var pathname = window.location.pathname;
        var match = pathname.match(/^(\/proxy\/\d+)/);
        if (match) {
            return match[1];
        }
        return '';
    }

    var baseUrl = getStaticBaseUrl();

    // ==================== 内联 HTML 模板 ====================

    /** 头部 HTML */
    var headerHtml =
        '<header class="admin-header">' +
            '<div class="admin-header-content">' +
                '<div class="admin-logo">' +
                    '<img src="' + baseUrl + '/static/images/logo.png" alt="赛意AI" class="logo-image">' +
                    '<span class="admin-logo-text"> AI </span>' +
                '</div>' +
                '<nav class="admin-nav" style="display: flex;">' +
                    '<a href="http://218.13.91.107:6200/mermaid" target="_blank" class="nav-item active">' +
                        '<i class="fas fa-image"></i><span>AI Draw</span>' +
                    '</a>' +
                    '<a href="http://218.13.91.107:6202/" target="_blank" class="nav-item active">' +
                        '<i class="fas fa-code"></i><span>VsCode在线</span>' +
                    '</a>' +
                    '<a href="https://aistudio.baidu.com/paddleocr/task/new" target="_blank" class="nav-item active">' +
                        '<i class="fas fa-cube"></i><span>PaddleOCR</span>' +
                    '</a>' +
                    '<a href="https://mineru.net/OpenSourceTools/Extractor" target="_blank" class="nav-item active">' +
                        '<i class="fas fa-cube"></i><span>MinerU</span>' +
                    '</a>' +
                '</nav>' +
                '<div class="admin-user-info">' +
                    '<div class="user-notifications">' +
                        '<button class="notification-btn">' +
                            '<i class="fas fa-bell"></i>' +
                            '<span class="notification-badge">3</span>' +
                        '</button>' +
                    '</div>' +
                    '<div class="user-profile">' +
                        '<div class="user-avatar">' +
                            '<i class="fas fa-user"></i>' +
                        '</div>' +
                        '<div class="user-details">' +
                            '<span class="user-name">管理员</span>' +
                            '<span class="user-role">系统管理员</span>' +
                        '</div>' +
                        '<button class="user-menu-btn">' +
                            '<i class="fas fa-chevron-down"></i>' +
                        '</button>' +
                    '</div>' +
                '</div>' +
            '</div>' +
        '</header>';

    /** 侧边栏 HTML */
    var sidebarHtml =
        '<aside class="sidebar">' +
            '<nav class="sidebar-menu">' +
                /* 首页 */
                '<div class="menu-section">' +
                    '<a href="JavaScript:viod(0)" class="menu-item" data-page="home">' +
                        '<div class="menu-icon"><i class="fas fa-home"></i></div>' +
                        '<div class="menu-text">首页</div>' +
                    '</a>' +
                '</div>' +
                /* RPA智能自动化 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-robot"></i></div>' +
                        '<span class="menu-group-title">RPA智能自动化</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items">' +
                        '<a href="rpa.html" class="menu-item  menu-sub-item" data-page="rpa">' +
                                '<div class="menu-sub-dot"></div>' +
                                '<div class="menu-text">星辰RPA</div>' +
                            '</a>' +
                    '</div>' +
                '</div>' +
                /* OCR识别 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-file-alt"></i></div>' +
                        '<span class="menu-group-title">OCR 识别</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items">' +
                        '<a href="index.html" class="menu-item menu-sub-item" data-page="index">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">工业图纸识别</div>' +
                        '</a>' +
                        '<a href="image_ocr.html" class="menu-item menu-sub-item" data-page="image_ocr">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">图片识别多场景</div>' +
                        '</a>' +
                        '<a href="pdf_ocr.html" class="menu-item menu-sub-item" data-page="pdf_ocr">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">PDF 识别</div>' +
                        '</a>' +
                    '</div>' +
                '</div>' +
                /* AI视觉检测 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-eye"></i></div>' +
                        '<span class="menu-group-title">AI 视觉检测</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items">' +
                        '<a href="safety_helmet_detection.html" class="menu-item menu-sub-item" data-page="safety_helmet_detection">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">实时安全帽检测</div>' +
                        '</a>' +
                        '<a href="license_plate_detection.html" class="menu-item menu-sub-item" data-page="license_plate_detection">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">车牌识别</div>' +
                        '</a>' +
                        '<a href="face_detection.html" class="menu-item menu-sub-item" data-page="face_detection">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">人脸检测</div>' +
                        '</a>' +
                        '<a href="keypoint_detection.html" class="menu-item menu-sub-item" data-page="keypoint_detection">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">全身关键点检测</div>' +
                        '</a>' +
                        '<a href="gauge_detection.html" class="menu-item menu-sub-item" data-page="gauge_detection">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">精密压力表检测</div>' +
                        '</a>' +
                    '</div>' +
                '</div>' +
                /* 其他 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-ellipsis-h"></i></div>' +
                        '<span class="menu-group-title">其他</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items">' +
                        '<a href="paddle_ocr.html" class="menu-item menu-sub-item" data-page="paddle_ocr">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">在线官方案例</div>' +
                        '</a>' +
                    '</div>' +
                '</div>' +
            '</nav>' +
        '</aside>';

    /** 底部 HTML */
    var footerHtml =
        '<footer class="simple-footer">' +
            '<div class="footer-content">' +
                '<p>© 2026 赛意AI | 技术支持: sie@chinasie.com</p>' +
            '</div>' +
        '</footer>';

    // ==================== 渲染函数 ====================

    /**
     * 将 HTML 插入到占位元素中
     */
    function insertHtml(placeholderId, html) {
        var placeholder = document.getElementById(placeholderId);
        if (placeholder) {
            placeholder.outerHTML = html;
        }
    }

    /**
     * 高亮当前页面在侧边栏中对应的菜单项
     */
    function highlightCurrentPage() {
        var currentPage = window.location.pathname.split('/').pop().split('?')[0].split('#')[0];
        if (!currentPage) {
            currentPage = 'index.html';
        }

        // 先清除所有 has-active
        document.querySelectorAll('.menu-group-header.has-active').forEach(function(h) {
            h.classList.remove('has-active');
        });

        var menuItems = document.querySelectorAll('.sidebar-menu .menu-item');
        menuItems.forEach(function(item) {
            var href = item.getAttribute('href');
            if (href === currentPage) {
                item.classList.add('active');
                // 如果当前项在折叠菜单中，自动展开父级并高亮父级
                var subItems = item.closest('.menu-sub-items');
                if (subItems) {
                    subItems.classList.add('expanded');
                    var header = subItems.previousElementSibling;
                    if (header && header.classList.contains('menu-group-header')) {
                        header.classList.add('expanded');
                        header.classList.add('has-active');
                    }
                }
            } else {
                item.classList.remove('active');
            }
        });
    }

    // ==================== 立即执行 ====================

    // 同步插入 HTML，避免异步加载导致的闪烁
    insertHtml('header-placeholder', headerHtml);
    insertHtml('sidebar-placeholder', sidebarHtml);
    insertHtml('footer-placeholder', footerHtml);

    // 高亮当前页面菜单项
    highlightCurrentPage();

    // ==================== 全局函数 ====================

    /**
     * 切换子菜单的展开/折叠状态
     */
    window.toggleSubMenu = function(header) {
        header.classList.toggle('expanded');
        var subItems = header.nextElementSibling;
        if (subItems && subItems.classList.contains('menu-sub-items')) {
            subItems.classList.toggle('expanded');
        }
    };
})();
