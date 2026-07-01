"""
Whisper 语音转字幕路由
"""

import os
import uuid
import json
import threading
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file

from app_core import app
from whisper_processor import whisper_processor
from ai_summary_processor import ai_summary_processor


whisper_bp = Blueprint("whisper", __name__, url_prefix="/api/whisper")

WHISPER_TASKS = {}
WHISPER_TASK_LOCK = threading.Lock()


@whisper_bp.route("/status", methods=["GET"])
def get_whisper_status():
    """获取 Whisper 状态"""
    status = whisper_processor.get_status()
    return jsonify({"success": True, "status": status})


@whisper_bp.route("/upload/init", methods=["POST"])
def upload_init():
    """初始化分片上传会话"""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "缺少请求参数"}), 400

    original_filename = data.get("filename", "")
    total_chunks = data.get("totalChunks", 0)

    if not original_filename:
        return jsonify({"success": False, "error": "缺少文件名"}), 400
    if total_chunks <= 0:
        return jsonify({"success": False, "error": "分片数无效"}), 400

    file_ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
    allowed_extensions = {"mp4", "avi", "mov", "mkv", "flv", "wmv", "mp3", "wav", "m4a"}

    if file_ext not in allowed_extensions:
        return jsonify({"success": False, "error": f"不支持的文件格式"}), 400

    task_id = uuid.uuid4().hex
    safe_filename = f"whisper_{task_id}.{file_ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_filename)

    # 预创建空文件（分片写入用 r+b 模式，文件必须存在）
    with open(filepath, "wb") as f:
        f.truncate(0)  # 确保空文件

    # 创建临时进度文件，记录总分片数
    progress_path = filepath + ".chunks"
    with open(progress_path, "w") as f:
        json.dump({"total": total_chunks, "received": [], "original_filename": original_filename}, f)

    return jsonify({
        "success": True,
        "task_id": task_id,
        "chunkSize": 10 * 1024 * 1024,  # 每片 10MB
        "totalChunks": total_chunks
    })


@whisper_bp.route("/upload/chunk", methods=["POST"])
def upload_chunk():
    """接收单个分片"""
    chunk_index = request.args.get("index")
    task_id = request.args.get("task_id")

    if not chunk_index or not task_id:
        return jsonify({"success": False, "error": "缺少分片参数"}), 400

    try:
        chunk_index = int(chunk_index)
    except ValueError:
        return jsonify({"success": False, "error": "分片索引无效"}), 400

    if "chunk" not in request.files:
        return jsonify({"success": False, "error": "没有分片数据"}), 400

    # 找到对应的文件
    upload_dir = app.config["UPLOAD_FOLDER"]
    existing_files = [f for f in os.listdir(upload_dir) if f.startswith(f"whisper_{task_id}.") and not f.endswith(".chunks")]
    if not existing_files:
        return jsonify({"success": False, "error": "上传会话不存在，请先调用 /upload/init"}), 404

    target_file = os.path.join(upload_dir, existing_files[0])
    progress_path = target_file + ".chunks"

    if not os.path.exists(progress_path):
        return jsonify({"success": False, "error": "上传会话已过期"}), 404

    # 读取进度
    with open(progress_path, "r") as f:
        progress = json.load(f)

    if chunk_index in progress["received"]:
        # 已接收，幂等
        return jsonify({"success": True, "index": chunk_index, "received": len(progress["received"])})

    # 写入分片数据（追加模式）
    chunk_file = request.files["chunk"]
    CHUNK_SIZE = 10 * 1024 * 1024  # 10MB
    chunk_data = chunk_file.stream.read(CHUNK_SIZE + 1024 * 1024)  # 多读一点以防万一

    with open(target_file, "r+b") as f:
        f.seek(chunk_index * 10 * 1024 * 1024)
        f.write(chunk_data)

    # 更新进度
    progress["received"].append(chunk_index)
    with open(progress_path, "w") as f:
        json.dump(progress, f)

    return jsonify({"success": True, "index": chunk_index, "received": len(progress["received"])})


@whisper_bp.route("/upload/complete", methods=["POST"])
def upload_complete():
    """完成分片上传，合并并创建任务"""
    data = request.json
    if not data or "task_id" not in data:
        return jsonify({"success": False, "error": "缺少 task_id"}), 400

    task_id = data["task_id"]
    upload_dir = app.config["UPLOAD_FOLDER"]

    existing_files = [f for f in os.listdir(upload_dir) if f.startswith(f"whisper_{task_id}.") and not f.endswith(".chunks")]
    if not existing_files:
        return jsonify({"success": False, "error": "上传会话不存在"}), 404

    target_file = os.path.join(upload_dir, existing_files[0])
    progress_path = target_file + ".chunks"

    if not os.path.exists(progress_path):
        return jsonify({"success": False, "error": "上传会话已过期"}), 404

    with open(progress_path, "r") as f:
        progress = json.load(f)

    total = progress["total"]
    received = len(progress["received"])
    original_filename = progress.get("original_filename", existing_files[0])

    if received < total:
        return jsonify({
            "success": False,
            "error": f"分片不完整: 已收到 {received}/{total}"
        }), 400

    # 截断文件到实际大小（去掉最后一块的填充）
    file_size = data.get("fileSize", 0)
    if file_size > 0:
        with open(target_file, "r+b") as f:
            f.truncate(file_size)

    # 删除进度文件
    try:
        os.remove(progress_path)
    except OSError:
        pass

    task = {
        "task_id": task_id,
        "status": "uploaded",
        "progress": 0,
        "message": "文件已上传，等待处理",
        "original_filename": original_filename,
        "filename": existing_files[0],
        "filepath": target_file,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    with WHISPER_TASK_LOCK:
        WHISPER_TASKS[task_id] = task

    return jsonify({"success": True, "task_id": task_id, "filename": original_filename})


@whisper_bp.route("/process", methods=["POST"])
def process_video():
    """处理视频，生成字幕"""
    data = request.json
    if not data or "task_id" not in data:
        return jsonify({"success": False, "error": "缺少 task_id"}), 400

    task_id = data["task_id"]
    model_name = data.get("model", "base")
    language = data.get("language", "auto")

    with WHISPER_TASK_LOCK:
        task = WHISPER_TASKS.get(task_id)
        if not task:
            return jsonify({"success": False, "error": "任务不存在"}), 404
        if task["status"] not in ["uploaded", "failed"]:
            return jsonify({"success": False, "error": "任务正在处理中或已完成"}), 400

        task["status"] = "processing"
        task["progress"] = 10
        task["message"] = "正在处理..."
        task["model"] = model_name
        task["language"] = language
        task["updated_at"] = datetime.now().isoformat()

    thread = threading.Thread(
        target=_process_whisper_task,
        args=(task_id, task["filepath"], model_name, language),
        daemon=True
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "message": "开始处理"})


@whisper_bp.route("/task/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """获取任务状态"""
    with WHISPER_TASK_LOCK:
        task = WHISPER_TASKS.get(task_id)
        if not task:
            return jsonify({"success": False, "error": "任务不存在"}), 404
        return jsonify({"success": True, "task": task})


@whisper_bp.route("/history", methods=["GET"])
def get_history():
    """获取历史任务列表"""
    try:
        upload_dir = app.config["UPLOAD_FOLDER"]
        print(f"[DEBUG] Upload dir: {upload_dir}")
        print(f"[DEBUG] Upload dir exists: {os.path.exists(upload_dir)}")

        history_tasks = []

        # 扫描 uploads 目录查找所有 whisper_*.json 文件
        all_files = os.listdir(upload_dir)
        json_files = [f for f in all_files if f.startswith("whisper_") and f.endswith(".json")]
        print(f"[DEBUG] Found JSON files: {json_files}")

        for filename in json_files:
            json_path = os.path.join(upload_dir, filename)

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 提取 task_id
                task_id = filename.replace("whisper_", "").replace(".json", "")
                print(f"[DEBUG] Processing task_id: {task_id}")

                # 检查文件是否都存在
                base_name = f"whisper_{task_id}"
                srt_exists = os.path.exists(os.path.join(upload_dir, f"{base_name}.srt"))
                vtt_exists = os.path.exists(os.path.join(upload_dir, f"{base_name}.vtt"))
                txt_exists = os.path.exists(os.path.join(upload_dir, f"{base_name}.txt"))

                print(f"[DEBUG] SRT: {srt_exists}, VTT: {vtt_exists}, TXT: {txt_exists}")

                # 只返回完整的任务
                if srt_exists and vtt_exists:
                    print(f"[DEBUG] Task {task_id} is complete, adding to history")
                    # 查找原始视频文件
                    video_filename = None
                    for ext in ['.mp4', '.avi', '.mov', '.mkv', '.mp3', '.wav']:
                        potential_video = f"{base_name}{ext}"
                        if os.path.exists(os.path.join(upload_dir, potential_video)):
                            video_filename = potential_video
                            break

                    # 优先从 JSON 文件中获取原始文件名
                    original_filename = data.get("original_filename")

                    # 如果 JSON 中没有，尝试从内存任务中获取
                    if not original_filename:
                        with WHISPER_TASK_LOCK:
                            memory_task = WHISPER_TASKS.get(task_id)
                        if memory_task:
                            original_filename = memory_task.get("original_filename")

                    # 如果还是没有，使用视频文件名
                    if not original_filename:
                        if video_filename:
                            original_filename = video_filename
                        else:
                            original_filename = f"任务_{task_id[:8]}.mp4"

                    # 获取处理时间（JSON文件的修改时间）
                    processed_time = datetime.fromtimestamp(
                        os.path.getmtime(json_path)
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    history_tasks.append({
                        "task_id": task_id,
                        "original_filename": original_filename,
                        "filename": video_filename or f"{base_name}.mp4",
                        "status": "completed",
                        "progress": 100,
                        "message": f"处理完成 ({processed_time})",
                        "detected_language": data.get("language", "zh"),
                        "segment_count": len(data.get("segments", [])),
                        "processed_time": processed_time,
                        "files": {
                            "srt": f"{base_name}.srt",
                            "vtt": f"{base_name}.vtt",
                            "txt": f"{base_name}.txt",
                            "json": f"{base_name}.json"
                        }
                    })
                else:
                    print(f"[DEBUG] Task {task_id} is incomplete, skipping")
            except Exception as e:
                print(f"[DEBUG] Error processing {filename}: {e}")
                continue

        print(f"[DEBUG] Total history tasks: {len(history_tasks)}")

        # 按文件修改时间排序（最新的在前）
        if history_tasks:
            history_tasks.sort(key=lambda x: os.path.getmtime(
                os.path.join(upload_dir, f"whisper_{x['task_id']}.json")
            ), reverse=True)

        return jsonify({"success": True, "tasks": history_tasks})

    except Exception as e:
        print(f"[DEBUG] Exception in get_history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@whisper_bp.route("/download/<task_id>/<file_type>", methods=["GET"])
def download_subtitle(task_id, file_type):
    """下载字幕文件"""
    if file_type not in ["srt", "txt", "json", "vtt"]:
        return jsonify({"success": False, "error": "不支持的文件类型"}), 400

    # 直接构造文件路径，不依赖内存中的 task
    filename = f"whisper_{task_id}.{file_type}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.exists(filepath):
        return jsonify({"success": False, "error": "文件不存在"}), 404

    # 设置正确的 Content-Type
    if file_type == "vtt":
        mimetype = "text/vtt"
    elif file_type == "srt":
        mimetype = "text/plain"
    elif file_type == "json":
        mimetype = "application/json"
    else:
        mimetype = "text/plain"

    return send_file(filepath, as_attachment=True, download_name=filename, mimetype=mimetype)


def _process_whisper_task(task_id: str, video_path: str, model_name: str, language: str):
    """后台处理 Whisper 任务"""
    try:
        # 定义进度回调函数
        def progress_callback(progress: int, message: str):
            _update_task(task_id, progress=progress, message=message)

        # 处理视频
        result = whisper_processor.process_video(
            video_path=video_path,
            output_dir=app.config["UPLOAD_FOLDER"],
            model_name=model_name,
            language=language if language != "auto" else None,
            base_filename=f"whisper_{task_id}",
            original_filename=WHISPER_TASKS.get(task_id, {}).get("original_filename"),
            progress_callback=progress_callback
        )

        if not result["success"]:
            _update_task(
                task_id, status="failed", progress=0,
                message=f"处理失败: {result.get('error', '未知错误')}",
                error=result.get("error")
            )
            return

        # 完成
        _update_task(
            task_id, status="completed", progress=100, message="处理完成",
            text=result["text"], detected_language=result["language"],
            segment_count=result["segment_count"], files=result["files"]
        )
    except Exception as e:
        _update_task(task_id, status="failed", progress=0,
                    message=f"处理失败: {str(e)}", error=str(e))


def _update_task(task_id: str, **updates):
    """更新任务状态"""
    with WHISPER_TASK_LOCK:
        task = WHISPER_TASKS.get(task_id)
        if task:
            task.update(updates)
            task["updated_at"] = datetime.now().isoformat()


@whisper_bp.route("/ai-summary", methods=["POST"])
def generate_ai_summary():
    """生成 AI 会议纪要"""
    data = request.json
    if not data or "task_id" not in data:
        return jsonify({"success": False, "error": "缺少 task_id"}), 400

    task_id = data["task_id"]
    model = data.get("model", "gpt-4o")

    # 读取转录文本
    txt_path = os.path.join(app.config["UPLOAD_FOLDER"], f"whisper_{task_id}.txt")

    if not os.path.exists(txt_path):
        return jsonify({"success": False, "error": "转录文件不存在"}), 404

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            transcript = f.read()

        # 调用 AI 生成纪要
        result = ai_summary_processor.generate_summary(transcript, model)

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

