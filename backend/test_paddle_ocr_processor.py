#!/usr/bin/env python3
"""
测试更新后的PaddleOCR处理器
"""

import os
import sys
import logging

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from paddle_ocr_processor import PaddleOCRProcessor

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_processor():
    """测试OCR处理器"""
    print("测试PaddleOCR处理器...")
    
    # 创建处理器
    try:
        processor = PaddleOCRProcessor(lang='ch')
        if not processor.initialized:
            print("❌ PaddleOCR初始化失败")
            return False
        
        print("✅ PaddleOCR初始化成功")
        
        # 创建测试图像
        test_image_path = "test_image.png"
        create_test_image(test_image_path)
        
        if not os.path.exists(test_image_path):
            print(f"❌ 测试图像不存在: {test_image_path}")
            return False
        
        print(f"✅ 创建测试图像: {test_image_path}")
        
        # 处理图像
        print("正在处理图像...")
        result = processor.process_image(test_image_path)
        
        if result['success']:
            print(f"✅ 图像处理成功!")
            print(f"   识别到 {result['total_items']} 个文本项")
            print(f"   处理时间: {result['processing_time']}秒")
            
            # 显示识别结果
            if result['text_items']:
                print("\n识别结果:")
                for i, item in enumerate(result['text_items'][:5], 1):
                    print(f"  {i}. [{item['type']}] {item['text']} (置信度: {item['confidence']:.3f})")
            
            # 显示分析结果
            analysis = result['analysis']
            print(f"\n分析结果:")
            print(f"  尺寸标注: {analysis.get('dimension_count', 0)}")
            print(f"  公差标注: {analysis.get('tolerance_count', 0)}")
            print(f"  材料信息: {analysis.get('material_count', 0)}")
            print(f"  技术要求: {analysis.get('technical_count', 0)}")
            print(f"  平均置信度: {analysis.get('average_confidence', 0):.3f}")
            
            # 清理测试文件
            if os.path.exists(test_image_path):
                os.remove(test_image_path)
                print(f"✅ 清理测试文件: {test_image_path}")
            
            return True
        else:
            print(f"❌ 图像处理失败: {result.get('error', '未知错误')}")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_test_image(image_path):
    """创建测试图像"""
    try:
        import numpy as np
        import cv2
        
        # 创建白色背景图像
        img = np.ones((200, 400, 3), dtype=np.uint8) * 255
        
        # 添加测试文本
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, 'Test 123', (50, 80), font, 1.5, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(img, 'φ25±0.1', (50, 130), font, 1.2, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.putText(img, 'Q235 Steel', (50, 180), font, 1.2, (0, 0, 0), 2, cv2.LINE_AA)
        
        # 保存图像
        cv2.imwrite(image_path, img)
        return True
    except Exception as e:
        print(f"创建测试图像失败: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("PaddleOCR处理器测试")
    print("=" * 60)
    
    success = test_processor()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试通过!")
    else:
        print("❌ 测试失败!")
    print("=" * 60)