import base64
import os
import tempfile
import threading
import time
import traceback
import uuid

import cv2
import numpy as np
from flask import Blueprint, jsonify, request
from PIL import Image, ImageDraw, ImageFont


vision_bp = Blueprint("vision", __name__)

_face_detection_lock = threading.Lock()
_face_detection_pipeline = None

_safety_helmet_lock = threading.Lock()
_safety_helmet_pipeline = None
_HELMET_MAX_RETRIES = 3
_HELMET_RETRY_DELAY = 5

_license_ocr_lock = threading.Lock()
_license_ocr_instance = None
_LICENSE_OCR_MAX_RETRIES = 3
_LICENSE_OCR_RETRY_DELAY = 5

_keypoint_model_lock = threading.Lock()
_keypoint_model = None
_keypoint_device = None
_KEYPOINT_MAX_RETRIES = 3
_KEYPOINT_RETRY_DELAY = 5

KEYPOINT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

KEYPOINT_SKELETON = [
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (12, 14),
    (13, 15),
    (14, 16),
]

KEYPOINT_COLORS = [
    (0, 0, 255),
    (255, 0, 0),
    (0, 255, 0),
    (0, 255, 255),
    (255, 0, 255),
    (255, 255, 0),
    (128, 0, 255),
    (0, 128, 255),
    (255, 128, 0),
    (0, 255, 128),
    (128, 255, 0),
    (255, 0, 128),
    (128, 0, 0),
    (0, 0, 128),
    (0, 128, 0),
    (128, 128, 0),
    (0, 128, 128),
]


def _get_project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_chinese_font(size):
    project_root = _get_project_root()
    font_paths = [
        os.path.join(project_root, "frontend", "static", "fonts", "NotoSansSC.ttf"),
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _get_face_detection_pipeline():
    global _face_detection_pipeline
    if _face_detection_pipeline is None:
        with _face_detection_lock:
            if _face_detection_pipeline is None:
                try:
                    from modelscope.pipelines import pipeline
                    from modelscope.utils.constant import Tasks

                    _face_detection_pipeline = pipeline(
                        Tasks.face_detection,
                        model="iic/cv_resnet50_face-detection_retinaface",
                    )
                except Exception as exc:
                    print(f"[FaceDetection] 加载 RetinaFace 模型失败: {exc}")
                    _face_detection_pipeline = None
    return _face_detection_pipeline


def _init_safety_helmet_pipeline():
    global _safety_helmet_pipeline
    try:
        from modelscope.pipelines import pipeline
        from modelscope.utils.constant import Tasks

        _safety_helmet_pipeline = pipeline(
            Tasks.image_object_detection,
            model="iic/cv_tinynas_object-detection_damoyolo_safety-helmet",
            trust_remote_code=True,
        )
        print("[SafetyHelmet] DAMO-YOLO 安全帽检测模型已加载")
        return True
    except Exception as exc:
        print(f"[SafetyHelmet] 加载安全帽检测模型失败: {exc}")
        _safety_helmet_pipeline = None
        return False


def _get_safety_helmet_pipeline():
    global _safety_helmet_pipeline
    if _safety_helmet_pipeline is None:
        with _safety_helmet_lock:
            if _safety_helmet_pipeline is None:
                for attempt in range(1, _HELMET_MAX_RETRIES + 1):
                    print(f"[SafetyHelmet] 尝试初始化 (第 {attempt}/{_HELMET_MAX_RETRIES} 次)...")
                    if _init_safety_helmet_pipeline():
                        break
                    if attempt < _HELMET_MAX_RETRIES:
                        print(f"[SafetyHelmet] 等待 {_HELMET_RETRY_DELAY} 秒后重试...")
                        time.sleep(_HELMET_RETRY_DELAY)
                    else:
                        print(f"[SafetyHelmet] 初始化失败，已重试 {_HELMET_MAX_RETRIES} 次")
    return _safety_helmet_pipeline


def preload_safety_helmet():
    print("[SafetyHelmet] 正在预加载安全帽检测模型...")
    pipeline = _get_safety_helmet_pipeline()
    if pipeline is not None:
        print("[SafetyHelmet] 安全帽检测模型预加载成功")
        try:
            test_img = np.ones((100, 100, 3), dtype=np.uint8) * 255
            pipeline(test_img)
            print("[SafetyHelmet] 安全帽检测模型预热完成")
        except Exception as exc:
            print(f"[SafetyHelmet] 模型预热失败（不影响后续使用）: {exc}")
    else:
        print("[SafetyHelmet] 安全帽检测模型预加载失败，将在首次请求时重试")


def _init_license_ocr():
    global _license_ocr_instance
    try:
        from paddleocr import PaddleOCR

        _license_ocr_instance = PaddleOCR(
            lang="ch",
            ocr_version="PP-OCRv5",
            text_det_box_thresh=0.13,
            text_det_unclip_ratio=2.5,
            text_rec_score_thresh=0.1,
            use_doc_unwarping=False,
        )
        print("[LicensePlate] PaddleOCR 车牌识别模型已加载 (PP-OCRv5)")
        return True
    except Exception as exc:
        print(f"[LicensePlate] 加载 PaddleOCR 失败: {exc}")
        _license_ocr_instance = None
        return False


def _get_license_ocr():
    global _license_ocr_instance
    if _license_ocr_instance is None:
        with _license_ocr_lock:
            if _license_ocr_instance is None:
                for attempt in range(1, _LICENSE_OCR_MAX_RETRIES + 1):
                    print(f"[LicensePlate] 尝试初始化 PaddleOCR (第 {attempt}/{_LICENSE_OCR_MAX_RETRIES} 次)...")
                    if _init_license_ocr():
                        break
                    if attempt < _LICENSE_OCR_MAX_RETRIES:
                        print(f"[LicensePlate] 等待 {_LICENSE_OCR_RETRY_DELAY} 秒后重试...")
                        time.sleep(_LICENSE_OCR_RETRY_DELAY)
                    else:
                        print(f"[LicensePlate] PaddleOCR 初始化失败，已重试 {_LICENSE_OCR_MAX_RETRIES} 次")
    return _license_ocr_instance


def preload_license_ocr():
    print("[LicensePlate] 正在预加载车牌识别模型...")
    ocr = _get_license_ocr()
    if ocr is not None:
        print("[LicensePlate] 车牌识别模型预加载成功")
        try:
            test_img = np.ones((100, 100, 3), dtype=np.uint8) * 255
            ocr.predict(test_img)
            print("[LicensePlate] 车牌识别模型预热完成")
        except Exception as exc:
            print(f"[LicensePlate] 模型预热失败（不影响后续使用）: {exc}")
    else:
        print("[LicensePlate] 车牌识别模型预加载失败，将在首次请求时重试")


def _is_license_plate_text(text):
    if not text:
        return False
    text = text.strip()
    if len(text) < 6 or len(text) > 8:
        return False
    has_digit = any(char.isdigit() for char in text)
    has_alpha = any(char.isalpha() for char in text)
    if not (has_digit or has_alpha):
        return False
    province_chars = {
        "京",
        "津",
        "沪",
        "渝",
        "冀",
        "豫",
        "云",
        "辽",
        "黑",
        "湘",
        "皖",
        "鲁",
        "新",
        "苏",
        "浙",
        "赣",
        "鄂",
        "桂",
        "甘",
        "晋",
        "蒙",
        "陕",
        "吉",
        "闽",
        "贵",
        "粤",
        "川",
        "青",
        "藏",
        "琼",
        "宁",
        "港",
        "澳",
        "台",
        "使",
        "领",
    }
    if any(char in province_chars for char in text):
        return True
    return has_digit and has_alpha and len(text) >= 6


def _init_keypoint_model():
    global _keypoint_model, _keypoint_device
    try:
        import torch
        import torchvision

        _keypoint_model = torchvision.models.detection.keypointrcnn_resnet50_fpn(
            weights=torchvision.models.detection.KeypointRCNN_ResNet50_FPN_Weights.DEFAULT
        )
        _keypoint_model.eval()
        _keypoint_device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        _keypoint_model.to(_keypoint_device)
        print(f"[KeypointDetection] Keypoint R-CNN 模型已加载 (设备: {_keypoint_device})")
        return True
    except Exception as exc:
        print(f"[KeypointDetection] 加载 Keypoint R-CNN 模型失败: {exc}")
        _keypoint_model = None
        return False


def _get_keypoint_model():
    global _keypoint_model, _keypoint_device
    if _keypoint_model is None:
        with _keypoint_model_lock:
            if _keypoint_model is None:
                for attempt in range(1, _KEYPOINT_MAX_RETRIES + 1):
                    print(f"[KeypointDetection] 尝试初始化 (第 {attempt}/{_KEYPOINT_MAX_RETRIES} 次)...")
                    if _init_keypoint_model():
                        break
                    if attempt < _KEYPOINT_MAX_RETRIES:
                        print(f"[KeypointDetection] 等待 {_KEYPOINT_RETRY_DELAY} 秒后重试...")
                        time.sleep(_KEYPOINT_RETRY_DELAY)
                    else:
                        print(f"[KeypointDetection] 初始化失败，已重试 {_KEYPOINT_MAX_RETRIES} 次")
    return _keypoint_model, _keypoint_device


def preload_keypoint():
    print("[KeypointDetection] 正在预加载关键点检测模型...")
    model, device = _get_keypoint_model()
    if model is not None:
        print(f"[KeypointDetection] 关键点检测模型预加载成功 (设备: {device})")
        try:
            import torch

            test_img = np.ones((100, 100, 3), dtype=np.uint8) * 128
            img_tensor = torch.from_numpy(test_img).permute(2, 0, 1).float().div(255.0).unsqueeze(0).to(device)
            with torch.no_grad():
                model(img_tensor)
            print("[KeypointDetection] 关键点检测模型预热完成")
        except Exception as exc:
            print(f"[KeypointDetection] 模型预热失败（不影响后续使用）: {exc}")
    else:
        print("[KeypointDetection] 关键点检测模型预加载失败，将在首次请求时重试")


@vision_bp.route("/api/face_detection", methods=["POST"])
def face_detection():
    if "file" not in request.files:
        return jsonify({"error": "没有文件部分"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400

    try:
        image_bytes = file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "无法解码图片"}), 400

        img_height, img_width = img.shape[:2]
        temp_path = os.path.join(tempfile.gettempdir(), f"face_detection_{uuid.uuid4().hex}.jpg")
        cv2.imwrite(temp_path, img)

        try:
            pipeline = _get_face_detection_pipeline()
            if pipeline is not None:
                result = pipeline(temp_path)
                scores = result.get("scores", [])
                boxes = result.get("boxes", [])
                faces = []
                for index, box in enumerate(boxes):
                    if len(box) < 4:
                        continue
                    x1, y1, x2, y2 = box[:4]
                    confidence = float(scores[index]) if index < len(scores) else 0.0
                    x1 = max(0, int(x1))
                    y1 = max(0, int(y1))
                    x2 = min(img_width, int(x2))
                    y2 = min(img_height, int(y2))
                    faces.append(
                        {
                            "bbox": {
                                "x1": float(x1),
                                "y1": float(y1),
                                "x2": float(x2),
                                "y2": float(y2),
                                "width": float(x2 - x1),
                                "height": float(y2 - y1),
                            },
                            "confidence": round(confidence, 4),
                        }
                    )
                detector_name = "ModelScope RetinaFace"
            else:
                faces, detector_name = _detect_faces_with_opencv(img, img_width, img_height)
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass

        img_draw = img.copy()
        for face in faces:
            bbox = face["bbox"]
            x1 = int(bbox["x1"])
            y1 = int(bbox["y1"])
            x2 = int(bbox["x2"])
            y2 = int(bbox["y2"])
            cv2.rectangle(img_draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"Face {face['confidence']:.2f}"
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(img_draw, (x1, y1 - label_h - 10), (x1 + label_w + 10, y1), (0, 255, 0), -1)
            cv2.putText(img_draw, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        _, buffer_draw = cv2.imencode(".jpg", img_draw, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_result_base64 = base64.b64encode(buffer_draw).decode("utf-8")
        return jsonify(
            {
                "success": True,
                "face_count": len(faces),
                "faces": faces,
                "image_width": img_width,
                "image_height": img_height,
                "result_image": f"data:image/jpeg;base64,{img_result_base64}",
                "detector": detector_name,
                "model_ref": "https://modelscope.cn/models/iic/cv_resnet50_face-detection_retinaface",
            }
        )
    except Exception as exc:
        return jsonify({"error": f"人脸检测失败: {str(exc)}"}), 500


@vision_bp.route("/api/safety_helmet_detection", methods=["POST"])
def safety_helmet_detection():
    if "file" not in request.files:
        return jsonify({"error": "没有文件部分"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400

    try:
        image_bytes = file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "无法解码图片"}), 400

        img_height, img_width = img.shape[:2]
        temp_path = os.path.join(tempfile.gettempdir(), f"safety_helmet_{uuid.uuid4().hex}.jpg")
        cv2.imwrite(temp_path, img)

        try:
            pipeline = _get_safety_helmet_pipeline()
            if pipeline is None:
                return (
                    jsonify(
                        {
                            "error": "安全帽检测模型未加载",
                            "suggestion": "ModelScope DAMO-YOLO 模型初始化失败。请检查: 1) 服务器网络是否可访问 modelscope.cn; 2) 是否在 Docker 构建时预下载了模型; 3) 可尝试 docker build --network=host 重新构建。",
                        }
                    ),
                    500,
                )

            result = pipeline(temp_path)
            scores = result.get("scores", [])
            labels = result.get("labels", [])
            boxes = result.get("boxes", [])
            detections = []
            for index, box in enumerate(boxes):
                if len(box) < 4:
                    continue
                x1, y1, x2, y2 = box[:4]
                confidence = float(scores[index]) if index < len(scores) else 0.0
                label = str(labels[index]) if index < len(labels) else "unknown"
                x1 = max(0, int(x1))
                y1 = max(0, int(y1))
                x2 = min(img_width, int(x2))
                y2 = min(img_height, int(y2))
                detections.append(
                    {
                        "bbox": {
                            "x1": float(x1),
                            "y1": float(y1),
                            "x2": float(x2),
                            "y2": float(y2),
                            "width": float(x2 - x1),
                            "height": float(y2 - y1),
                        },
                        "label": label,
                        "confidence": round(confidence, 4),
                    }
                )
            detector_name = "ModelScope DAMO-YOLO (Safety Helmet)"
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass

        img_draw = img.copy()
        for det in detections:
            bbox = det["bbox"]
            x1 = int(bbox["x1"])
            y1 = int(bbox["y1"])
            x2 = int(bbox["x2"])
            y2 = int(bbox["y2"])
            if det["label"] == "safety hat":
                color = (0, 255, 0)
                label_text = f"Safety Hat {det['confidence']:.2f}"
            else:
                color = (0, 0, 255)
                label_text = f"No Hat {det['confidence']:.2f}"
            cv2.rectangle(img_draw, (x1, y1), (x2, y2), color, 2)
            (label_w, label_h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(img_draw, (x1, y1 - label_h - 10), (x1 + label_w + 10, y1), color, -1)
            cv2.putText(img_draw, label_text, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        _, buffer_draw = cv2.imencode(".jpg", img_draw, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_result_base64 = base64.b64encode(buffer_draw).decode("utf-8")
        return jsonify(
            {
                "success": True,
                "detection_count": len(detections),
                "safety_hat_count": sum(1 for item in detections if item["label"] == "safety hat"),
                "no_safety_hat_count": sum(1 for item in detections if item["label"] == "no safety hat"),
                "detections": detections,
                "image_width": img_width,
                "image_height": img_height,
                "result_image": f"data:image/jpeg;base64,{img_result_base64}",
                "detector": detector_name,
                "model_ref": "https://modelscope.cn/models/iic/cv_tinynas_object-detection_damoyolo_safety-helmet",
            }
        )
    except Exception as exc:
        return jsonify({"error": f"安全帽检测失败: {str(exc)}"}), 500


@vision_bp.route("/api/license_plate_detection", methods=["POST"])
def license_plate_detection():
    if "file" not in request.files:
        return jsonify({"error": "没有文件部分"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400

    try:
        image_bytes = file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "无法解码图片"}), 400

        img_height, img_width = img.shape[:2]
        ocr = _get_license_ocr()
        detections = []

        if ocr is None:
            return (
                jsonify(
                    {
                        "error": "OCR 模型未加载",
                        "suggestion": "PaddleOCR模型初始化失败。请检查: 1) 服务器网络是否可访问PaddleOCR模型下载地址; 2) 是否在Docker构建时预下载了模型; 3) 模型文件是否完整。可尝试重启容器或重新构建镜像。",
                    }
                ),
                500,
            )

        try:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ocr_result = ocr.predict(img_rgb)
            if ocr_result and len(ocr_result) > 0:
                ocr_data = ocr_result[0]
                if isinstance(ocr_data, dict):
                    rec_texts = ocr_data.get("rec_texts", [])
                    rec_scores = ocr_data.get("rec_scores", [])
                    rec_polys = ocr_data.get("rec_polys", [])
                    for index in range(len(rec_texts)):
                        text = rec_texts[index]
                        confidence = float(rec_scores[index]) if index < len(rec_scores) else 0.0
                        if not _is_license_plate_text(text):
                            continue
                        poly = rec_polys[index] if index < len(rec_polys) else None
                        if poly is None or not isinstance(poly, np.ndarray):
                            continue
                        xs = poly[:, 0]
                        ys = poly[:, 1]
                        x1, y1 = int(min(xs)), int(min(ys))
                        x2, y2 = int(max(xs)), int(max(ys))
                        detections.append(
                            {
                                "bbox": {
                                    "x1": float(x1),
                                    "y1": float(y1),
                                    "x2": float(x2),
                                    "y2": float(y2),
                                    "width": float(x2 - x1),
                                    "height": float(y2 - y1),
                                },
                                "confidence": round(confidence, 4),
                                "plate_text": text,
                                "plate_text_confidence": round(confidence, 4),
                            }
                        )
            detector_name = "PaddleOCR (License Plate Recognition)"
        except Exception as exc:
            error_msg = str(exc)
            print(f"[LicensePlate] OCR 识别失败: {error_msg}")
            if any(token in error_msg.lower() for token in ("download", "connection", "timeout", "http")):
                return (
                    jsonify(
                        {
                            "error": f"OCR模型加载失败: {error_msg}",
                            "suggestion": "请检查服务器网络连接，确保可以访问PaddleOCR模型下载地址。如果使用Docker，请尝试: docker build --network=host 或在Dockerfile中预下载模型。也可以手动下载模型后挂载到 /root/.paddleocr 目录。",
                        }
                    ),
                    500,
                )
            return jsonify({"error": f"OCR识别失败: {error_msg}"}), 500

        img_draw = img.copy()
        img_pil = Image.fromarray(cv2.cvtColor(img_draw, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        chinese_font = _load_chinese_font(24)

        for det in detections:
            bbox = det["bbox"]
            x1 = int(bbox["x1"])
            y1 = int(bbox["y1"])
            x2 = int(bbox["x2"])
            y2 = int(bbox["y2"])
            color_bgr = (255, 0, 0)
            cv2.rectangle(img_draw, (x1, y1), (x2, y2), color_bgr, 3)
            label_text = det.get("plate_text", "")
            bbox_text = draw.textbbox((0, 0), label_text, font=chinese_font)
            label_w = bbox_text[2] - bbox_text[0]
            label_h = bbox_text[3] - bbox_text[1]
            cv2.rectangle(img_draw, (x1, y1 - label_h - 12), (x1 + label_w + 12, y1), color_bgr, -1)
            img_pil = Image.fromarray(cv2.cvtColor(img_draw, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(img_pil)
            draw.text((x1 + 6, y1 - label_h - 6), label_text, font=chinese_font, fill=(255, 255, 255))
            img_draw = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
            cv2.putText(img_draw, f"conf: {det['confidence']:.2f}", (x1, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)

        _, buffer_draw = cv2.imencode(".jpg", img_draw, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_result_base64 = base64.b64encode(buffer_draw).decode("utf-8")
        return jsonify(
            {
                "success": True,
                "detection_count": len(detections),
                "detections": detections,
                "image_width": img_width,
                "image_height": img_height,
                "result_image": f"data:image/jpeg;base64,{img_result_base64}",
                "detector": detector_name,
                "model_ref": "https://modelscope.cn/models/iic/cv_resnet18_license-plate-detection_damo",
            }
        )
    except Exception as exc:
        return jsonify({"error": f"车牌检测失败: {str(exc)}"}), 500


@vision_bp.route("/api/keypoint_detection", methods=["POST"])
def keypoint_detection():
    if "file" not in request.files:
        return jsonify({"error": "没有文件部分"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400

    try:
        image_bytes = file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "无法解码图片"}), 400

        img_height, img_width = img.shape[:2]
        model, device = _get_keypoint_model()
        if model is None:
            return (
                jsonify(
                    {
                        "error": "关键点检测模型未加载",
                        "suggestion": "PyTorch Keypoint R-CNN 模型初始化失败。请检查: 1) 服务器网络是否可访问 PyTorch 模型下载地址; 2) 是否在 Docker 构建时预下载了模型; 3) 可尝试 docker build --network=host 重新构建。",
                    }
                ),
                500,
            )

        import torch

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).float().div(255.0).unsqueeze(0).to(device)
        with torch.no_grad():
            predictions = model(img_tensor)

        scores = predictions[0]["scores"].cpu().numpy()
        boxes = predictions[0]["boxes"].cpu().numpy()
        keypoints = predictions[0]["keypoints"].cpu().numpy()
        valid_indices = scores > 0.5
        persons = []

        for idx in range(len(scores)):
            if not valid_indices[idx]:
                continue
            score = float(scores[idx])
            box = boxes[idx]
            kps = keypoints[idx]
            x1, y1, x2, y2 = map(int, box)
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img_width, x2)
            y2 = min(img_height, y2)
            person_kps = []
            for point_idx, kp in enumerate(kps):
                x, y, conf = int(kp[0]), int(kp[1]), float(kp[2])
                person_kps.append(
                    {
                        "name": KEYPOINT_NAMES[point_idx] if point_idx < len(KEYPOINT_NAMES) else f"kp_{point_idx}",
                        "x": x,
                        "y": y,
                        "confidence": round(conf, 4),
                    }
                )
            persons.append(
                {
                    "bbox": {
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                        "width": float(x2 - x1),
                        "height": float(y2 - y1),
                    },
                    "confidence": round(score, 4),
                    "keypoints": person_kps,
                }
            )

        img_draw = img.copy()
        for person in persons:
            bbox = person["bbox"]
            x1 = int(bbox["x1"])
            y1 = int(bbox["y1"])
            x2 = int(bbox["x2"])
            y2 = int(bbox["y2"])
            cv2.rectangle(img_draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img_draw, f"Person {person['confidence']:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            for color_idx, kp in enumerate(person["keypoints"]):
                if kp["confidence"] > 0.3:
                    color = KEYPOINT_COLORS[color_idx % len(KEYPOINT_COLORS)]
                    cv2.circle(img_draw, (kp["x"], kp["y"]), 4, color, -1)
                    cv2.circle(img_draw, (kp["x"], kp["y"]), 5, (255, 255, 255), 1)
            for start, end in KEYPOINT_SKELETON:
                if start < len(person["keypoints"]) and end < len(person["keypoints"]):
                    if person["keypoints"][start]["confidence"] > 0.3 and person["keypoints"][end]["confidence"] > 0.3:
                        pt1 = (person["keypoints"][start]["x"], person["keypoints"][start]["y"])
                        pt2 = (person["keypoints"][end]["x"], person["keypoints"][end]["y"])
                        cv2.line(img_draw, pt1, pt2, (0, 255, 255), 2)

        _, buffer_draw = cv2.imencode(".jpg", img_draw, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_result_base64 = base64.b64encode(buffer_draw).decode("utf-8")
        return jsonify(
            {
                "success": True,
                "person_count": len(persons),
                "persons": persons,
                "image_width": img_width,
                "image_height": img_height,
                "result_image": f"data:image/jpeg;base64,{img_result_base64}",
                "detector": "PyTorch Keypoint R-CNN (ResNet50-FPN)",
                "model_ref": "https://modelscope.cn/models/iic/cv_hrnetw48_human-wholebody-keypoint_image",
            }
        )
    except Exception as exc:
        return jsonify({"error": f"关键点检测失败: {str(exc)}"}), 500


@vision_bp.route("/api/gauge_detection", methods=["POST"])
def gauge_detection():
    if "file" not in request.files:
        return jsonify({"error": "没有文件部分"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "没有选择文件"}), 400

    try:
        image_bytes = file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "无法解码图片"}), 400

        img_height, img_width = img.shape[:2]
        auto_detect = request.form.get("auto_detect", "true").lower() == "true"
        refine_center = request.form.get("refine_center", "true").lower() == "true"
        auto_scale = request.form.get("auto_scale", "true").lower() == "true"
        center_x = request.form.get("center_x", type=int)
        center_y = request.form.get("center_y", type=int)
        radius = request.form.get("radius", type=int)
        start_angle = request.form.get("start_angle", 0, type=float)
        end_angle = request.form.get("end_angle", 270, type=float)
        min_value = request.form.get("min_value", 0, type=float)
        max_value = request.form.get("max_value", 100, type=float)

        from gauge_reader import PrecisionGaugeReader

        reader = PrecisionGaugeReader()
        if not auto_detect and center_x is not None and center_y is not None and radius is not None:
            reader.set_gauge_params((center_x, center_y), radius, start_angle, end_angle, min_value, max_value)

        result = reader.read_gauge(img, auto_scale=auto_scale, refine_center=refine_center)
        if not result["success"]:
            return jsonify({"success": False, "error": result.get("error", "压力表读数失败"), "image_width": img_width, "image_height": img_height}), 400

        annotated = reader.draw_result(img, result)
        _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
        img_result_base64 = base64.b64encode(buffer).decode("utf-8")

        debug_images = {}
        debug_info = result.get("debug_info", {})
        pointer_mask = debug_info.get("pointer_mask")
        if pointer_mask is not None and np.any(pointer_mask):
            mask_vis = np.zeros((img_height, img_width, 3), dtype=np.uint8)
            mask_vis[pointer_mask > 0] = [0, 0, 255]
            overlay = cv2.addWeighted(img, 0.7, mask_vis, 0.3, 0)
            _, buf = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 90])
            debug_images["pointer_mask"] = base64.b64encode(buf).decode("utf-8")

        polar_img = debug_info.get("polar_image")
        if polar_img is not None:
            polar_vis = cv2.resize(polar_img, (360, 200), interpolation=cv2.INTER_NEAREST)
            polar_color = cv2.cvtColor(polar_vis, cv2.COLOR_GRAY2BGR)
            _, buf = cv2.imencode(".jpg", polar_color, [cv2.IMWRITE_JPEG_QUALITY, 90])
            debug_images["polar"] = base64.b64encode(buf).decode("utf-8")

        polar_processed = debug_info.get("polar_processed")
        if polar_processed is not None:
            polar_vis = cv2.resize(polar_processed, (360, 200), interpolation=cv2.INTER_NEAREST)
            polar_color = cv2.cvtColor(polar_vis, cv2.COLOR_GRAY2BGR)
            _, buf = cv2.imencode(".jpg", polar_color, [cv2.IMWRITE_JPEG_QUALITY, 90])
            debug_images["polar_processed"] = base64.b64encode(buf).decode("utf-8")

        return jsonify(
            {
                "success": True,
                "reading": float(result["reading"]),
                "pointer_angle": float(result["pointer_angle"]),
                "center": [float(item) for item in result["center"]],
                "radius": int(result["radius"]),
                "start_angle": float(result["start_angle"]),
                "end_angle": float(result["end_angle"]),
                "min_value": float(result["min_value"]),
                "max_value": float(result["max_value"]),
                "image_width": int(img_width),
                "image_height": int(img_height),
                "result_image": f"data:image/jpeg;base64,{img_result_base64}",
                "debug_images": debug_images,
                "detector": "PrecisionGaugeReader (CV-based)",
            }
        )
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"压力表检测失败: {str(exc)}"}), 500


def _detect_faces_with_opencv(img, img_width, img_height):
    model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
    prototxt = os.path.join(model_dir, "deploy.prototxt")
    caffemodel = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")

    if os.path.exists(prototxt) and os.path.exists(caffemodel):
        net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
        blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
        net.setInput(blob)
        detections = net.forward()
        faces = []
        for index in range(detections.shape[2]):
            confidence = float(detections[0, 0, index, 2])
            if confidence <= 0.5:
                continue
            box = detections[0, 0, index, 3:7] * np.array([img_width, img_height, img_width, img_height])
            x1, y1, x2, y2 = box.astype(int)
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img_width, x2)
            y2 = min(img_height, y2)
            faces.append(
                {
                    "bbox": {
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                        "width": float(x2 - x1),
                        "height": float(y2 - y1),
                    },
                    "confidence": round(confidence, 4),
                }
            )
        return faces, "OpenCV DNN (ResNet SSD)"

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces_data = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
    faces = []
    for x, y, w, h in faces_data:
        faces.append(
            {
                "bbox": {
                    "x1": float(x),
                    "y1": float(y),
                    "x2": float(x + w),
                    "y2": float(y + h),
                    "width": float(w),
                    "height": float(h),
                },
                "confidence": 0.95,
            }
        )
    return faces, "OpenCV Haar Cascade"
