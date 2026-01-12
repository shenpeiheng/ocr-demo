"""
OCR处理器 - 使用PaddleOCR PP-OCRv5模型进行工业图片识别
"""

import os
import time
from typing import Dict, List, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRProcessor:
    """OCR处理器类"""
    
    def __init__(self, lang='ch'):
        """
        初始化OCR处理器
        
        Args:
            lang: 识别语言 ('ch'中文, 'en'英文)
        """
        self.lang = lang
        self.paddle_processor = None
        
        try:
            from paddle_ocr_processor import PaddleOCRProcessor
            self.paddle_processor = PaddleOCRProcessor(lang=lang)
            if self.paddle_processor.initialized:
                logger.info("PaddleOCR处理器初始化成功")
            else:
                raise RuntimeError("PaddleOCR初始化失败")
        except ImportError as e:
            logger.error(f"导入PaddleOCR处理器失败: {e}")
            raise RuntimeError(f"PaddleOCR未安装: {e}")
        except Exception as e:
            logger.error(f"PaddleOCR处理器初始化失败: {e}")
            raise RuntimeError(f"PaddleOCR初始化失败: {e}")
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """
        处理图片并进行OCR识别
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            识别结果字典
        """
        logger.info(f"开始处理图片: {image_path}")
        
        try:
            # 获取图片信息
            import PIL.Image as Image
            img = Image.open(image_path)
            img_width, img_height = img.size
            
            if not self.paddle_processor:
                raise RuntimeError("PaddleOCR处理器未初始化")
            
            # 使用PaddleOCR进行识别
            results = self.paddle_processor.process_image(image_path)
            
            # 确保结果包含必要的字段
            if 'image_info' not in results:
                results['image_info'] = {
                    'filename': os.path.basename(image_path),
                    'width': img_width,
                    'height': img_height,
                    'size': os.path.getsize(image_path)
                }
            
            if 'processed_at' not in results:
                results['processed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            
            logger.info(f"图片处理完成，识别到 {len(results.get('text_items', []))} 个文本项")
            return results
            
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            return self._get_error_result(str(e))
    
    
    def extract_coordinates(self, text_items: List[Dict]) -> List[Dict]:
        """
        提取坐标信息
        
        Args:
            text_items: 文本项列表
            
        Returns:
            坐标信息列表
        """
        coordinates = []
        
        for item in text_items:
            location = item.get('location', {})
            coordinates.append({
                'id': item.get('id'),
                'x': location.get('left', 0),
                'y': location.get('top', 0),
                'width': location.get('width', 0),
                'height': location.get('height', 0),
                'text': item.get('text', ''),
                'type': item.get('type', 'text'),
                'confidence': item.get('confidence', 0)
            })
        
        return coordinates
    
    def analyze_industrial_patterns(self, text_items: List[Dict]) -> Dict[str, Any]:
        """
        分析工业图纸模式
        
        Args:
            text_items: 文本项列表
            
        Returns:
            分析结果
        """
        # 统计不同类型的内容
        type_counts = {}
        dimension_items = []
        tolerance_items = []
        material_items = []
        technical_items = []
        
        for item in text_items:
            item_type = item.get('type', 'text')
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
            
            if item_type == 'dimension':
                dimension_items.append(item)
            elif item_type == 'tolerance':
                tolerance_items.append(item)
            elif item_type == 'material':
                material_items.append(item)
            elif item_type == 'technical':
                technical_items.append(item)
        
        # 计算平均置信度
        confidences = [item.get('confidence', 0) for item in text_items]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            'type_distribution': type_counts,
            'dimension_count': len(dimension_items),
            'tolerance_count': len(tolerance_items),
            'material_count': len(material_items),
            'technical_count': len(technical_items),
            'total_items': len(text_items),
            'average_confidence': round(avg_confidence, 3)
        }
    
    def _get_error_result(self, error_message: str) -> Dict[str, Any]:
        """获取错误结果"""
        return {
            'success': False,
            'error': error_message,
            'text_items': [],
            'total_items': 0,
            'processing_time': 0,
            'analysis': {},
            'image_info': {},
            'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'ocr_engine': 'PaddleOCR PP-OCRv5'
        }
    
    def batch_process(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """
        批量处理图片
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            处理结果列表
        """
        results = []
        for image_path in image_paths:
            result = self.process_image(image_path)
            results.append(result)
        return results


# 工厂函数，便于使用
def create_ocr_processor(lang='ch'):
    """创建OCR处理器实例"""
    return OCRProcessor(lang=lang)


if __name__ == '__main__':
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # 使用示例图片
        image_path = "../frontend/uploads/sample_industrial_drawing.png"
        if not os.path.exists(image_path):
            print(f"示例图片不存在: {image_path}")
            print("请上传真实图片进行测试，或创建示例图片")
            print("用法: python ocr_processor.py <图片路径>")
            sys.exit(1)
    
    print("测试OCR处理器...")
    print(f"处理图片: {image_path}")
    
    try:
        # 创建处理器
        processor = OCRProcessor(lang='ch')
        
        # 处理图片
        result = processor.process_image(image_path)
        
        if result['success']:
            print(f"\n识别成功!")
            print(f"OCR引擎: {result.get('ocr_engine', '未知')}")
            print(f"识别到 {result['total_items']} 个文本项")
            print(f"处理时间: {result.get('processing_time', 0)}秒")
            
            # 显示分析结果
            analysis = result.get('analysis', {})
            print(f"\n分析结果:")
            print(f"  尺寸标注: {analysis.get('dimension_count', 0)}")
            print(f"  公差标注: {analysis.get('tolerance_count', 0)}")
            print(f"  材料信息: {analysis.get('material_count', 0)}")
            print(f"  技术要求: {analysis.get('technical_count', 0)}")
            print(f"  平均置信度: {analysis.get('average_confidence', 0):.3f}")
            
            # 显示前5个识别结果
            print(f"\n前5个识别结果:")
            for i, item in enumerate(result['text_items'][:5], 1):
                print(f"  {i}. [{item['type']}] {item['text']} (置信度: {item['confidence']:.3f})")
                print(f"     位置: ({item['location']['left']}, {item['location']['top']})")
            
        else:
            print(f"\n识别失败: {result.get('error', '未知错误')}")
    except Exception as e:
        print(f"\nOCR处理器初始化失败: {e}")
        print("请检查PaddleOCR是否正确安装")
        sys.exit(1)