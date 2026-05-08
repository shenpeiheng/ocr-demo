#!/usr/bin/env python3
"""
模型预下载脚本 - 在 Docker 构建阶段运行
提前下载所有需要的 AI 模型，避免运行时首次调用因网络问题下载超时

包含以下模型:
1. PaddleOCR PP-OCRv5 - 用于车牌识别
2. ModelScope DAMO-YOLO - 用于安全帽检测
3. PyTorch Keypoint R-CNN - 用于全身关键点检测

注意: 即使部分模型下载失败，脚本也会返回 0（不中断构建）
      因为运行时 app.py 的预加载机制会重试下载
"""

import os
import sys
import time


def download_paddleocr_models():
    """预下载 PaddleOCR PP-OCRv5 模型"""
    print("\n" + "=" * 60)
    print("[1/3] 预下载 PaddleOCR PP-OCRv5 模型...")
    print("=" * 60)

    model_dir = '/root/.paddleocr'
    os.environ['PADDLEOCR_MODEL_DIR'] = model_dir
    os.makedirs(model_dir, exist_ok=True)

    start_time = time.time()

    try:
        from paddleocr import PaddleOCR
        import numpy as np

        print("[ModelPreload] 正在初始化 PaddleOCR (PP-OCRv5)...")
        print("[ModelPreload] 将自动下载检测(det)、识别(rec)和分类(cls)模型...")

        ocr = PaddleOCR(
            lang='ch',
            ocr_version='PP-OCRv5',
            text_det_box_thresh=0.13,
            text_det_unclip_ratio=2.5,
            text_rec_score_thresh=0.1,
            use_doc_unwarping=False
        )

        print("[ModelPreload] 模型初始化完成，执行一次预测以完整加载...")

        test_img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        result = ocr.predict(test_img)

        elapsed = time.time() - start_time
        print(f"[ModelPreload] PaddleOCR PP-OCRv5 模型预下载完成! (耗时: {elapsed:.1f}秒)")

        # 列出下载的模型文件
        total_size = 0
        if os.path.exists(model_dir):
            for root, dirs, files in os.walk(model_dir):
                for f in sorted(files):
                    filepath = os.path.join(root, f)
                    size_bytes = os.path.getsize(filepath)
                    size_mb = size_bytes / (1024 * 1024)
                    total_size += size_bytes
                    rel_path = os.path.relpath(filepath, model_dir)
                    print(f"  [Model] {rel_path:<60} {size_mb:>6.2f} MB")

        print(f"  [Total] PaddleOCR 模型总计: {total_size / (1024 * 1024):.2f} MB")
        return True

    except ImportError as e:
        print(f"[ModelPreload] 导入 PaddleOCR 失败: {e}")
        return False
    except Exception as e:
        print(f"[ModelPreload] PaddleOCR 模型下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def download_safety_helmet_model():
    """预下载 ModelScope DAMO-YOLO 安全帽检测模型"""
    print("\n" + "=" * 60)
    print("[2/3] 预下载 ModelScope DAMO-YOLO 安全帽检测模型...")
    print("=" * 60)

    # ModelScope 模型缓存目录
    modelscope_cache = os.environ.get('MODELSCOPE_CACHE', '/root/.cache/modelscope')
    os.makedirs(modelscope_cache, exist_ok=True)
    os.environ['MODELSCOPE_CACHE'] = modelscope_cache

    start_time = time.time()

    try:
        from modelscope.pipelines import pipeline
        from modelscope.utils.constant import Tasks

        print("[ModelPreload] 正在加载 DAMO-YOLO 安全帽检测模型...")
        print("[ModelPreload] 模型: iic/cv_tinynas_object-detection_damoyolo_safety-helmet")

        # 初始化 pipeline，这会自动下载模型
        helmet_pipeline = pipeline(
            Tasks.image_object_detection,
            model='iic/cv_tinynas_object-detection_damoyolo_safety-helmet',
            trust_remote_code=True
        )

        print("[ModelPreload] 模型加载完成，执行一次预测以完整缓存...")

        # 执行一次预测以触发完整的模型加载
        import numpy as np
        test_img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        result = helmet_pipeline(test_img)

        elapsed = time.time() - start_time
        print(f"[ModelPreload] DAMO-YOLO 安全帽检测模型预下载完成! (耗时: {elapsed:.1f}秒)")

        # 列出下载的模型文件
        total_size = 0
        if os.path.exists(modelscope_cache):
            for root, dirs, files in os.walk(modelscope_cache):
                for f in sorted(files):
                    filepath = os.path.join(root, f)
                    try:
                        size_bytes = os.path.getsize(filepath)
                        size_mb = size_bytes / (1024 * 1024)
                        total_size += size_bytes
                        rel_path = os.path.relpath(filepath, modelscope_cache)
                        if size_mb > 0.01:
                            print(f"  [Model] {rel_path:<60} {size_mb:>6.2f} MB")
                    except:
                        pass

        print(f"  [Total] ModelScope 模型总计: {total_size / (1024 * 1024):.2f} MB")
        return True

    except ImportError as e:
        print(f"[ModelPreload] 导入 ModelScope 失败: {e}")
        return False
    except Exception as e:
        print(f"[ModelPreload] DAMO-YOLO 模型下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def download_keypoint_model():
    """预下载 PyTorch Keypoint R-CNN 模型"""
    print("\n" + "=" * 60)
    print("[3/3] 预下载 PyTorch Keypoint R-CNN (ResNet50-FPN) 模型...")
    print("=" * 60)

    # PyTorch 模型缓存目录
    torch_cache = os.environ.get('TORCH_HOME', '/root/.cache/torch')
    os.makedirs(torch_cache, exist_ok=True)
    os.environ['TORCH_HOME'] = torch_cache

    start_time = time.time()

    try:
        import torch
        import torchvision

        print("[ModelPreload] 正在加载 Keypoint R-CNN 模型...")
        print("[ModelPreload] 模型: keypointrcnn_resnet50_fpn (COCO 预训练权重)")

        # 加载模型，这会自动下载预训练权重
        model = torchvision.models.detection.keypointrcnn_resnet50_fpn(
            weights=torchvision.models.detection.KeypointRCNN_ResNet50_FPN_Weights.DEFAULT
        )
        model.eval()

        # 检测设备
        device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        model.to(device)
        print(f"[ModelPreload] 模型已加载到设备: {device}")

        print("[ModelPreload] 执行一次预测以完整缓存...")

        # 执行一次预测以触发完整的模型加载
        import numpy as np
        test_img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        img_tensor = torch.from_numpy(test_img).permute(2, 0, 1).float().div(255.0).unsqueeze(0).to(device)

        with torch.no_grad():
            predictions = model(img_tensor)

        elapsed = time.time() - start_time
        print(f"[ModelPreload] Keypoint R-CNN 模型预下载完成! (耗时: {elapsed:.1f}秒)")

        # 列出下载的模型文件
        total_size = 0
        if os.path.exists(torch_cache):
            for root, dirs, files in os.walk(torch_cache):
                for f in sorted(files):
                    filepath = os.path.join(root, f)
                    try:
                        size_bytes = os.path.getsize(filepath)
                        size_mb = size_bytes / (1024 * 1024)
                        total_size += size_bytes
                        rel_path = os.path.relpath(filepath, torch_cache)
                        if size_mb > 0.01:
                            print(f"  [Model] {rel_path:<60} {size_mb:>6.2f} MB")
                    except:
                        pass

        print(f"  [Total] PyTorch 模型总计: {total_size / (1024 * 1024):.2f} MB")
        return True

    except ImportError as e:
        print(f"[ModelPreload] 导入 PyTorch/Torchvision 失败: {e}")
        return False
    except Exception as e:
        print(f"[ModelPreload] Keypoint R-CNN 模型下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数 - 依次下载所有模型"""
    print("=" * 60)
    print("  模型预下载脚本")
    print("  将在 Docker 构建阶段下载所有需要的 AI 模型")
    print("  注意: 部分模型下载失败不会中断构建，运行时将自动重试")
    print("=" * 60)

    results = {}

    # 1. PaddleOCR
    results['paddleocr'] = download_paddleocr_models()

    # 2. Safety Helmet (ModelScope)
    results['safety_helmet'] = download_safety_helmet_model()

    # 3. Keypoint R-CNN (PyTorch)
    results['keypoint'] = download_keypoint_model()

    # 汇总
    print("\n" + "=" * 60)
    print("  模型预下载汇总")
    print("=" * 60)
    all_success = True
    for name, success in results.items():
        status = "✓ 成功" if success else "✗ 失败"
        print(f"  {name:<20} {status}")
        if not success:
            all_success = False

    print("=" * 60)
    if all_success:
        print("  所有模型预下载成功完成!")
    else:
        print("  部分模型下载失败（不会中断构建）")
        print("  容器启动时 app.py 的预加载机制会自动重试下载")
        print("  如果持续失败，请检查网络连接或使用 --network=host 构建")

    # 始终返回 0，不中断 Docker 构建
    # 失败的模型会在容器启动时由 app.py 的重试机制处理
    return 0


if __name__ == '__main__':
    sys.exit(main())
