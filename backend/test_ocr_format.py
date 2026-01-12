#!/usr/bin/env python3
"""
测试PaddleOCR 3.3.2返回的数据格式
"""

import sys
import os
sys.path.append('.')

print("测试PaddleOCR 3.3.2数据格式...")
print("=" * 60)

try:
    from paddleocr import PaddleOCR
    import numpy as np
    import cv2
    
    # 创建PaddleOCR实例
    ocr = PaddleOCR(lang='ch', ocr_version='PP-OCRv5')
    print("✅ PaddleOCR实例创建成功")
    
    # 创建一个简单的测试图像
    print("\n创建测试图像...")
    test_image = np.ones((100, 200, 3), dtype=np.uint8) * 255
    cv2.putText(test_image, 'Test 123', (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    # 进行OCR识别 - 使用predict()方法
    print("进行OCR识别...")
    result = ocr.predict(test_image)
    
    print(f"\nOCR结果类型: {type(result)}")
    
    # 尝试不同的结果格式
    if isinstance(result, list):
        print(f"结果长度: {len(result)}")
        
        # 尝试访问第一个元素
        if len(result) > 0:
            first_item = result[0]
            print(f"第一个元素类型: {type(first_item)}")
            
            # 检查是否是字典
            if isinstance(first_item, dict):
                print("结果格式: 字典")
                for key, value in first_item.items():
                    print(f"  {key}: {type(value)}")
                    if isinstance(value, (list, tuple)) and len(value) > 0:
                        print(f"    第一个值: {value[0] if len(value) > 0 else 'N/A'}")
            # 检查是否是列表
            elif isinstance(first_item, (list, tuple)):
                print(f"第一个元素长度: {len(first_item)}")
                if len(first_item) > 0:
                    print(f"  第一个子元素: {first_item[0]} (类型: {type(first_item[0])})")
            else:
                print(f"第一个元素值: {first_item}")
    elif isinstance(result, dict):
        print("结果格式: 字典")
        for key, value in result.items():
            print(f"  {key}: {type(value)}")
    else:
        print(f"结果值: {result}")
    
    # 也尝试使用ocr()方法看看
    print("\n尝试使用ocr()方法...")
    try:
        result2 = ocr.ocr(test_image)
        print(f"ocr()方法结果类型: {type(result2)}")
        if isinstance(result2, list) and len(result2) > 0:
            print(f"ocr()方法结果长度: {len(result2)}")
            if len(result2[0]) > 0:
                print(f"第一个项目: {result2[0][0] if isinstance(result2[0], (list, tuple)) else result2[0]}")
    except Exception as e:
        print(f"ocr()方法失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()