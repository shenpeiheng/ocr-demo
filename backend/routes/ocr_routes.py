import base64
import json
import os
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file, send_from_directory

from app_core import app, ocr_processor, pdf_processor
from image_utils import preprocess_image_for_ocr
from markdown_formatter import markdown_formatter, save_markdown
from prompt_manager import get_prompt, prompt_manager
from services.result_utils import draw_ocr_boxes, format_results_as_json, generate_excel, generate_pdf_excel
from config import Config


ocr_bp = Blueprint("ocr", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


def is_pdf_file(filename):
    return os.path.splitext(filename)[1].lower() == ".pdf"


@ocr_bp.route("/")
def index():
    return send_from_directory("../frontend", "index.html")


@ocr_bp.route("/api")
def api_index():
    engine_info = ocr_processor.get_engine_info()
    return jsonify(
        {
            "name": "OCR工业图片识别系统",
            "version": "3.0.0",
            "description": "工业图纸和PDF文件OCR识别API服务，支持PaddleOCR和OpenAI VL",
            "supported_formats": list(app.config["ALLOWED_EXTENSIONS"]),
            "pdf_support": pdf_processor.initialized,
            "ocr_engine": {
                "current": engine_info["current_engine"],
                "type": engine_info["engine_type"],
                "paddleocr_available": engine_info["paddleocr_available"],
                "openai_vl_available": engine_info["openai_vl_available"],
            },
            "endpoints": {
                "/api/upload": "上传文件（支持图片和PDF）",
                "/api/process": "处理已上传的文件（自动识别文件类型）",
                "/api/process/openai_vl": "使用OpenAI VL处理图片",
                "/api/process/paddleocr": "使用PaddleOCR处理图片",
                "/api/prompts": "获取可用提示词列表",
                "/api/results/<filename>": "获取识别结果",
                "/api/download/excel/<filename>": "下载Excel格式结果",
                "/api/download/json/<filename>": "下载JSON格式结果",
                "/api/download/markdown/<filename>": "下载Markdown格式结果",
                "/api/pdf/info/<filename>": "获取PDF文件信息",
                "/api/pdf/extract/<filename>": "直接提取PDF文本",
            },
        }
    )


@ocr_bp.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "没有文件部分"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400

    if file and allowed_file(file.filename):
        original_filename = file.filename
        file_ext = os.path.splitext(original_filename)[1].lower()
        file_ext = file_ext[1:] if file_ext else "pdf"
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)
        return jsonify(
            {
                "success": True,
                "message": "文件上传成功",
                "filename": unique_filename,
                "original_filename": original_filename,
                "filepath": filepath,
                "upload_time": datetime.now().isoformat(),
            }
        )

    return jsonify({"error": "文件类型不支持"}), 400


@ocr_bp.route("/api/process", methods=["POST"])
def process_file():
    data = request.json
    if not data or "filename" not in data:
        return jsonify({"error": "缺少文件名参数"}), 400

    filename = data["filename"]
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404

    try:
        if is_pdf_file(filename):
            return process_pdf_file(filename, filepath, data)
        return process_image_file(filename, filepath, data)
    except Exception as exc:
        return jsonify({"error": f"处理失败: {str(exc)}"}), 500


@ocr_bp.route("/api/process/openai_vl", methods=["POST"])
def process_with_openai_vl():
    data = request.json
    if not data or "filename" not in data:
        return jsonify({"error": "缺少文件名参数"}), 400

    filename = data["filename"]
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    if is_pdf_file(filename):
        return jsonify({"error": "OpenAI VL暂不支持PDF文件，请先转换为图片"}), 400

    try:
        prompt_name = data.get("prompt", "mechanical_drawing_standard")
        custom_prompt = data.get("custom_prompt")
        prompt = custom_prompt if custom_prompt else get_prompt(prompt_name)

        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990, max_size=2048)
        use_preprocessed = preprocessed_path != filepath
        results = ocr_processor.process_image_with_engine(preprocessed_path, "openai_vl", prompt)

        if use_preprocessed:
            results["preprocessed_image"] = os.path.basename(preprocessed_path)
            results["original_image"] = filename
            results["image_preprocessed"] = True
        else:
            results["image_preprocessed"] = False

        result_filename = f"result_openai_vl_{os.path.splitext(filename)[0]}.json"
        result_path = os.path.join(app.config["UPLOAD_FOLDER"], result_filename)
        with open(result_path, "w", encoding="utf-8") as file_obj:
            json.dump(results, file_obj, ensure_ascii=False, indent=2)

        markdown_filename = f"result_openai_vl_{os.path.splitext(filename)[0]}.md"
        markdown_path = os.path.join(app.config["UPLOAD_FOLDER"], markdown_filename)
        markdown_content = markdown_formatter.format_ocr_results(results, include_raw=data.get("include_raw", False))
        save_markdown(markdown_content, markdown_path)

        excel_filename = f"result_openai_vl_{os.path.splitext(filename)[0]}.xlsx"
        excel_path = os.path.join(app.config["UPLOAD_FOLDER"], excel_filename)
        generate_excel(results, excel_path)

        return jsonify(
            {
                "success": True,
                "message": "OpenAI VL处理成功",
                "filename": filename,
                "file_type": "image",
                "engine": "openai_vl",
                "prompt_used": prompt_name,
                "results": results,
                "result_files": {
                    "json": result_filename,
                    "excel": excel_filename,
                    "markdown": markdown_filename,
                },
            }
        )
    except Exception as exc:
        return jsonify({"error": f"OpenAI VL处理失败: {str(exc)}"}), 500


@ocr_bp.route("/api/process/paddleocr", methods=["POST"])
def process_with_paddleocr():
    data = request.json
    if not data or "filename" not in data:
        return jsonify({"error": "缺少文件名参数"}), 400

    filename = data["filename"]
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404

    try:
        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990)
        use_preprocessed = preprocessed_path != filepath
        results = ocr_processor.process_image_with_engine(preprocessed_path, "paddleocr")

        if use_preprocessed:
            results["preprocessed_image"] = os.path.basename(preprocessed_path)
            results["original_image"] = filename
            results["image_preprocessed"] = True
        else:
            results["image_preprocessed"] = False

        result_filename = f"result_paddleocr_{os.path.splitext(filename)[0]}.json"
        result_path = os.path.join(app.config["UPLOAD_FOLDER"], result_filename)
        with open(result_path, "w", encoding="utf-8") as file_obj:
            json.dump(results, file_obj, ensure_ascii=False, indent=2)

        excel_filename = f"result_paddleocr_{os.path.splitext(filename)[0]}.xlsx"
        excel_path = os.path.join(app.config["UPLOAD_FOLDER"], excel_filename)
        generate_excel(results, excel_path)

        return jsonify(
            {
                "success": True,
                "message": "PaddleOCR处理成功",
                "filename": filename,
                "file_type": "image",
                "engine": "paddleocr",
                "results": results,
                "result_files": {"json": result_filename, "excel": excel_filename},
            }
        )
    except Exception as exc:
        return jsonify({"error": f"PaddleOCR处理失败: {str(exc)}"}), 500


@ocr_bp.route("/api/process/custom", methods=["POST"])
def process_with_custom_prompt():
    data = request.json
    if not data or "filename" not in data:
        return jsonify({"error": "缺少文件名参数"}), 400
    if "prompt" not in data or not data["prompt"].strip():
        return jsonify({"error": "缺少提示词参数"}), 400

    filename = data["filename"]
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "文件不存在"}), 404
    if is_pdf_file(filename):
        return jsonify({"error": "自定义提示词暂不支持PDF文件"}), 400

    try:
        prompt = data["prompt"] + """


        【重要输出要求】
        请在回答的最后，严格按照以下Markdown表格格式列出所有识别到的信息项及其位置坐标：

        | 序号 | 内容 | 类型 | 区域 | 坐标 |
        |------|------|------|------|------|
        | 1 | 识别出的文本 | 类型名称 | 区域描述 | (x1, y1, x2, y2) |

        坐标请使用 (左上角x, 左上角y, 右下角x, 右下角y) 格式，坐标范围为 [0, 1000]，所有数值为整数。"""

        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990, max_size=2048)
        results = ocr_processor.process_image_with_engine(preprocessed_path, "openai_vl", prompt)

        raw_text = results.get("raw_response", "")
        if not raw_text and "text_items" in results:
            raw_text = "\n".join(item.get("text", "") for item in results.get("text_items", []))

        result_image_base64 = None
        text_items = results.get("text_items", [])
        draw_source = preprocessed_path if os.path.exists(preprocessed_path) else filepath
        if os.path.exists(draw_source):
            try:
                result_image_base64 = draw_ocr_boxes(draw_source, text_items)
            except Exception as draw_err:
                print(f"[WARN] 绘制标注框失败: {draw_err}")

        if result_image_base64 is None and os.path.exists(filepath):
            try:
                with open(filepath, "rb") as file_obj:
                    img_data = file_obj.read()
                result_image_base64 = f"data:image/jpeg;base64,{base64.b64encode(img_data).decode('utf-8')}"
            except Exception as exc:
                print(f"[WARN] 读取原始图片失败: {exc}")

        return jsonify(
            {
                "success": True,
                "message": "自定义提示词处理成功",
                "filename": filename,
                "engine": "openai_vl",
                "raw_text": raw_text,
                "results": results,
                "result_image": result_image_base64,
                "json_result": format_results_as_json(results),
            }
        )
    except Exception as exc:
        return jsonify({"error": f"自定义提示词处理失败: {str(exc)}"}), 500


@ocr_bp.route("/api/prompts", methods=["GET"])
def get_prompts():
    try:
        prompts = prompt_manager.get_all_prompts()
        prompt_list = [
            {
                "name": name,
                "preview": content[:100] + "..." if len(content) > 100 else content,
                "length": len(content),
            }
            for name, content in prompts.items()
        ]
        return jsonify({"success": True, "prompts": prompt_list, "total": len(prompt_list)})
    except Exception as exc:
        return jsonify({"error": f"获取提示词失败: {str(exc)}"}), 500


@ocr_bp.route("/api/prompts/<prompt_name>", methods=["GET"])
def get_prompt_detail(prompt_name):
    try:
        prompt = prompt_manager.get_prompt(prompt_name)
        return jsonify({"success": True, "name": prompt_name, "content": prompt, "length": len(prompt)})
    except Exception as exc:
        return jsonify({"error": f"获取提示词失败: {str(exc)}"}), 500


@ocr_bp.route("/api/results/<filename>")
def get_results(filename):
    possible_filenames = [
        f"result_{os.path.splitext(filename)[0]}.json",
        f"result_openai_vl_{os.path.splitext(filename)[0]}.json",
        f"result_paddleocr_{os.path.splitext(filename)[0]}.json",
    ]

    result_path = None
    for possible_filename in possible_filenames:
        test_path = os.path.join(app.config["UPLOAD_FOLDER"], possible_filename)
        if os.path.exists(test_path):
            result_path = test_path
            break

    if not result_path:
        return jsonify({"error": "结果文件不存在"}), 404

    try:
        with open(result_path, "r", encoding="utf-8") as file_obj:
            results = json.load(file_obj)
        return jsonify(
            {
                "success": True,
                "filename": filename,
                "result_file": os.path.basename(result_path),
                "results": results,
            }
        )
    except Exception as exc:
        return jsonify({"error": f"读取结果失败: {str(exc)}"}), 500


@ocr_bp.route("/api/download/excel/<filename>")
def download_excel(filename):
    excel_path = _find_existing_result_file(
        filename,
        [
            f"result_{os.path.splitext(filename)[0]}.xlsx",
            f"result_openai_vl_{os.path.splitext(filename)[0]}.xlsx",
            f"result_paddleocr_{os.path.splitext(filename)[0]}.xlsx",
        ],
    )
    if not excel_path:
        return jsonify({"error": "Excel文件不存在"}), 404
    return send_file(excel_path, as_attachment=True, download_name=f"ocr_result_{filename}.xlsx")


@ocr_bp.route("/api/download/json/<filename>")
def download_json(filename):
    json_path = _find_existing_result_file(
        filename,
        [
            f"result_{os.path.splitext(filename)[0]}.json",
            f"result_openai_vl_{os.path.splitext(filename)[0]}.json",
            f"result_paddleocr_{os.path.splitext(filename)[0]}.json",
        ],
    )
    if not json_path:
        return jsonify({"error": "JSON文件不存在"}), 404
    return send_file(json_path, as_attachment=True, download_name=f"ocr_result_{filename}.json")


@ocr_bp.route("/api/download/markdown/<filename>")
def download_markdown(filename):
    markdown_path = _find_existing_result_file(
        filename,
        [
            f"result_{os.path.splitext(filename)[0]}.md",
            f"result_openai_vl_{os.path.splitext(filename)[0]}.md",
        ],
    )
    if not markdown_path:
        return jsonify({"error": "Markdown文件不存在"}), 404
    return send_file(markdown_path, as_attachment=True, download_name=f"ocr_result_{filename}.md")


@ocr_bp.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


def process_image_file(filename, filepath, data):
    try:
        engine = data.get("engine", "auto")
        prompt_name = data.get("prompt", "mechanical_drawing_standard")
        custom_prompt = data.get("custom_prompt")

        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990, max_size=2048)
        use_preprocessed = preprocessed_path != filepath

        if engine == "openai_vl":
            prompt = custom_prompt if custom_prompt else get_prompt(prompt_name)
            results = ocr_processor.process_image_with_engine(preprocessed_path, "openai_vl", prompt)
            result_prefix = "result_openai_vl"
        elif engine == "paddleocr":
            results = ocr_processor.process_image_with_engine(preprocessed_path, "paddleocr")
            result_prefix = "result_paddleocr"
        else:
            results = ocr_processor.process_image(preprocessed_path, custom_prompt) if custom_prompt else ocr_processor.process_image(preprocessed_path)
            result_prefix = "result"

        if use_preprocessed:
            results["preprocessed_image"] = os.path.basename(preprocessed_path)
            results["original_image"] = filename
            results["image_preprocessed"] = True
        else:
            results["image_preprocessed"] = False

        result_filename = f"{result_prefix}_{os.path.splitext(filename)[0]}.json"
        result_path = os.path.join(app.config["UPLOAD_FOLDER"], result_filename)
        with open(result_path, "w", encoding="utf-8") as file_obj:
            json.dump(results, file_obj, ensure_ascii=False, indent=2)

        excel_filename = f"{result_prefix}_{os.path.splitext(filename)[0]}.xlsx"
        excel_path = os.path.join(app.config["UPLOAD_FOLDER"], excel_filename)
        generate_excel(results, excel_path)

        markdown_filename = None
        if engine == "openai_vl" or (engine == "auto" and ocr_processor.current_engine == "openai_vl"):
            markdown_filename = f"{result_prefix}_{os.path.splitext(filename)[0]}.md"
            markdown_path = os.path.join(app.config["UPLOAD_FOLDER"], markdown_filename)
            markdown_content = markdown_formatter.format_ocr_results(results, include_raw=data.get("include_raw", False))
            save_markdown(markdown_content, markdown_path)

        response = {
            "success": True,
            "message": "图片处理成功",
            "filename": filename,
            "file_type": "image",
            "engine": results.get("ocr_engine", "unknown"),
            "results": results,
            "result_files": {"json": result_filename, "excel": excel_filename},
        }
        if markdown_filename:
            response["result_files"]["markdown"] = markdown_filename

        return jsonify(response)
    except Exception as exc:
        return jsonify({"error": f"图片处理失败: {str(exc)}"}), 500


def process_pdf_file(filename, filepath, data):
    try:
        if not pdf_processor.initialized:
            return jsonify(
                {
                    "success": False,
                    "error": "PDF处理器未初始化，请安装PDF处理依赖",
                    "suggestion": "请运行: pip install pdf2image PyMuPDF pdfplumber",
                }
            ), 500

        max_pages = data.get("max_pages", Config.PDF_MAX_PAGES)
        dpi = data.get("dpi", Config.PDF_DPI)

        pdf_base_name = os.path.splitext(filename)[0]
        images_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"images_{pdf_base_name}")
        os.makedirs(images_dir, exist_ok=True)

        pdf_result = pdf_processor.process_pdf_with_ocr(
            filepath,
            ocr_processor,
            dpi=dpi,
            max_pages=max_pages,
            output_dir=images_dir,
        )
        if not pdf_result["success"]:
            return jsonify({"success": False, "error": pdf_result.get("error", "PDF处理失败"), "file_type": "pdf"}), 500

        result_filename = f"result_{pdf_base_name}.json"
        result_path = os.path.join(app.config["UPLOAD_FOLDER"], result_filename)
        with open(result_path, "w", encoding="utf-8") as file_obj:
            json.dump(pdf_result, file_obj, ensure_ascii=False, indent=2)

        excel_filename = f"result_{pdf_base_name}.xlsx"
        excel_path = os.path.join(app.config["UPLOAD_FOLDER"], excel_filename)
        generate_pdf_excel(pdf_result, excel_path)

        if "conversion_info" in pdf_result and "image_paths" in pdf_result["conversion_info"]:
            relative_image_paths = []
            for img_path in pdf_result["conversion_info"]["image_paths"]:
                if os.path.exists(img_path):
                    relative_image_paths.append(os.path.relpath(img_path, app.config["UPLOAD_FOLDER"]))
            pdf_result["conversion_info"]["relative_image_paths"] = relative_image_paths

        return jsonify(
            {
                "success": True,
                "message": "PDF处理成功",
                "filename": filename,
                "file_type": "pdf",
                "results": pdf_result,
                "result_files": {"json": result_filename, "excel": excel_filename},
            }
        )
    except Exception as exc:
        return jsonify({"error": f"PDF处理失败: {str(exc)}"}), 500


def _find_existing_result_file(filename, candidates):
    for possible_filename in candidates:
        test_path = os.path.join(app.config["UPLOAD_FOLDER"], possible_filename)
        if os.path.exists(test_path):
            return test_path
    return None
