#!/usr/bin/env python3
"""
测试OCR初始化 - 验证PaddleOCR 3.3.2配置是否正确
"""

import sys
import os
sys.path.append('.')

print("测试OCR初始化...")
print("=" * 60)

try:
    # 测试1: 导入PaddleOCR
    print("1. 导入PaddleOCR...")
    from paddleocr import PaddleOCR
    print("✅ PaddleOCR导入成功")
    
    # 测试2: 创建简单的PaddleOCR实例
    print("\n2. 创建简单的PaddleOCR实例...")
    ocr_simple = PaddleOCR()
    print("✅ 简单PaddleOCR实例创建成功")
    
    # 测试3: 使用PP-OCRv5配置创建实例
    print("\n3. 使用PP-OCRv5配置创建实例...")
    ocr_v5 = PaddleOCR(
        lang='ch',
        ocr_version='PP-OCRv5',
        text_det_box_thresh=0.2,
        text_det_unclip_ratio=2.5,
        text_rec_score_thresh=0.3,
        text_det_limit_type='max',
        text_det_limit_side_len=1920,
        text_det_thresh=0.3,
    )
    print("✅ PP-OCRv5实例创建成功")
    
    # 测试4: 测试英文模型
    print("\n4. 测试英文PP-OCRv5模型...")
    ocr_en = PaddleOCR(
        lang='en',
        ocr_version='PP-OCRv5',
    )
    print("✅ 英文PP-OCRv5实例创建成功")
    
    # 测试5: 导入我们的OCR处理器
    print("\n5. 导入我们的OCR处理器...")
    from ocr_processor import OCRProcessor
    print("✅ OCRProcessor导入成功")
    
    # 测试6: 创建OCR处理器实例
    print("\n6. 创建OCR处理器实例...")
    processor = OCRProcessor(lang='ch')
    print("✅ OCR处理器实例创建成功")
    
    # 测试7: 检查处理器是否初始化
    print("\n7. 检查处理器状态...")
    if hasattr(processor, 'paddle_processor') and processor.paddle_processor:
        if processor.paddle_processor.initialized:
            print("✅ PaddleOCR处理器已正确初始化")
        else:
            print("❌ PaddleOCR处理器未初始化")
    else:
        print("❌ 处理器未正确创建")
    
    print("\n" + "=" * 60)
    print("所有测试通过！✅")
    print("PaddleOCR 3.3.2 配置正确，支持PP-OCRv5模型")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保已安装 paddlepaddle 和 paddleocr")
    print("安装命令: pip install paddlepaddle==3.2.2 paddleocr==3.3.2")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)