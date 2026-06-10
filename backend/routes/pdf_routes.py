import os
import re

from flask import Blueprint, jsonify, request, send_file

from app_core import app, pdf_processor
from routes.ocr_routes import is_pdf_file


pdf_bp = Blueprint("pdf", __name__)


@pdf_bp.route("/api/pdf/info/<filename>")
def get_pdf_info(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    if not is_pdf_file(filename):
        return jsonify({"error": "文件不是PDF格式"}), 400
    if not pdf_processor.initialized:
        return jsonify(
            {
                "success": False,
                "error": "PDF处理器未初始化",
                "suggestion": "请安装PDF处理依赖: pip install pdf2image PyMuPDF pdfplumber",
            }
        ), 500

    try:
        pdf_info = pdf_processor._get_pdf_info(filepath)

        # 生成预览图（使用 PyMuPDF）
        try:
            import fitz  # PyMuPDF
            pdf_base_name = os.path.splitext(filename)[0]
            preview_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"preview_{pdf_base_name}")
            os.makedirs(preview_dir, exist_ok=True)

            preview_paths = []
            doc = fitz.open(filepath)
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=300)  # 提高到 300 DPI
                preview_path = os.path.join(preview_dir, f"page_{page_num + 1}.jpg")
                pix.save(preview_path)
                relative_path = os.path.relpath(preview_path, app.config["UPLOAD_FOLDER"])
                preview_paths.append(relative_path)
            doc.close()

            pdf_info["preview_images"] = preview_paths
        except Exception:
            # 预览图生成失败，返回空数组
            pdf_info["preview_images"] = []

        return jsonify({"success": True, "filename": filename, "pdf_info": pdf_info})
    except Exception as exc:
        return jsonify({"error": f"获取PDF信息失败: {str(exc)}"}), 500


@pdf_bp.route("/api/pdf/extract/<filename>")
def extract_pdf_text(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    if not is_pdf_file(filename):
        return jsonify({"error": "文件不是PDF格式"}), 400
    if not pdf_processor.initialized:
        return jsonify(
            {
                "success": False,
                "error": "PDF处理器未初始化",
                "suggestion": "请安装PDF处理依赖: pip install pdf2image PyMuPDF pdfplumber",
            }
        ), 500

    try:
        text_result = pdf_processor.extract_text_from_pdf(
            filepath,
            first_page=request.args.get("first_page", default=None, type=int),
            last_page=request.args.get("last_page", default=None, type=int),
        )
        if text_result["success"]:
            return jsonify({"success": True, "filename": filename, "result": text_result})
        return jsonify({"success": False, "error": text_result.get("error", "文本提取失败")}), 500
    except Exception as exc:
        return jsonify({"error": f"提取PDF文本失败: {str(exc)}"}), 500


@pdf_bp.route("/api/pdf/images/<filename>/<int:page>")
def get_pdf_image(filename, page):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    if not is_pdf_file(filename):
        return jsonify({"error": "文件不是PDF格式"}), 400

    pdf_base_name = os.path.splitext(filename)[0]
    images_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"images_{pdf_base_name}")
    image_patterns = [
        f"page_{page:03d}.png",
        f"page_{page}.png",
        f"{page}.png",
        f"page_{page:03d}.jpg",
        f"page_{page}.jpg",
        f"{page}.jpg",
    ]

    image_path = None
    for pattern in image_patterns:
        test_path = os.path.join(images_dir, pattern)
        if os.path.exists(test_path):
            image_path = test_path
            break

    if not image_path:
        return jsonify({"error": "PDF页面图像不存在"}), 404

    return send_file(image_path)


@pdf_bp.route("/api/pdf/images/list/<filename>")
def list_pdf_images(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    if not is_pdf_file(filename):
        return jsonify({"error": "文件不是PDF格式"}), 400

    pdf_base_name = os.path.splitext(filename)[0]
    images_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"images_{pdf_base_name}")
    if not os.path.exists(images_dir):
        return jsonify({"success": True, "filename": filename, "images": [], "total": 0})

    image_files = []
    for file_name in os.listdir(images_dir):
        if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
            match = re.search(r"page_(\d+)", file_name)
            if match:
                page_num = int(match.group(1))
            else:
                match = re.search(r"(\d+)\.", file_name)
                page_num = int(match.group(1)) if match else 0
            image_files.append(
                {
                    "filename": file_name,
                    "page": page_num,
                    "url": f"/api/pdf/images/{filename}/{page_num}",
                }
            )

    image_files.sort(key=lambda item: item["page"])
    return jsonify({"success": True, "filename": filename, "images": image_files, "total": len(image_files)})
