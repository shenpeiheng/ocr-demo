"""共享登录后端代理。"""

from __future__ import annotations

from typing import Any

import requests
from flask import Blueprint, jsonify, request, session

from auth_utils import normalize_next_path
from config import Config


auth_bp = Blueprint("auth", __name__)


def _shared_api_url(path: str) -> str:
    return f"{Config.SHARED_AUTH_API_BASE_URL}{path}"


def _extract_response_data(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = {
            "code": response.status_code,
            "msg": "共享认证服务返回了非 JSON 响应",
            "data": None,
        }
    return payload if isinstance(payload, dict) else {"code": response.status_code, "msg": "响应格式错误", "data": None}


def _get_user_summary(access_token: str, tenant_id: int | None = None) -> dict[str, Any]:
    response = requests.get(
        _shared_api_url("/system/auth/get-permission-info"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "tenant-id": str(tenant_id) if tenant_id is not None else "",
        },
        timeout=Config.SHARED_AUTH_TIMEOUT,
    )
    payload = _extract_response_data(response)
    if payload.get("code") != 0:
        return {}

    user = ((payload.get("data") or {}).get("user") or {})
    return {
        "avatar": user.get("avatar"),
        "deptName": user.get("deptName"),
        "id": user.get("id"),
        "nickname": user.get("nickname"),
        "username": user.get("username"),
    }


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    """登录并建立本地 session。"""
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    captcha_verification = str(payload.get("captchaVerification") or "").strip()
    tenant_id = payload.get("tenantId")

    if not username or not password:
        return jsonify({"success": False, "message": "请输入用户名和密码"}), 400

    login_payload: dict[str, Any] = {
        "username": username,
        "password": password,
    }
    if captcha_verification:
        login_payload["captchaVerification"] = captcha_verification

    try:
        response = requests.post(
            _shared_api_url("/system/auth/login"),
            json=login_payload,
            headers={
                "Content-Type": "application/json",
                "tenant-id": str(tenant_id) if tenant_id not in (None, "") else "",
            },
            timeout=Config.SHARED_AUTH_TIMEOUT,
        )
    except requests.RequestException as exc:
        return jsonify({"success": False, "message": f"共享认证服务不可用: {exc}"}), 502

    data = _extract_response_data(response)
    if data.get("code") != 0:
        return jsonify({
            "success": False,
            "message": data.get("msg") or "登录失败",
            "code": data.get("code"),
            "data": data.get("data"),
        }), 400

    login_result = data.get("data") or {}
    access_token = str(login_result.get("accessToken") or "").strip()
    refresh_token = str(login_result.get("refreshToken") or "").strip()
    if not access_token:
        return jsonify({"success": False, "message": "共享认证服务未返回 accessToken"}), 502

    normalized_tenant_id = int(tenant_id) if str(tenant_id or "").strip() else None
    user = {}
    try:
        user = _get_user_summary(access_token, normalized_tenant_id)
    except requests.RequestException:
        user = {}

    session.clear()
    session["shared_auth"] = {
        "access_token": access_token,
        "expires_time": login_result.get("expiresTime"),
        "refresh_token": refresh_token,
        "tenant_id": normalized_tenant_id,
        "user_id": login_result.get("userId"),
    }
    session["shared_user"] = user
    session.modified = True

    return jsonify({
        "success": True,
        "message": "登录成功",
        "next": normalize_next_path(payload.get("next")),
        "user": user,
    })


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """退出共享登录。"""
    auth = session.get("shared_auth") or {}
    access_token = (auth.get("access_token") or "").strip()
    tenant_id = auth.get("tenant_id")
    if access_token:
        try:
            requests.post(
                _shared_api_url("/system/auth/logout"),
                json={},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "tenant-id": str(tenant_id) if tenant_id is not None else "",
                },
                timeout=Config.SHARED_AUTH_TIMEOUT,
            )
        except requests.RequestException:
            pass

    session.clear()
    return jsonify({"success": True})


@auth_bp.route("/api/auth/status", methods=["GET"])
def status():
    """返回当前登录态。"""
    return jsonify({
        "success": True,
        "loggedIn": bool((session.get("shared_auth") or {}).get("access_token")),
        "user": session.get("shared_user") or {},
    })


@auth_bp.route("/api/auth/tenant-options", methods=["GET"])
def tenant_options():
    """返回登录页租户列表和默认租户。"""
    website = str(request.args.get("website") or "").strip()
    headers = {"Accept": "application/json"}

    try:
        list_response = requests.get(
            _shared_api_url("/system/tenant/simple-list"),
            headers=headers,
            timeout=Config.SHARED_AUTH_TIMEOUT,
        )
        list_payload = _extract_response_data(list_response)
    except requests.RequestException as exc:
        return jsonify({"success": False, "message": f"获取租户列表失败: {exc}", "options": []}), 502

    options = list_payload.get("data") or []
    default_tenant = None

    if website:
        try:
            website_response = requests.get(
                _shared_api_url(f"/system/tenant/get-by-website?website={website}"),
                headers=headers,
                timeout=Config.SHARED_AUTH_TIMEOUT,
            )
            website_payload = _extract_response_data(website_response)
            if website_payload.get("code") == 0:
                default_tenant = website_payload.get("data")
        except requests.RequestException:
            default_tenant = None

    if not default_tenant and options:
        default_tenant = options[0]

    return jsonify({
        "success": True,
        "defaultTenantId": (default_tenant or {}).get("id"),
        "options": options,
    })
