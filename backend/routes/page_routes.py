"""
页面路由 - 处理所有前端页面访问，移除 .html 后缀
"""

from urllib.parse import urlencode

from flask import Blueprint, send_from_directory, redirect, jsonify, request

from auth_utils import build_login_redirect_response
from config import Config

page_bp = Blueprint("pages", __name__)


# 页面路由映射表
PAGE_ROUTES = {
    # 首页
    "/": "index.html",
    "/index": "index.html",
    "/login": "login.html",

    # OCR 相关页面
    "/paddle-ocr": "paddle_ocr.html",
    "/openai-vl": "openai_vl.html",
    "/pdf-ocr": "pdf_ocr.html",
    "/image-ocr": "image_ocr.html",
    "/mechanical-drawing-ocr": "mechanical_drawing_ocr.html",

    # 流程图相关
    "/flowchart-ocr": "flowchart_ocr.html",
    "/word-flowchart-ocr": "word_flowchart_ocr.html",

    # 视觉检测页面
    "/keypoint-detection": "keypoint_detection.html",
    "/safety-helmet-detection": "safety_helmet_detection.html",
    "/gauge-detection": "gauge_detection.html",
    "/face-detection": "face_detection.html",
    "/license-plate-detection": "license_plate_detection.html",

    # 业务应用页面
    "/rpa": "rpa.html",
    "/contract-recognition": "contract_recognition.html",
    "/opportunity-entry": "opportunity_entry.html",
    "/ai-agent-service-desk": "ai_agent_service_desk.html",
    "/oracle-prd": "oracle_prd.html",
    "/apex-ai": "apex_ai.html",
    "/price-comparison": "price_comparison.html",
    "/item-code-generation": "item_code_generation.html",
    "/procurement-matching": "procurement_matching.html",

    # 测试页面
    "/voice-test": "voice_test.html",

    # Whisper 语音转字幕
    "/whisper": "whisper.html",
}

PUBLIC_PAGE_ROUTES = {"/login"}


# 动态注册所有页面路由
for route, html_file in PAGE_ROUTES.items():
    def create_handler(current_route, filename):
        def handler():
            if current_route not in PUBLIC_PAGE_ROUTES:
                login_redirect = build_login_redirect_response()
                if login_redirect:
                    return login_redirect
            return send_from_directory("../frontend", filename)
        return handler

    # 设置路由名称（用下划线替换连字符）
    route_name = route.strip("/").replace("-", "_") or "home"
    page_bp.add_url_rule(
        route,
        endpoint=route_name,
        view_func=create_handler(route, html_file)
    )


# 兼容性重定向：旧的 .html URL 重定向到新 URL
@page_bp.route("/<path:filename>.html")
def legacy_html_redirect(filename):
    """
    兼容旧的 .html URL，自动重定向到无后缀版本
    例如: /paddle_ocr.html -> /paddle-ocr
    """
    clean_path = filename.replace("_", "-")
    route_path = "/" if clean_path == "index" else f"/{clean_path}"

    if route_path not in PUBLIC_PAGE_ROUTES:
        login_redirect = build_login_redirect_response()
        if login_redirect:
            return login_redirect

    # 将下划线转换为连字符（符合现代URL规范）
    query_string = request.args.to_dict(flat=False)
    encoded_query = urlencode(query_string, doseq=True)

    # 特殊处理：index.html 重定向到根路径
    if clean_path == "index":
        target = "/"
        if encoded_query:
            target = f"{target}?{encoded_query}"
        return redirect(target, code=301)

    target = f"/{clean_path}"
    if encoded_query:
        target = f"{target}?{encoded_query}"
    return redirect(target, code=301)


# 静态文件路由保持不变
@page_bp.route("/static/<path:filename>")
def static_files(filename):
    """静态资源文件"""
    return send_from_directory("../frontend/static", filename)


@page_bp.route("/api/ui/model-options", methods=["GET"])
def get_ui_model_options():
    """返回前端页面使用的模型标签与实际模型映射（兼容旧接口）"""
    return jsonify({
        "success": True,
        "models": Config.get_model_options(),
    })


@page_bp.route("/api/llm/config", methods=["GET"])
def get_llm_config():
    """通用 LLM 配置接口 - 返回可用模型列表，前端动态渲染模型选择器"""
    models = Config.get_llm_models()
    # 默认模型排到最前面
    sorted_models = sorted(models, key=lambda m: (not m.get('default', False), m.get('key', '')))
    return jsonify({
        "success": True,
        "models": [
            {
                "key": m["key"],
                "label": m.get("label", m["key"]),
                "default": bool(m.get("default", False)),
            }
            for m in sorted_models
        ],
        "default_model": Config.get_llm_default_model(),
    })
