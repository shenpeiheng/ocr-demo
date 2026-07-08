"""认证辅助方法。"""

from urllib.parse import quote

import requests
from flask import redirect, request, session

from config import Config


DEFAULT_LOGIN_NEXT = "/"


def is_logged_in() -> bool:
    """当前请求是否已建立本地登录态。"""
    auth = session.get("shared_auth") or {}
    return bool(auth.get("access_token"))


def should_bypass_login() -> bool:
    """嵌入模式请求绕过登录校验。"""
    return "_no_sidebar" in request.args


def has_valid_remote_session() -> bool:
    """校验共享后端 token 是否仍然有效。"""
    auth = session.get("shared_auth") or {}
    access_token = str(auth.get("access_token") or "").strip()
    if not access_token:
        return False

    tenant_id = auth.get("tenant_id")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "tenant-id": str(tenant_id) if tenant_id is not None else "",
    }

    try:
        response = requests.get(
            f"{Config.SHARED_AUTH_API_BASE_URL}/system/auth/get-permission-info",
            headers=headers,
            timeout=Config.SHARED_AUTH_TIMEOUT,
        )
    except requests.RequestException:
        # 共享认证服务暂时不可用时，不强制清空当前本地会话
        return True

    if response.status_code == 401:
        return False

    try:
        payload = response.json()
    except ValueError:
        return True

    return payload.get("code") != 401


def build_login_redirect_response():
    """未登录时跳转到本地登录页。"""
    if is_logged_in():
        if has_valid_remote_session():
            return None
        session.clear()
    elif should_bypass_login():
        return None

    next_path = request.full_path if request.query_string else request.path
    if next_path.endswith("?"):
        next_path = next_path[:-1]

    if not next_path.startswith("/"):
        next_path = DEFAULT_LOGIN_NEXT

    return redirect(f"/login?next={quote(next_path, safe='')}", code=302)


def normalize_next_path(next_path: str | None) -> str:
    """清洗登录成功后的跳转路径，避免开放重定向。"""
    value = (next_path or "").strip()
    if not value.startswith("/"):
        return DEFAULT_LOGIN_NEXT
    if value.startswith("//"):
        return DEFAULT_LOGIN_NEXT
    return value
