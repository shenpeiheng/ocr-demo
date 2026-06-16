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
    var SIDEBAR_COLLAPSED_KEY = 'sie_admin_sidebar_collapsed';

    // ==================== 内联 HTML 模板 ====================

    /** 头部 HTML */
    var headerHtml =
        '<header class="admin-header">' +
            '<div class="admin-header-content">' +
                '<a href="' + baseUrl + '/index.html" class="admin-logo" style="cursor: pointer; text-decoration: none;">' +
                    '<img src="' + baseUrl + '/static/images/logo.png" alt="赛意AI" class="logo-image">' +
                    '<span class="admin-logo-text">赛意AI</span>' +
                '</a>' +
                '<nav class="admin-nav" style="display: flex;">' +
                    '<a href="http://218.13.91.107:6200/mermaid" target="_blank" class="nav-item">' +
                        '<i class="fas fa-image"></i><span>AI Draw</span>' +
                    '</a>' +
                    '<a href="https://218.13.91.107:6201/" target="_blank" class="nav-item">' +
                        '<i class="fas fa-code"></i><span>VsCode在线</span>' +
                    '</a>' +
                    '<a href="https://aistudio.baidu.com/paddleocr/task/new" target="_blank" class="nav-item">' +
                        '<i class="fas fa-cube"></i><span>PaddleOCR</span>' +
                    '</a>' +
                    '<a href="https://mineru.net/OpenSourceTools/Extractor" target="_blank" class="nav-item">' +
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
        '<aside class="sidebar" id="appSidebar">' +
            '<div class="sidebar-control">' +
                '<span class="sidebar-control-title"><i class="fas fa-stream"></i><span>功能导航</span></span>' +
                '<button type="button" class="sidebar-toggle" id="sidebarToggle" aria-label="收起侧边栏" title="收起侧边栏">' +
                    '<i class="fas fa-angle-double-left"></i>' +
                '</button>' +
            '</div>' +
            '<nav class="sidebar-menu">' +
                /* 首页 */
                '<div class="menu-section">' +
                    '<a href="index.html" class="menu-item" data-page="index">' +
                        '<div class="menu-icon"><i class="fas fa-home"></i></div>' +
                        '<div class="menu-text">首页</div>' +
                    '</a>' +
                '</div>' +
                /* RPA智能自动化 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header expanded" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-robot"></i></div>' +
                        '<span class="menu-group-title">RPA智能自动化</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items expanded">' +
                        '<a href="rpa.html" class="menu-item  menu-sub-item" data-page="rpa">' +
                                '<div class="menu-sub-dot"></div>' +
                                '<div class="menu-text">星辰RPA</div>' +
                            '</a>' +
                    '</div>' +
                '</div>' +
                /* OCR识别 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header expanded" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-file-alt"></i></div>' +
                        '<span class="menu-group-title">OCR 识别</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items expanded">' +
                        '<a href="mechanical_drawing_ocr.html" class="menu-item menu-sub-item" data-page="mechanical_drawing_ocr">' +
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
                        '<a href="flowchart_ocr.html" class="menu-item menu-sub-item" data-page="flowchart_ocr">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">流程图识别</div>' +
                        '</a>' +
                        '<a href="word_flowchart_ocr.html" class="menu-item menu-sub-item" data-page="word_flowchart_ocr">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">Word流程图识别</div>' +
                        '</a>' +
                    '</div>' +
                '</div>' +
                /* AI视觉检测 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header expanded" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-eye"></i></div>' +
                        '<span class="menu-group-title">AI 视觉检测</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items expanded">' +
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
                /* 业务应用 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header expanded" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-briefcase"></i></div>' +
                        '<span class="menu-group-title">业务应用</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items expanded">' +
                        '<a href="opportunity_entry.html" class="menu-item menu-sub-item" data-page="opportunity_entry">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">商机快速录入</div>' +
                        '</a>' +
                        '<a href="contract_recognition.html" class="menu-item menu-sub-item" data-page="contract_recognition">' +
                            '<div class="menu-sub-dot"></div>' +
                            '<div class="menu-text">合同识别</div>' +
                        '</a>' +
                    '</div>' +
                '</div>' +
                /* 其他 */
                '<div class="menu-section">' +
                    '<div class="menu-group-header expanded" onclick="toggleSubMenu(this)">' +
                        '<div class="menu-group-icon"><i class="fas fa-ellipsis-h"></i></div>' +
                        '<span class="menu-group-title">其他</span>' +
                        '<i class="fas fa-chevron-left menu-group-arrow"></i>' +
                    '</div>' +
                    '<div class="menu-sub-items expanded">' +
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

    /**
     * 读取侧边栏折叠状态
     */
    function getSidebarCollapsed() {
        try {
            return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1';
        } catch (error) {
            console.warn('Read sidebar state failed:', error);
            return false;
        }
    }

    /**
     * 保存侧边栏折叠状态
     */
    function saveSidebarCollapsed(collapsed) {
        try {
            window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0');
        } catch (error) {
            console.warn('Save sidebar state failed:', error);
        }
    }

    /**
     * 应用侧边栏折叠状态
     */
    function setSidebarCollapsed(collapsed) {
        var sidebar = document.getElementById('appSidebar');
        var toggle = document.getElementById('sidebarToggle');
        if (!sidebar) {
            return;
        }

        sidebar.classList.toggle('is-collapsed', collapsed);
        if (toggle) {
            toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            toggle.setAttribute('aria-label', collapsed ? '展开侧边栏' : '收起侧边栏');
            toggle.setAttribute('title', collapsed ? '展开侧边栏' : '收起侧边栏');
        }
    }

    /**
     * 初始化侧边栏整体折叠
     */
    function initSidebarCollapse() {
        var toggle = document.getElementById('sidebarToggle');
        setSidebarCollapsed(getSidebarCollapsed());

        if (toggle) {
            toggle.addEventListener('click', function() {
                var sidebar = document.getElementById('appSidebar');
                var collapsed = sidebar ? !sidebar.classList.contains('is-collapsed') : false;
                setSidebarCollapsed(collapsed);
                saveSidebarCollapsed(collapsed);
            });
        }
    }

    /**
     * 为折叠后的图标菜单补充浏览器原生提示
     */
    function initSidebarTitles() {
        document.querySelectorAll('.sidebar .menu-item, .sidebar .menu-group-header').forEach(function(item) {
            var titleNode = item.querySelector('.menu-text, .menu-group-title');
            if (titleNode && !item.getAttribute('title')) {
                item.setAttribute('title', titleNode.textContent.trim());
            }
        });
    }

    /**
     * 初始化 AI 视觉检测结果 Tab 切换
     */
    function initAiResultTabs() {
        document.addEventListener('click', function(event) {
            if (!event.target || !event.target.closest) {
                return;
            }

            var tab = event.target.closest('.ai-result-tab');
            if (!tab) {
                return;
            }

            var card = tab.closest('.ai-result-card');
            if (!card) {
                return;
            }

            var target = tab.getAttribute('data-target');
            card.querySelectorAll('.ai-result-tab').forEach(function(btn) {
                btn.classList.toggle('active', btn === tab);
            });
            card.querySelectorAll('.ai-result-pane').forEach(function(pane) {
                pane.classList.toggle('active', pane.getAttribute('data-pane') === target);
            });
        });
    }

    /**
     * 初始化 AI 视觉检测 JSON 复制
     */
    function initAiJsonCopy() {
        document.addEventListener('click', function(event) {
            if (!event.target || !event.target.closest) {
                return;
            }

            var copyButton = event.target.closest('[data-ai-copy-json]');
            if (!copyButton) {
                return;
            }

            var card = copyButton.closest('.ai-result-card');
            var jsonOutput = card ? card.querySelector('#jsonOutput') : null;
            var text = jsonOutput ? jsonOutput.textContent : '';

            if (!text || !text.trim()) {
                showAiCopyToast('暂无可复制内容');
                return;
            }

            copyTextToClipboard(text, function() {
                showAiCopyToast('JSON 已复制');
            }, function() {
                showAiCopyToast('复制失败，请手动选择复制');
            });
        });
    }

    function copyTextToClipboard(text, onSuccess, onError) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(onSuccess).catch(function() {
                if (fallbackCopyText(text)) {
                    onSuccess();
                } else {
                    onError();
                }
            });
            return;
        }

        if (fallbackCopyText(text)) {
            onSuccess();
        } else {
            onError();
        }
    }

    function fallbackCopyText(text) {
        var textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.setAttribute('readonly', '');
        textArea.style.position = 'fixed';
        textArea.style.top = '0';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            return document.execCommand('copy');
        } catch (err) {
            return false;
        } finally {
            document.body.removeChild(textArea);
        }
    }

    function showAiCopyToast(message) {
        var toast = document.querySelector('[data-ai-copy-toast]');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'copy-toast';
            toast.setAttribute('data-ai-copy-toast', 'true');
            document.body.appendChild(toast);
        }

        toast.textContent = message;
        toast.classList.add('show');

        clearTimeout(showAiCopyToast.timer);
        showAiCopyToast.timer = setTimeout(function() {
            toast.classList.remove('show');
        }, 2000);
    }

    // ==================== 立即执行 ====================

    // 同步插入 HTML，避免异步加载导致的闪烁
    insertHtml('header-placeholder', headerHtml);
    insertHtml('sidebar-placeholder', sidebarHtml);
    insertHtml('footer-placeholder', footerHtml);

    // 高亮当前页面菜单项
    highlightCurrentPage();
    initSidebarTitles();
    initSidebarCollapse();
    initAiResultTabs();
    initAiJsonCopy();

    // ==================== 全局函数 ====================

    /**
     * 切换子菜单的展开/折叠状态
     */
    window.toggleSubMenu = function(header) {
        var subItems = header.nextElementSibling;
        var sidebar = header.closest('.sidebar');

        if (sidebar && sidebar.classList.contains('is-collapsed')) {
            setSidebarCollapsed(false);
            saveSidebarCollapsed(false);
            if (subItems && subItems.classList.contains('menu-sub-items')) {
                header.classList.add('expanded');
                subItems.classList.add('expanded');
            }
            return;
        }

        header.classList.toggle('expanded');
        if (subItems && subItems.classList.contains('menu-sub-items')) {
            subItems.classList.toggle('expanded');
        }
    };
})();
