import base64
import copy
import json
import os
import threading
import time
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file, send_from_directory

from app_core import app, ocr_processor, pdf_processor
from flowchart_processor import FLOWCHART_COLUMNS, process_flowchart_images
from image_utils import preprocess_image_for_ocr
from markdown_formatter import markdown_formatter, save_markdown
from mineru_processor import create_mineru_processor
from prompt_manager import get_prompt, prompt_manager
from services.result_utils import (
    draw_ocr_boxes,
    format_results_as_json,
    generate_excel,
    generate_flowchart_excel,
    generate_pdf_excel,
    generate_word_flowchart_excel,
)
from word_flowchart_processor import extract_docx_images, is_docx_file
from config import Config


ocr_bp = Blueprint("ocr", __name__)
WORD_FLOWCHART_TASKS = {}
WORD_FLOWCHART_TASK_LOCK = threading.Lock()
DEFAULT_WORD_FLOWCHART_DOC = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "frontend",
        "static",
        "images",
        "demo",
        "flow",
        "ERP_Blueprint_FlowCharts_Only.docx",
    )
)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


def is_pdf_file(filename):
    return os.path.splitext(filename)[1].lower() == ".pdf"


def is_image_file(filename):
    return os.path.splitext(filename)[1].lower().lstrip(".") in {"png", "jpg", "jpeg", "bmp", "tiff", "gif", "webp"}


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
            "pdf_engines": {
                "current": Config.PDF_ENGINE,
                "available": ["ocr", "mineru", "paddleocr_vl"],
                "mineru_configured": bool(Config.MINERU_API_KEY or Config.MINERU_OFFICIAL_TOKEN),
                "mineru_mode": Config.MINERU_REQUEST_MODE,
                "mineru_model": Config.MINERU_MODEL,
                "mineru_official_enabled": bool(Config.MINERU_OFFICIAL_TOKEN),
                "paddleocr_vl_configured": bool(Config.PADDLEOCR_ONLINE_TOKEN),
            },
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
                "/api/flowchart/process": "批量识别流程图图片",
                "/api/flowchart/download/excel/<batch_id>": "下载流程图识别Excel",
                "/api/flowchart/word/process": "从Word文档批量提取流程图图片",
                "/api/flowchart/word/start/<task_id>": "识别已勾选的Word流程图图片",
                "/api/flowchart/word/status/<task_id>": "获取Word流程图批量识别任务状态",
                "/api/flowchart/word/retry/<task_id>": "重试Word流程图识别失败图片",
                "/api/flowchart/word/download/excel/<batch_id>": "下载Word流程图识别Excel",
                "/api/flowchart/word/download/json/<batch_id>": "下载Word流程图识别JSON",
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


@ocr_bp.route("/api/flowchart/process", methods=["POST"])
def process_flowchart_files():
    files = request.files.getlist("files")
    if not files:
        single_file = request.files.get("file")
        files = [single_file] if single_file else []

    files = [file for file in files if file and file.filename]
    if not files:
        return jsonify({"success": False, "error": "请选择流程图图片"}), 400

    if len(files) > 10:
        return jsonify({"success": False, "error": "一次最多支持10张流程图图片"}), 400

    batch_id = uuid.uuid4().hex
    image_entries = []
    for index, file in enumerate(files, 1):
        original_filename = file.filename
        if not is_image_file(original_filename):
            return jsonify({"success": False, "error": f"不支持的图片格式: {original_filename}"}), 400

        file_ext = os.path.splitext(original_filename)[1].lower().lstrip(".") or "png"
        unique_filename = f"flowchart_{batch_id}_{index:02d}.{file_ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)
        image_entries.append(
            {
                "filename": unique_filename,
                "original_filename": original_filename,
                "path": filepath,
            }
        )

    try:
        flowchart_result = process_flowchart_images(image_entries, ocr_processor)
        flowchart_result["batch_id"] = batch_id

        result_filename = f"result_flowchart_{batch_id}.json"
        result_path = os.path.join(app.config["UPLOAD_FOLDER"], result_filename)
        with open(result_path, "w", encoding="utf-8") as file_obj:
            json.dump(flowchart_result, file_obj, ensure_ascii=False, indent=2)

        excel_filename = f"result_flowchart_{batch_id}.xlsx"
        excel_path = os.path.join(app.config["UPLOAD_FOLDER"], excel_filename)
        generate_flowchart_excel(flowchart_result, excel_path)

        if not flowchart_result.get("success"):
            return jsonify(
                {
                    "success": False,
                    "error": "流程图识别失败，未解析到有效流程节点",
                    "batch_id": batch_id,
                    "results": flowchart_result,
                    "result_files": {"json": result_filename, "excel": excel_filename},
                }
            ), 500

        return jsonify(
            {
                "success": True,
                "message": "流程图识别完成",
                "batch_id": batch_id,
                "columns": FLOWCHART_COLUMNS,
                "results": flowchart_result,
                "result_files": {"json": result_filename, "excel": excel_filename},
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": f"流程图识别失败: {str(exc)}"}), 500


@ocr_bp.route("/api/flowchart/word/process", methods=["POST"])
def start_word_flowchart_process():
    batch_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex
    use_sample = request.form.get("use_sample", "").lower() == "true"

    if use_sample:
        if not os.path.exists(DEFAULT_WORD_FLOWCHART_DOC):
            return jsonify({"success": False, "error": "默认Word示例文件不存在"}), 404
        document_path = DEFAULT_WORD_FLOWCHART_DOC
        original_filename = os.path.basename(DEFAULT_WORD_FLOWCHART_DOC)
    else:
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"success": False, "error": "请选择Word文档"}), 400
        if not is_docx_file(file.filename):
            return jsonify({"success": False, "error": "仅支持DOCX格式Word文档"}), 400

        original_filename = file.filename
        document_path = os.path.join(app.config["UPLOAD_FOLDER"], f"word_flowchart_{batch_id}.docx")
        file.save(document_path)

    task = {
        "success": True,
        "task_id": task_id,
        "batch_id": batch_id,
        "status": "queued",
        "message": "任务已创建，等待提取图片",
        "document": {
            "original_filename": original_filename,
            "filename": os.path.basename(document_path),
        },
        "total_images": 0,
        "selected_images": 0,
        "skipped_images": 0,
        "processed_images": 0,
        "successful_images": 0,
        "failed_images": 0,
        "total_rows": 0,
        "files": [],
        "result_files": {},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _set_word_flowchart_task(task_id, task)

    thread = threading.Thread(
        target=_run_word_flowchart_prepare_task,
        args=(task_id, batch_id, document_path, original_filename),
        daemon=True,
    )
    thread.start()

    return jsonify(
        {
            "success": True,
            "message": "Word流程图图片提取任务已启动",
            "task_id": task_id,
            "batch_id": batch_id,
        }
    )


@ocr_bp.route("/api/flowchart/word/start/<task_id>", methods=["POST"])
def start_selected_word_flowchart_images(task_id):
    task = _get_word_flowchart_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    if task.get("status") in {"queued", "running", "retrying"}:
        return jsonify({"success": False, "error": "当前任务还在处理中，请稍后再开始检测"}), 400

    if task.get("status") != "ready":
        return jsonify({"success": False, "error": "当前任务已开始处理，请重新提取图片后再选择检测范围"}), 400

    data = request.get_json(silent=True) or {}
    selected_entries, missing_images = _build_selected_word_entries(
        task,
        image_indices=data.get("image_indices"),
        filenames=data.get("filenames"),
    )

    if missing_images:
        return jsonify({"success": False, "error": f"选中的图片文件不存在: {', '.join(missing_images[:3])}"}), 400

    if not selected_entries:
        return jsonify({"success": False, "error": "请至少勾选一张图片后再开始检测"}), 400

    if not _prepare_word_flowchart_selected_start(task_id, selected_entries):
        return jsonify({"success": False, "error": "当前任务状态已变化，请刷新状态后重试"}), 400

    thread = threading.Thread(
        target=_run_word_flowchart_selected_task,
        args=(task_id, selected_entries),
        daemon=True,
    )
    thread.start()

    return jsonify(
        {
            "success": True,
            "message": f"已开始识别 {len(selected_entries)} 张已勾选图片",
            "task_id": task_id,
            "batch_id": task.get("batch_id"),
            "selected_images": len(selected_entries),
        }
    )


@ocr_bp.route("/api/flowchart/word/status/<task_id>")
def get_word_flowchart_status(task_id):
    task = _get_word_flowchart_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404
    return jsonify(task)


@ocr_bp.route("/api/flowchart/word/retry/<task_id>", methods=["POST"])
def retry_word_flowchart_failed_images(task_id):
    task = _get_word_flowchart_task(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    if task.get("status") in {"queued", "running", "retrying"}:
        return jsonify({"success": False, "error": "当前任务还在处理中，请完成后再重试"}), 400

    failed_files = _get_failed_word_files(task)
    if not failed_files:
        return jsonify({"success": False, "error": "当前任务没有失败图片需要重试"}), 400

    retry_entries, missing_results = _build_word_retry_entries(task, failed_files)
    if not retry_entries:
        _apply_missing_word_retry_results(task_id, missing_results)
        return jsonify({"success": False, "error": "失败图片文件不存在，无法重试"}), 400

    _prepare_word_flowchart_retry(task_id, retry_entries, missing_results)
    thread = threading.Thread(
        target=_run_word_flowchart_retry_task,
        args=(task_id, retry_entries),
        daemon=True,
    )
    thread.start()

    return jsonify(
        {
            "success": True,
            "message": f"已开始重试 {len(retry_entries)} 张失败图片",
            "task_id": task_id,
            "batch_id": task.get("batch_id"),
            "retry_images": len(retry_entries),
            "missing_images": len(missing_results),
        }
    )


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


@ocr_bp.route("/api/ocr/process-custom", methods=["POST"])
def process_ocr_with_file_upload():
    """
    商机页面专用OCR接口 - 支持直接文件上传和OCR识别
    """
    if "file" not in request.files:
        return jsonify({"success": False, "error": "缺少文件参数"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "没有选择文件"}), 400

    # 获取参数
    engine = request.form.get("engine", "auto")
    prompt = request.form.get("prompt", "请识别图片中的所有文字内容，按原样输出。")

    try:
        # 保存上传的文件
        original_filename = file.filename
        file_ext = os.path.splitext(original_filename)[1].lower()
        file_ext = file_ext[1:] if file_ext else "png"
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)

        # 预处理图片
        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990, max_size=2048)

        # 根据引擎选择处理方式
        if engine == "paddleocr":
            # 使用PaddleOCR
            results = ocr_processor.process_image_with_engine(preprocessed_path, "paddleocr")
        elif engine == "auto":
            # 自动选择：优先使用PaddleOCR（本地、快速、免费）
            results = ocr_processor.process_image(preprocessed_path)
        else:
            # 默认使用当前配置的引擎
            results = ocr_processor.process_image(preprocessed_path, prompt)

        # 提取识别的文字
        raw_text = ""
        if results.get("success") and results.get("text_items"):
            raw_text = "\n".join(item.get("text", "") for item in results.get("text_items", []))

        return jsonify({
            "success": True,
            "message": "OCR识别成功",
            "filename": unique_filename,
            "original_filename": original_filename,
            "engine": results.get("ocr_engine", engine),
            "raw_text": raw_text,
            "results": results,
            "total_items": results.get("total_items", 0)
        })

    except Exception as exc:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[ERROR] OCR识别失败: {error_detail}")
        return jsonify({
            "success": False,
            "error": f"OCR识别失败: {str(exc)}"
        }), 500


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


@ocr_bp.route("/api/flowchart/download/excel/<batch_id>")
def download_flowchart_excel(batch_id):
    if not _is_safe_batch_id(batch_id):
        return jsonify({"error": "批次ID不合法"}), 400

    excel_path = os.path.join(app.config["UPLOAD_FOLDER"], f"result_flowchart_{batch_id}.xlsx")
    if not os.path.exists(excel_path):
        return jsonify({"error": "流程图Excel文件不存在"}), 404
    return send_file(excel_path, as_attachment=True, download_name=f"flowchart_result_{batch_id}.xlsx")


@ocr_bp.route("/api/flowchart/download/json/<batch_id>")
def download_flowchart_json(batch_id):
    if not _is_safe_batch_id(batch_id):
        return jsonify({"error": "批次ID不合法"}), 400

    json_path = os.path.join(app.config["UPLOAD_FOLDER"], f"result_flowchart_{batch_id}.json")
    if not os.path.exists(json_path):
        return jsonify({"error": "流程图JSON文件不存在"}), 404
    return send_file(json_path, as_attachment=True, download_name=f"flowchart_result_{batch_id}.json")


@ocr_bp.route("/api/flowchart/word/download/excel/<batch_id>")
def download_word_flowchart_excel(batch_id):
    if not _is_safe_batch_id(batch_id):
        return jsonify({"error": "批次ID不合法"}), 400

    excel_path = os.path.join(app.config["UPLOAD_FOLDER"], f"result_word_flowchart_{batch_id}.xlsx")
    if not os.path.exists(excel_path):
        return jsonify({"error": "Word流程图Excel文件不存在"}), 404
    return send_file(excel_path, as_attachment=True, download_name=f"word_flowchart_result_{batch_id}.xlsx")


@ocr_bp.route("/api/flowchart/word/download/json/<batch_id>")
def download_word_flowchart_json(batch_id):
    if not _is_safe_batch_id(batch_id):
        return jsonify({"error": "批次ID不合法"}), 400

    json_path = os.path.join(app.config["UPLOAD_FOLDER"], f"result_word_flowchart_{batch_id}.json")
    if not os.path.exists(json_path):
        return jsonify({"error": "Word流程图JSON文件不存在"}), 404
    return send_file(json_path, as_attachment=True, download_name=f"word_flowchart_result_{batch_id}.json")


@ocr_bp.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@ocr_bp.route("/uploads/<path:subpath>")
def uploaded_file_subpath(subpath):
    return send_from_directory(app.config["UPLOAD_FOLDER"], subpath)


@ocr_bp.route("/api/pdf/images/list/<filename>")
def get_pdf_images_list(filename):
    """获取PDF的预览图列表"""
    try:
        pdf_base_name = os.path.splitext(filename)[0]
        images_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"images_{pdf_base_name}")

        if not os.path.exists(images_dir):
            return jsonify({"success": False, "error": "预览图尚未生成"}), 404

        images = []
        for img_file in sorted(os.listdir(images_dir)):
            if img_file.endswith(('.png', '.jpg', '.jpeg')):
                images.append({
                    "url": f"/uploads/images_{pdf_base_name}/{img_file}",
                    "filename": img_file
                })
        return jsonify({"success": True, "images": images})

    except Exception as e:
        logger.error(f"获取PDF图像列表失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


def _run_word_flowchart_prepare_task(task_id, batch_id, document_path, original_filename):
    try:
        _update_word_flowchart_task(task_id, status="running", message="正在提取Word中的流程图图片")
        image_entries = extract_docx_images(
            document_path,
            app.config["UPLOAD_FOLDER"],
            batch_id,
            original_filename,
        )

        if not image_entries:
            raise ValueError("Word文档中未提取到可识别的图片")

        _update_word_flowchart_task(
            task_id,
            status="ready",
            total_images=len(image_entries),
            selected_images=len(image_entries),
            skipped_images=0,
            files=[_build_pending_word_file(entry, selected=True) for entry in image_entries],
            message=f"已提取 {len(image_entries)} 张图片，请勾选需要识别的图片后点击开始检测",
        )
    except Exception as exc:
        _update_word_flowchart_task(
            task_id,
            status="failed",
            success=False,
            message=f"Word流程图图片提取失败: {str(exc)}",
            error=str(exc),
        )


def _run_word_flowchart_selected_task(task_id, selected_entries):
    started_at = time.time()
    task_before_start = _get_word_flowchart_task(task_id)
    if not task_before_start:
        return

    batch_id = task_before_start.get("batch_id")
    document = task_before_start.get("document", {})

    try:
        def on_file_processed(file_result):
            _update_word_file_progress(task_id, file_result)

        flowchart_result = process_flowchart_images(
            selected_entries,
            ocr_processor,
            progress_callback=on_file_processed,
        )
        flowchart_result["batch_id"] = batch_id

        task_after_start = _get_word_flowchart_task(task_id)
        files = task_after_start.get("files", []) if task_after_start else flowchart_result.get("files", [])
        processing_time = round(time.time() - started_at, 2)
        word_result = _build_word_flowchart_result(
            batch_id=batch_id,
            document=document,
            rows=flowchart_result.get("rows", []),
            files=files,
            processing_time=processing_time,
            processing_info={
                **flowchart_result.get("processing_info", {}),
                "source_type": "word_docx",
                "document_filename": document.get("original_filename", ""),
                "selected_images": len(selected_entries),
            },
        )
        successful_images = word_result["stats"]["successful_images"]
        failed_images = word_result["stats"]["failed_images"]
        skipped_images = word_result["stats"]["skipped_images"]
        result_files = _save_word_flowchart_result(word_result, batch_id)

        _update_word_flowchart_task(
            task_id,
            status="completed",
            message=f"处理完成：成功 {successful_images} 张，失败 {failed_images} 张，未选择 {skipped_images} 张",
            processed_images=successful_images + failed_images,
            selected_images=word_result["stats"]["selected_images"],
            skipped_images=word_result["stats"]["skipped_images"],
            successful_images=successful_images,
            failed_images=failed_images,
            total_rows=word_result["total_rows"],
            files=word_result["files"],
            result_files=result_files,
            results={
                "rows": word_result["rows"],
                "total_rows": word_result["total_rows"],
                "stats": word_result["stats"],
            },
        )
    except Exception as exc:
        _mark_word_selected_failed(task_id, selected_entries, exc)


def _run_word_flowchart_retry_task(task_id, retry_entries):
    started_at = time.time()
    task_before_retry = _get_word_flowchart_task(task_id)
    if not task_before_retry:
        return

    batch_id = task_before_retry.get("batch_id")
    document = task_before_retry.get("document", {})
    retry_filenames = {entry.get("filename") for entry in retry_entries if entry.get("filename")}
    existing_rows = task_before_retry.get("results", {}).get("rows", [])

    try:
        def on_file_processed(file_result):
            _update_word_file_progress(task_id, file_result)

        retry_result = process_flowchart_images(
            retry_entries,
            ocr_processor,
            progress_callback=on_file_processed,
        )

        task_after_retry = _get_word_flowchart_task(task_id)
        files = task_after_retry.get("files", []) if task_after_retry else []
        retry_rows = retry_result.get("rows", [])
        merged_rows = _merge_word_flowchart_rows(existing_rows, retry_rows, retry_entries)
        previous_time = _safe_float(task_before_retry.get("results", {}).get("stats", {}).get("processing_time"))
        total_processing_time = round(previous_time + (time.time() - started_at), 2)

        word_result = _build_word_flowchart_result(
            batch_id=batch_id,
            document=document,
            rows=merged_rows,
            files=files,
            processing_time=total_processing_time,
            processing_info={
                **retry_result.get("processing_info", {}),
                "source_type": "word_docx",
                "document_filename": document.get("original_filename", ""),
                "retry_images": len(retry_entries),
            },
        )
        result_files = _save_word_flowchart_result(word_result, batch_id)

        retry_success_count = len(
            [
                file_result
                for file_result in word_result["files"]
                if file_result.get("filename") in retry_filenames and file_result.get("success")
            ]
        )
        failed_images = word_result["stats"]["failed_images"]
        _update_word_flowchart_task(
            task_id,
            status="completed",
            message=f"重试完成：本次成功 {retry_success_count} 张，仍失败 {failed_images} 张",
            success=word_result["success"],
            error="",
            processed_images=word_result["stats"]["successful_images"] + failed_images,
            selected_images=word_result["stats"]["selected_images"],
            skipped_images=word_result["stats"]["skipped_images"],
            successful_images=word_result["stats"]["successful_images"],
            failed_images=failed_images,
            total_rows=word_result["total_rows"],
            files=word_result["files"],
            result_files=result_files,
            results={
                "rows": word_result["rows"],
                "total_rows": word_result["total_rows"],
                "stats": word_result["stats"],
            },
        )
    except Exception as exc:
        _mark_word_retry_failed(task_id, retry_entries, exc)


def _get_failed_word_files(task):
    return [
        file_result
        for file_result in task.get("files", [])
        if file_result.get("success") is False or file_result.get("status") == "failed"
    ]


def _build_selected_word_entries(task, image_indices=None, filenames=None):
    upload_folder = app.config["UPLOAD_FOLDER"]
    document_name = task.get("document", {}).get("original_filename", "")
    if not isinstance(image_indices, (list, tuple, set)):
        image_indices = []
    if not isinstance(filenames, (list, tuple, set)):
        filenames = []
    selected_indices = {
        _safe_int(image_index)
        for image_index in (image_indices or [])
        if _safe_int(image_index) is not None
    }
    selected_filenames = {
        os.path.basename(str(filename))
        for filename in (filenames or [])
        if filename
    }
    selected_entries = []
    missing_images = []

    for file_result in task.get("files", []):
        filename = os.path.basename(str(file_result.get("filename") or ""))
        image_index = _safe_int(file_result.get("image_index"))
        if not filename:
            continue

        is_selected = filename in selected_filenames or image_index in selected_indices
        if not is_selected:
            continue

        image_path = os.path.join(upload_folder, filename)
        if not os.path.exists(image_path):
            missing_images.append(filename)
            continue

        selected_entries.append(
            {
                "filename": filename,
                "original_filename": file_result.get("original_filename") or filename,
                "path": image_path,
                "image_index": file_result.get("image_index"),
                "source_document": file_result.get("source_document") or document_name,
            }
        )

    return selected_entries, missing_images


def _prepare_word_flowchart_selected_start(task_id, selected_entries):
    selected_filenames = {entry["filename"] for entry in selected_entries}

    with WORD_FLOWCHART_TASK_LOCK:
        task = WORD_FLOWCHART_TASKS.get(task_id)
        if not task or task.get("status") != "ready":
            return False

        for file_result in task.get("files", []):
            filename = file_result.get("filename")
            if filename in selected_filenames:
                file_result.update(
                    {
                        "status": "running",
                        "success": None,
                        "selected": True,
                        "total_rows": 0,
                        "processing_time": "",
                        "error": "正在识别",
                    }
                )
            else:
                file_result.update(
                    {
                        "status": "skipped",
                        "success": None,
                        "selected": False,
                        "total_rows": 0,
                        "processing_time": "",
                        "error": "",
                    }
                )

        _sync_word_task_file_counts(task)
        task["status"] = "running"
        task["success"] = True
        task["error"] = ""
        task["message"] = f"正在识别 {len(selected_entries)} 张已勾选图片"
        task["result_files"] = {}
        task["results"] = {
            "rows": [],
            "total_rows": 0,
            "stats": {},
        }
        task["updated_at"] = datetime.now().isoformat()
        return True


def _build_word_retry_entries(task, failed_files):
    upload_folder = app.config["UPLOAD_FOLDER"]
    document_name = task.get("document", {}).get("original_filename", "")
    retry_entries = []
    missing_results = []

    for file_result in failed_files:
        filename = os.path.basename(str(file_result.get("filename") or ""))
        if not filename:
            missing_results.append(
                {
                    **file_result,
                    "success": False,
                    "status": "failed",
                    "error": "图片文件名缺失，无法重试",
                }
            )
            continue

        image_path = os.path.join(upload_folder, filename)
        if not os.path.exists(image_path):
            missing_results.append(
                {
                    **file_result,
                    "filename": filename,
                    "success": False,
                    "status": "failed",
                    "total_rows": 0,
                    "error": "图片文件不存在，无法重试",
                }
            )
            continue

        retry_entries.append(
            {
                "filename": filename,
                "original_filename": file_result.get("original_filename") or filename,
                "path": image_path,
                "image_index": file_result.get("image_index"),
                "source_document": file_result.get("source_document") or document_name,
            }
        )

    return retry_entries, missing_results


def _prepare_word_flowchart_retry(task_id, retry_entries, missing_results):
    retry_filenames = {entry["filename"] for entry in retry_entries}
    missing_by_filename = {item.get("filename"): item for item in missing_results if item.get("filename")}

    with WORD_FLOWCHART_TASK_LOCK:
        task = WORD_FLOWCHART_TASKS.get(task_id)
        if not task:
            return

        for file_result in task.get("files", []):
            filename = file_result.get("filename")
            if filename in retry_filenames:
                file_result.update(
                    {
                        "status": "running",
                        "success": None,
                        "total_rows": 0,
                        "processing_time": "",
                        "error": "正在重试",
                    }
                )
            elif filename in missing_by_filename:
                file_result.update(missing_by_filename[filename])

        _sync_word_task_file_counts(task)
        task["status"] = "retrying"
        task["success"] = True
        task["error"] = ""
        task["message"] = f"正在重试 {len(retry_entries)} 张失败图片"
        task["updated_at"] = datetime.now().isoformat()


def _apply_missing_word_retry_results(task_id, missing_results):
    if not missing_results:
        return

    with WORD_FLOWCHART_TASK_LOCK:
        task = WORD_FLOWCHART_TASKS.get(task_id)
        if not task:
            return

        missing_by_filename = {item.get("filename"): item for item in missing_results if item.get("filename")}
        for file_result in task.get("files", []):
            missing_result = missing_by_filename.get(file_result.get("filename"))
            if missing_result:
                file_result.update(missing_result)

        _sync_word_task_file_counts(task)
        task["message"] = "失败图片文件不存在，无法重试"
        task["updated_at"] = datetime.now().isoformat()


def _mark_word_selected_failed(task_id, selected_entries, exc):
    error_message = f"批量识别失败: {str(exc)}"
    for entry in selected_entries:
        _update_word_file_progress(
            task_id,
            {
                "success": False,
                "filename": entry.get("filename"),
                "original_filename": entry.get("original_filename"),
                "image_url": f"/uploads/{entry.get('filename')}",
                "image_index": entry.get("image_index"),
                "source_document": entry.get("source_document"),
                "rows": [],
                "total_rows": 0,
                "processing_time": "",
                "error": error_message,
            },
        )

    task = _get_word_flowchart_task(task_id)
    if not task:
        return

    batch_id = task.get("batch_id")
    word_result = _build_word_flowchart_result(
        batch_id=batch_id,
        document=task.get("document", {}),
        rows=[],
        files=task.get("files", []),
        processing_time=0,
        processing_info={
            "source_type": "word_docx",
            "document_filename": task.get("document", {}).get("original_filename", ""),
            "selected_images": len(selected_entries),
        },
    )
    result_files = _save_word_flowchart_result(word_result, batch_id) if batch_id else {}

    _update_word_flowchart_task(
        task_id,
        status="completed",
        message=error_message,
        success=word_result["success"],
        error=str(exc),
        processed_images=word_result["stats"]["successful_images"] + word_result["stats"]["failed_images"],
        selected_images=word_result["stats"]["selected_images"],
        skipped_images=word_result["stats"]["skipped_images"],
        successful_images=word_result["stats"]["successful_images"],
        failed_images=word_result["stats"]["failed_images"],
        total_rows=word_result["total_rows"],
        files=word_result["files"],
        result_files=result_files,
        results={
            "rows": word_result["rows"],
            "total_rows": word_result["total_rows"],
            "stats": word_result["stats"],
        },
    )


def _mark_word_retry_failed(task_id, retry_entries, exc):
    error_message = f"重试失败: {str(exc)}"
    for entry in retry_entries:
        _update_word_file_progress(
            task_id,
            {
                "success": False,
                "filename": entry.get("filename"),
                "original_filename": entry.get("original_filename"),
                "image_url": f"/uploads/{entry.get('filename')}",
                "image_index": entry.get("image_index"),
                "source_document": entry.get("source_document"),
                "rows": [],
                "total_rows": 0,
                "processing_time": "",
                "error": error_message,
            },
        )

    task = _get_word_flowchart_task(task_id)
    if not task:
        return

    batch_id = task.get("batch_id")
    rows = task.get("results", {}).get("rows", [])
    word_result = _build_word_flowchart_result(
        batch_id=batch_id,
        document=task.get("document", {}),
        rows=rows,
        files=task.get("files", []),
        processing_time=_safe_float(task.get("results", {}).get("stats", {}).get("processing_time")),
        processing_info={
            "source_type": "word_docx",
            "document_filename": task.get("document", {}).get("original_filename", ""),
        },
    )
    result_files = _save_word_flowchart_result(word_result, batch_id) if batch_id else task.get("result_files", {})

    _update_word_flowchart_task(
        task_id,
        status="completed",
        message=f"{error_message}，原有成功结果已保留",
        success=word_result["success"],
        error=str(exc),
        processed_images=word_result["stats"]["successful_images"] + word_result["stats"]["failed_images"],
        selected_images=word_result["stats"]["selected_images"],
        skipped_images=word_result["stats"]["skipped_images"],
        successful_images=word_result["stats"]["successful_images"],
        failed_images=word_result["stats"]["failed_images"],
        total_rows=word_result["total_rows"],
        files=word_result["files"],
        result_files=result_files,
        results={
            "rows": word_result["rows"],
            "total_rows": word_result["total_rows"],
            "stats": word_result["stats"],
        },
    )


def _build_word_flowchart_result(batch_id, document, rows, files, processing_time, processing_info=None):
    document = document or {}
    normalized_files = _sort_word_files(files or [])
    normalized_rows = _sort_word_rows(rows or [])
    successful_images = len([file_result for file_result in normalized_files if file_result.get("success")])
    failed_images = len([file_result for file_result in normalized_files if file_result.get("success") is False])
    skipped_images = len(
        [
            file_result
            for file_result in normalized_files
            if file_result.get("status") == "skipped" or file_result.get("selected") is False
        ]
    )
    selected_images = max(len(normalized_files) - skipped_images, 0)
    info = dict(processing_info or {})
    info.setdefault("source_type", "word_docx")
    info.setdefault("document_filename", document.get("original_filename", ""))

    return {
        "success": bool(successful_images),
        "batch_id": batch_id,
        "source_type": "word_docx",
        "document": document,
        "rows": normalized_rows,
        "total_rows": len(normalized_rows),
        "files": normalized_files,
        "stats": {
            "image_count": len(normalized_files),
            "selected_images": selected_images,
            "skipped_images": skipped_images,
            "processed_images": successful_images + failed_images,
            "successful_images": successful_images,
            "failed_images": failed_images,
            "total_rows": len(normalized_rows),
            "processing_time": round(_safe_float(processing_time), 2),
        },
        "processing_info": info,
    }


def _save_word_flowchart_result(word_result, batch_id):
    json_filename = f"result_word_flowchart_{batch_id}.json"
    json_path = os.path.join(app.config["UPLOAD_FOLDER"], json_filename)
    with open(json_path, "w", encoding="utf-8") as file_obj:
        json.dump(word_result, file_obj, ensure_ascii=False, indent=2)

    excel_filename = f"result_word_flowchart_{batch_id}.xlsx"
    excel_path = os.path.join(app.config["UPLOAD_FOLDER"], excel_filename)
    generate_word_flowchart_excel(word_result, excel_path)

    return {"json": json_filename, "excel": excel_filename}


def _merge_word_flowchart_rows(existing_rows, retry_rows, retry_entries):
    retry_filenames = {entry.get("filename") for entry in retry_entries if entry.get("filename")}
    retry_indices = {
        _safe_int(entry.get("image_index"))
        for entry in retry_entries
        if _safe_int(entry.get("image_index")) is not None
    }
    kept_rows = []

    for row in existing_rows or []:
        row_filename = row.get("图片文件")
        row_index = _safe_int(row.get("图片序号"))
        if row_filename in retry_filenames:
            continue
        if row_index in retry_indices:
            continue
        kept_rows.append(row)

    return _sort_word_rows(kept_rows + (retry_rows or []))


def _build_pending_word_file(entry, selected=True):
    return {
        "image_index": entry.get("image_index"),
        "filename": entry.get("filename"),
        "original_filename": entry.get("original_filename"),
        "image_url": f"/uploads/{entry.get('filename')}",
        "source_document": entry.get("source_document"),
        "status": "pending" if selected else "skipped",
        "selected": bool(selected),
        "success": None,
        "total_rows": 0,
        "processing_time": "",
        "error": "",
    }


def _update_word_file_progress(task_id, file_result):
    with WORD_FLOWCHART_TASK_LOCK:
        task = WORD_FLOWCHART_TASKS.get(task_id)
        if not task:
            return

        files = task.get("files", [])
        target_file = None
        for item in files:
            if item.get("filename") == file_result.get("filename"):
                target_file = item
                break

        if target_file is None:
            target_file = _build_pending_word_file(file_result)
            files.append(target_file)
            task["files"] = files

        success = bool(file_result.get("success"))
        target_file.update(
            {
                "status": "success" if success else "failed",
                "success": success,
                "selected": True,
                "total_rows": file_result.get("total_rows", 0),
                "processing_time": file_result.get("processing_time", ""),
                "error": "" if success else file_result.get("error", "识别失败"),
            }
        )

        _sync_word_task_file_counts(task)
        selected_total = task.get("selected_images") or task.get("total_images", 0)
        task["message"] = f"正在识别：{task['processed_images']}/{selected_total}"
        task["updated_at"] = datetime.now().isoformat()


def _sync_word_task_file_counts(task):
    files = task.get("files", [])
    processed_files = [item for item in files if item.get("status") in {"success", "failed"}]
    skipped_files = [item for item in files if item.get("status") == "skipped" or item.get("selected") is False]
    selected_files = [
        item
        for item in files
        if not (item.get("status") == "skipped" or item.get("selected") is False)
    ]
    task["selected_images"] = len(selected_files)
    task["skipped_images"] = len(skipped_files)
    task["processed_images"] = len(processed_files)
    task["successful_images"] = len([item for item in processed_files if item.get("success")])
    task["failed_images"] = len([item for item in processed_files if item.get("success") is False])
    task["total_rows"] = sum(_safe_int(item.get("total_rows")) or 0 for item in processed_files)


def _sort_word_files(files):
    return sorted(
        [dict(file_result) for file_result in files],
        key=lambda file_result: (
            _safe_int(file_result.get("image_index")) or 10**9,
            str(file_result.get("original_filename") or file_result.get("filename") or ""),
        ),
    )


def _sort_word_rows(rows):
    indexed_rows = [(index, dict(row)) for index, row in enumerate(rows)]
    indexed_rows.sort(
        key=lambda item: (
            _safe_int(item[1].get("图片序号")) or 10**9,
            item[0],
        )
    )
    return [row for _, row in indexed_rows]


def _safe_int(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value):
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _set_word_flowchart_task(task_id, task):
    with WORD_FLOWCHART_TASK_LOCK:
        WORD_FLOWCHART_TASKS[task_id] = task


def _update_word_flowchart_task(task_id, **updates):
    with WORD_FLOWCHART_TASK_LOCK:
        task = WORD_FLOWCHART_TASKS.get(task_id)
        if not task:
            return
        task.update(updates)
        task["updated_at"] = datetime.now().isoformat()


def _get_word_flowchart_task(task_id):
    with WORD_FLOWCHART_TASK_LOCK:
        task = WORD_FLOWCHART_TASKS.get(task_id)
        return copy.deepcopy(task) if task else None


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

        # 生成标注图片（与 /api/process/custom 保持一致）
        result_image_base64 = None
        text_items = results.get("text_items", [])
        draw_source = preprocessed_path if os.path.exists(preprocessed_path) else filepath
        if os.path.exists(draw_source) and text_items:
            try:
                result_image_base64 = draw_ocr_boxes(draw_source, text_items)
            except Exception as draw_err:
                print(f"[WARN] 绘制标注框失败: {draw_err}")

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
        if result_image_base64:
            response["result_image"] = result_image_base64

        return jsonify(response)
    except Exception as exc:
        return jsonify({"error": f"图片处理失败: {str(exc)}"}), 500


def process_pdf_file(filename, filepath, data):
    try:
        pdf_engine = (data.get("pdf_engine") or Config.PDF_ENGINE or "ocr").strip().lower()
        if pdf_engine not in {"ocr", "mineru", "paddleocr_vl"}:
            return jsonify({"success": False, "error": f"不支持的PDF解析方式: {pdf_engine}", "file_type": "pdf"}), 400

        if pdf_engine == "ocr" and not pdf_processor.initialized:
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

        if pdf_engine == "mineru":
            pdf_info = pdf_processor._get_pdf_info(filepath)
            mineru_processor = create_mineru_processor(
                api_url=Config.MINERU_API_URL,
                api_key=Config.MINERU_API_KEY,
                model=Config.MINERU_MODEL,
                timeout=Config.MINERU_TIMEOUT,
                request_mode=Config.MINERU_REQUEST_MODE,
                official_token=Config.MINERU_OFFICIAL_TOKEN,
            )
            pdf_result = mineru_processor.process_pdf(
                filepath,
                pdf_info=pdf_info,
                max_pages=max_pages,
                output_dir=images_dir,
                dpi=dpi,
            )
            if not pdf_result.get("conversion_info", {}).get("image_paths"):
                _render_pdf_preview_images(filepath, images_dir, dpi, max_pages, pdf_result)
        elif pdf_engine == "paddleocr_vl":
            from paddleocr_vl_processor import create_paddleocr_vl_processor
            paddleocr_vl_processor = create_paddleocr_vl_processor(
                api_url=Config.PADDLEOCR_ONLINE_API_URL,
                token=Config.PADDLEOCR_ONLINE_TOKEN,
            )
            if not paddleocr_vl_processor:
                return jsonify({"success": False, "error": "PaddleOCR-VL 未配置 token"}), 500

            # 获取模型参数，默认 PaddleOCR-VL-1.6
            model = data.get("paddleocr_model", "PaddleOCR-VL-1.6")
            pdf_result = paddleocr_vl_processor.process_pdf(filepath, model=model, max_pages=max_pages)
        else:
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

        # PaddleOCR-VL 不生成 Excel（格式不兼容）
        if pdf_engine != "paddleocr_vl":
            excel_filename = f"result_{pdf_base_name}.xlsx"
            excel_path = os.path.join(app.config["UPLOAD_FOLDER"], excel_filename)
            generate_pdf_excel(pdf_result, excel_path)
        else:
            excel_filename = None

        # PaddleOCR-VL 单独保存 Markdown 文件
        if pdf_engine == "paddleocr_vl" and pdf_result.get("markdown"):
            markdown_filename = f"result_{pdf_base_name}.md"
            markdown_path = os.path.join(app.config["UPLOAD_FOLDER"], markdown_filename)
            with open(markdown_path, "w", encoding="utf-8") as md_file:
                md_file.write(pdf_result["markdown"])

        if "conversion_info" in pdf_result and "image_paths" in pdf_result["conversion_info"]:
            relative_image_paths = []
            for img_path in pdf_result["conversion_info"]["image_paths"]:
                if os.path.exists(img_path):
                    relative_image_paths.append(os.path.relpath(img_path, app.config["UPLOAD_FOLDER"]))
            pdf_result["conversion_info"]["relative_image_paths"] = relative_image_paths

        result_files = {"json": result_filename}
        if excel_filename:
            result_files["excel"] = excel_filename

        return jsonify(
            {
                "success": True,
                "message": "PDF处理成功",
                "filename": filename,
                "file_type": "pdf",
                "pdf_engine": pdf_engine,
                "results": pdf_result,
                "result_files": result_files,
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


def _is_safe_batch_id(batch_id):
    return bool(batch_id) and all(char.isalnum() or char in "-_" for char in batch_id)


def _render_pdf_preview_images(filepath, images_dir, dpi, max_pages, pdf_result):
    if not pdf_result.get("success") or not pdf_processor.initialized:
        return

    actual_pages = pdf_result.get("processing_info", {}).get("actual_pages_processed") or max_pages
    actual_pages = max(1, min(int(actual_pages), int(max_pages)))
    preview_result = pdf_processor.convert_pdf_to_images(
        filepath,
        dpi=dpi,
        first_page=1,
        last_page=actual_pages,
        output_dir=images_dir,
    )
    if preview_result.get("success"):
        pdf_result["conversion_info"].update(preview_result.get("conversion_info", {}))
        pdf_result["conversion_info"]["image_paths"] = preview_result.get("image_paths", [])

