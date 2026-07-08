(function () {
    'use strict';

    var DEFAULT_NEXT = '/';
    var REMEMBER_ME_KEY = 'REMEMBER_ME_USERNAME_' + window.location.hostname;
    var LAYOUTS = ['panel-right', 'panel-center', 'panel-left'];
    var THEMES = ['login-light','login-dark'];
    var ACCENTS = ['#ac063e', '#16a34a', '#ec4899', '#0ea5e9'];

    var form = document.getElementById('loginForm');
    var tenantField = document.getElementById('tenantField');
    var tenantSelect = document.getElementById('tenantId');
    var usernameInput = document.getElementById('username');
    var passwordInput = document.getElementById('password');
    var rememberInput = document.getElementById('rememberMe');
    var feedback = document.getElementById('loginFeedback');
    var submitButton = document.getElementById('loginSubmit');
    var togglePasswordButton = document.getElementById('togglePassword');
    var layoutToggleButton = document.getElementById('layoutToggle');
    var themeToggleButton = document.getElementById('themeToggle');
    var colorToggleButton = document.getElementById('colorToggle');

    function getQueryParam(name) {
        try {
            return new URLSearchParams(window.location.search).get(name) || '';
        } catch (error) {
            return '';
        }
    }

    function normalizeNext(nextPath) {
        if (!nextPath || nextPath.charAt(0) !== '/' || nextPath.indexOf('//') === 0) {
            return DEFAULT_NEXT;
        }
        return nextPath;
    }

    function setFeedback(message, isSuccess) {
        feedback.textContent = message || '';
        feedback.classList.toggle('is-success', !!isSuccess);
    }

    function setSubmitting(isSubmitting) {
        submitButton.disabled = isSubmitting;
        submitButton.textContent = isSubmitting ? '登录中...' : '登录';
    }

    function renderTenantOptions(options, defaultTenantId) {
        if (!tenantField || !tenantSelect) {
            return;
        }

        tenantSelect.innerHTML = '<option value="">请选择租户</option>';
        if (!options || !options.length) {
            tenantField.hidden = true;
            return;
        }

        options.forEach(function (item) {
            var option = document.createElement('option');
            option.value = String(item.id);
            option.textContent = item.name || String(item.id);
            tenantSelect.appendChild(option);
        });

        if (defaultTenantId !== undefined && defaultTenantId !== null && String(defaultTenantId) !== '') {
            tenantSelect.value = String(defaultTenantId);
        } else if (options[0] && options[0].id !== undefined) {
            tenantSelect.value = String(options[0].id);
        }

        tenantField.hidden = false;
    }

    function applyTheme(themeName) {
        document.body.classList.remove('login-dark', 'login-light');
        document.body.classList.add(themeName);
        themeToggleButton.classList.toggle('is-active', themeName === 'login-light');
        localStorage.setItem('vben_login_theme', themeName);
    }

    function applyLayout(layoutName) {
        document.body.classList.remove('panel-right', 'panel-center', 'panel-left');
        document.body.classList.add(layoutName);
        localStorage.setItem('vben_login_layout', layoutName);
    }

    function applyAccent(color) {
        document.documentElement.style.setProperty('--login-primary', color);
        document.documentElement.style.setProperty('--login-primary-strong', color);
        localStorage.setItem('vben_login_accent', color);
    }

    function cycleValue(values, currentValue) {
        var currentIndex = values.indexOf(currentValue);
        return values[(currentIndex + 1) % values.length];
    }

    async function checkStatusAndRedirect() {
        try {
            var response = await fetch('/api/auth/status', { credentials: 'same-origin' });
            var data = await response.json();
            if (data && data.loggedIn) {
                window.location.replace(normalizeNext(getQueryParam('next')));
            }
        } catch (error) {
            // 忽略状态检查失败，允许继续显示登录页
        }
    }

    async function handleSubmit(event) {
        event.preventDefault();

        var username = usernameInput.value.trim();
        var password = passwordInput.value;
        var tenantId = tenantSelect ? tenantSelect.value : '';
        var nextPath = normalizeNext(getQueryParam('next'));

        if (!username || !password) {
            setFeedback('请输入用户名和密码');
            return;
        }

        setFeedback('');
        setSubmitting(true);

        try {
            var response = await fetch('/api/auth/login', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tenantId: tenantId,
                    username: username,
                    password: password,
                    next: nextPath
                })
            });

            var data = await response.json();
            if (!response.ok || !data.success) {
                setFeedback((data && data.message) || '登录失败，请稍后再试');
                return;
            }

            localStorage.setItem(REMEMBER_ME_KEY, rememberInput.checked ? username : '');
            setFeedback('登录成功，正在跳转...', true);
            window.location.replace(normalizeNext(data.next || nextPath));
        } catch (error) {
            setFeedback('登录请求失败，请检查共享认证服务是否可达');
        } finally {
            setSubmitting(false);
        }
    }

    function initRememberMe() {
        var savedUsername = localStorage.getItem(REMEMBER_ME_KEY) || '';
        if (savedUsername) {
            usernameInput.value = savedUsername;
            rememberInput.checked = true;
        }
    }

    async function initTenantOptions() {
        if (!tenantField || !tenantSelect) {
            return;
        }

        try {
            var response = await fetch('/api/auth/tenant-options?website=' + encodeURIComponent(window.location.hostname), {
                credentials: 'same-origin'
            });
            var data = await response.json();
            if (!response.ok || !data.success) {
                tenantField.hidden = true;
                return;
            }
            renderTenantOptions(data.options || [], data.defaultTenantId);
        } catch (error) {
            tenantField.hidden = true;
        }
    }

    function initPasswordToggle() {
        togglePasswordButton.addEventListener('click', function () {
            var isPassword = passwordInput.getAttribute('type') !== 'text';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            togglePasswordButton.innerHTML = isPassword
                ? '<i class="fas fa-eye-slash"></i>'
                : '<i class="fas fa-eye"></i>';
        });
    }

    function initToolbar() {
        var storedTheme = localStorage.getItem('vben_login_theme') || 'login-light';
        var storedLayout = localStorage.getItem('vben_login_layout') || 'panel-right';
        var storedAccent = localStorage.getItem('vben_login_accent') || ACCENTS[0];

        applyTheme(storedTheme);
        applyLayout(storedLayout);
        applyAccent(storedAccent);

        themeToggleButton.addEventListener('click', function () {
            applyTheme(cycleValue(THEMES, document.body.classList.contains('login-light') ? 'login-light' : 'login-dark'));
        });

        layoutToggleButton.addEventListener('click', function () {
            var activeLayout = LAYOUTS.filter(function (layoutName) {
                return document.body.classList.contains(layoutName);
            })[0] || LAYOUTS[0];
            applyLayout(cycleValue(LAYOUTS, activeLayout));
        });

        colorToggleButton.addEventListener('click', function () {
            var currentAccent = localStorage.getItem('vben_login_accent') || ACCENTS[0];
            applyAccent(cycleValue(ACCENTS, currentAccent));
        });
    }

    function initDisabledActions() {
        document.querySelectorAll('[data-disabled-action]').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                setFeedback('该登录方式暂未在本地接入');
            });
        });
    }

    form.addEventListener('submit', handleSubmit);
    initTenantOptions();
    initRememberMe();
    initPasswordToggle();
    initToolbar();
    initDisabledActions();
    checkStatusAndRedirect();
})();
