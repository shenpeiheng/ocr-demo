#!/usr/bin/env python3
"""
测试坐标解析的准确性
"""

import os
import sys
import numpy as np
import cv2
from PIL import Image

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from paddle_ocr_processor import PaddleOCRProcessor

def create_test_image_with_markers(image_path):
    """创建带有标记的测试图像，便于验证坐标"""
    # 创建白色背景
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    
    # 在特定位置添加文本（便于验证坐标）
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # 位置1: (100, 100)
    cv2.putText(img, 'POS1', (100, 100), font, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (100, 100), 5, (255, 0, 0), -1)  # 蓝色标记
    
    # 位置2: (300, 200)
    cv2.putText(img, 'POS2', (300, 200), font, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (300, 200), 5, (0, 255, 0), -1)  # 绿色标记
    
    # 位置3: (200, 300)
    cv2.putText(img, 'POS3', (200, 300), font, 1.0, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.circle(img, (200, 300), 5, (0, 0, 255), -1)  # 红色标记
    
    # 保存图像
    cv2.imwrite(image_path, img)
    print(f"创建测试图像: {image_path}")
    print("标记位置:")
    print("  POS1: (100, 100) - 蓝色标记")
    print("  POS2: (300, 200) - 绿色标记")
    print("  POS3: (200, 300) - 红色标记")
    
    return img

def test_coordinate_accuracy():
    """测试坐标准确性"""
    print("=" * 60)
    print("坐标准确性测试")
    print("=" * 60)
    
    # 创建测试图像
    test_image_path = "test_coordinate_image.png"
    create_test_image_with_markers(test_image_path)
    
    # 创建OCR处理器
    processor = PaddleOCRProcessor(lang='ch')
    if not processor.initialized:
        print("❌ PaddleOCR初始化失败")
        return False
    
    print("✅ PaddleOCR初始化成功")
    
    # 处理图像
    print("正在处理图像...")
    result = processor.process_image(test_image_path)
    
    if not result['success']:
        print(f"❌ 图像处理失败: {result.get('error', '未知错误')}")
        return False
    
    print(f"✅ 图像处理成功，识别到 {result['total_items']} 个文本项")
    
    # 显示识别结果和坐标
    print("\n识别结果坐标:")
    for i, item in enumerate(result['text_items'], 1):
        text = item['text']
        location = item['location']
        left = location['left']
        top = location['top']
        right = location['right']
        bottom = location['bottom']
        width = location['width']
        height = location['height']
        
        print(f"  {i}. 文本: '{text}'")
        print(f"     边界框: left={left}, top={top}, right={right}, bottom={bottom}")
        print(f"     尺寸: width={width}, height={height}")
        print(f"     中心点: ({left + width//2}, {top + height//2})")
        
        # 检查坐标是否合理
        if left < 0 or top < 0 or right > 600 or bottom > 400:
            print(f"     ⚠️  坐标超出图像范围!")
        
        # 检查文本位置是否接近预期
        if text == 'POS1':
            expected_x, expected_y = 100, 100
            distance = np.sqrt((left - expected_x)**2 + (top - expected_y)**2)
            print(f"     与预期位置距离: {distance:.1f} 像素")
            if distance > 50:
                print(f"     ⚠️  位置偏差较大!")
        
        print()
    
    # 显示原始多边形坐标
    print("原始多边形坐标:")
    for i, item in enumerate(result['text_items'], 1):
        points = item['location']['points']
        print(f"  {i}. '{item['text']}' 多边形:")
        for j, point in enumerate(points):
            print(f"      点{j}: {point}")
    
    # 清理测试文件
    if os.path.exists(test_image_path):
        os.remove(test_image_path)
        print(f"\n✅ 清理测试文件: {test_image_path}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return True

def test_raw_ocr_output():
    """测试原始OCR输出格式"""
    print("\n" + "=" * 60)
    print("原始OCR输出格式测试")
    print("=" * 60)
    
    # 创建测试图像
    test_image_path = "test_raw_image.png"
    img = np.ones((200, 300, 3), dtype=np.uint8) * 255
    cv2.putText(img, 'TEST', (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 2)
    cv2.imwrite(test_image_path, img)
    
    # 直接使用PaddleOCR获取原始结果
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(lang='ch', ocr_version='PP-OCRv5')
        
        # 读取图像
        img_array = cv2.imread(test_image_path)
        img_rgb = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
        
        # 使用predict方法
        result = ocr.predict(img_rgb)
        
        print(f"原始结果类型: {type(result)}")
        if isinstance(result, list) and len(result) > 0:
            ocr_data = result[0]
            print(f"OCR数据类型: {type(ocr_data)}")
            
            if isinstance(ocr_data, dict):
                print("OCR数据字段:")
                for key, value in ocr_data.items():
                    if isinstance(value, (list, np.ndarray)):
                        print(f"  {key}: {type(value)}, 长度: {len(value)}")
                        if len(value) > 0 and isinstance(value[0], (list, np.ndarray)):
                            print(f"    第一个元素: {value[0]}, 类型: {type(value[0])}")
                            if isinstance(value[0], np.ndarray):
                                print(f"      形状: {value[0].shape}, 数据类型: {value[0].dtype}")
                    else:
                        print(f"  {key}: {type(value)}, 值: {value}")
                
                # 特别检查rec_polys
                rec_polys = ocr_data.get('rec_polys', [])
                if rec_polys and len(rec_polys) > 0:
                    print(f"\n第一个rec_poly:")
                    print(f"  类型: {type(rec_polys[0])}")
                    if isinstance(rec_polys[0], np.ndarray):
                        print(f"  形状: {rec_polys[0].shape}")
                        print(f"  数据类型: {rec_polys[0].dtype}")
                        print(f"  值:\n{rec_polys[0]}")
                        
                        # 检查坐标范围
                        print(f"  坐标范围:")
                        print(f"    X: {np.min(rec_polys[0][:, 0])} 到 {np.max(rec_polys[0][:, 0])}")
                        print(f"    Y: {np.min(rec_polys[0][:, 1])} 到 {np.max(rec_polys[0][:, 1])}")
    
    except Exception as e:
        print(f"测试原始OCR输出失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 清理
    if os.path.exists(test_image_path):
        os.remove(test_image_path)
    
    print("=" * 60)

if __name__ == '__main__':
    # 运行坐标准确性测试
    success1 = test_coordinate_accuracy()
    
    # 运行原始OCR输出测试
    test_raw_ocr_output()
    
    if success1:
        print("\n✅ 坐标准确性测试通过")
    else:
        print("\n⚠️  坐标准确性测试发现问题")