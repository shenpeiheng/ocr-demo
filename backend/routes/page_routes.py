"""
页面路由 - 处理所有前端页面访问，移除 .html 后缀
"""

from flask import Blueprint, send_from_directory, redirect
from app_core import app

page_bp = Blueprint("pages", __name__)


# 页面路由映射表
PAGE_ROUTES = {
    # 首页
    "/": "index.html",
    "/index": "index.html",

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
    "/price-comparison": "price_comparison.html",
    "/item-code-generation": "item_code_generation.html",
    "/procurement-matching": "procurement_matching.html",

    # 测试页面
    "/voice-test": "voice-test.html",
}


# 动态注册所有页面路由
for route, html_file in PAGE_ROUTES.items():
    def create_handler(filename):
        def handler():
            return send_from_directory("../frontend", filename)
        return handler

    # 设置路由名称（用下划线替换连字符）
    route_name = route.strip("/").replace("-", "_") or "home"
    page_bp.add_url_rule(
        route,
        endpoint=route_name,
        view_func=create_handler(html_file)
    )


# 兼容性重定向：旧的 .html URL 重定向到新 URL
@page_bp.route("/<path:filename>.html")
def legacy_html_redirect(filename):
    """
    兼容旧的 .html URL，自动重定向到无后缀版本
    例如: /paddle_ocr.html -> /paddle-ocr
    """
    # 将下划线转换为连字符（符合现代URL规范）
    clean_path = filename.replace("_", "-")

    # 特殊处理：index.html 重定向到根路径
    if clean_path == "index":
        return redirect("/", code=301)

    return redirect(f"/{clean_path}", code=301)


# 静态文件路由保持不变
@page_bp.route("/static/<path:filename>")
def static_files(filename):
    """静态资源文件"""
    return send_from_directory("../frontend/static", filename)
