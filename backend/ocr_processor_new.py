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
    
    def __init__(self, use_paddleocr=True, use_gpu=False, lang='ch'):
        """
        初始化OCR处理器
        
        Args:
            use_paddleocr: 是否使用PaddleOCR（True）或模拟数据（False）
            use_gpu: 是否使用GPU加速（仅PaddleOCR有效）
            lang: 识别语言 ('ch'中文, 'en'英文)
        """
        self.use_paddleocr = use_paddleocr
        self.use_gpu = use_gpu
        self.lang = lang
        self.paddle_processor = None
        
        if use_paddleocr:
            try:
                from paddle_ocr_processor import PaddleOCRProcessor
                self.paddle_processor = PaddleOCRProcessor(use_gpu=use_gpu, lang=lang)
                if self.paddle_processor.initialized:
                    logger.info("PaddleOCR处理器初始化成功")
                else:
                    logger.warning("PaddleOCR初始化失败，将使用模拟模式")
                    self.use_paddleocr = False
            except ImportError as e:
                logger.warning(f"导入PaddleOCR处理器失败: {e}，将使用模拟模式")
                self.use_paddleocr = False
            except Exception as e:
                logger.warning(f"PaddleOCR处理器初始化失败: {e}，将使用模拟模式")
                self.use_paddleocr = False
        else:
            logger.info("使用模拟OCR模式")
    
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
            
            if self.use_paddleocr and self.paddle_processor:
                # 使用PaddleOCR进行识别
                results = self.paddle_processor.process_image(image_path)
            else:
                # 使用模拟数据
                results = self.mock_ocr_results(image_path, img_width, img_height)
            
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
    
    def mock_ocr_results(self, image_path: str, img_width: int, img_height: int) -> Dict[str, Any]:
        """
        生成模拟OCR结果（用于演示和测试）
        
        Args:
            image_path: 图片路径
            img_width: 图片宽度
            img_height: 图片高度
            
        Returns:
            模拟识别结果
        """
        # 模拟工业图纸中的常见文本
        industrial_texts = [
            "图纸编号: GD-2023-001",
            "产品名称: 液压阀体",
            "材料: 45#钢",
            "数量: 10件",
            "比例: 1:2",
            "公差: ±0.05mm",
            "表面粗糙度: Ra1.6",
            "热处理: 调质HRC28-32",
            "技术要求: 去毛刺",
            "检验标准: GB/T 1804-m",
            "设计: 张三",
            "审核: 李四",
            "日期: 2023-10-15",
            "版本: V2.0",
            "备注: 批量生产",
            "Φ25±0.02",
            "R12.5",
            "M16×1.5",
            "45°",
            "▽▽"
        ]
        
        # 生成模拟的文本项
        text_items = []
        num_items = min(15, len(industrial_texts))
        
        import numpy as np
        
        for i in range(num_items):
            # 生成随机位置（在图片范围内）
            left = np.random.randint(50, max(100, img_width - 200))
            top = np.random.randint(50, max(100, img_height - 100))
            width = np.random.randint(100, 300)
            height = np.random.randint(30, 60)
            
            text_items.append({
                'id': i + 1,
                'text': industrial_texts[i],
                'confidence': round(0.7 + np.random.random() * 0.3, 2),  # 0.7-1.0的置信度
                'location': {
                    'left': left,
                    'top': top,
                    'width': width,
                    'height': height
                },
                'type': 'text'
            })
        
        # 添加一些特殊标记（如尺寸标注）
        special_items = [
            {
                'id': num_items + 1,
                'text': "Φ50H7",
                'confidence': 0.95,
                'location': {'left': 300, 'top': 200, 'width': 80, 'height': 30},
                'type': 'dimension'
            },
            {
                'id': num_items + 2,
                'text': "120±0.1",
                'confidence': 0.92,
                'location': {'left': 400, 'top': 350, 'width': 100, 'height': 30},
                'type': 'dimension'
            },
            {
                'id': num_items + 3,
                'text': "▲ 0.02 A",
                'confidence': 0.88,
                'location': {'left': 150, 'top': 450, 'width': 90, 'height': 30},
                'type': 'tolerance'
            }
        ]
        
        text_items.extend(special_items)
        
        # 分析结果
        analysis_result = self.analyze_industrial_patterns(text_items)
        
        return {
            'success': True,
            'text_items': text_items,
            'total_items': len(text_items),
            'processing_time': 0.5,
            'analysis': analysis_result,
            'ocr_engine': '模拟OCR',
            'language': self.lang,
            'note': '这是模拟数据，实际使用时PaddleOCR已安装'
        }
    
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
def create_ocr_processor(use_paddleocr=True, use_gpu=False, lang='ch'):
    """创建OCR处理器实例"""
    return OCRProcessor(use_paddleocr=use_paddleocr, use_gpu=use_gpu, lang=lang)


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
            print("请先运行 create_sample_image.py 创建示例图片")
            sys.exit(1)
    
    print("测试OCR处理器...")
    print(f"处理图片: {image_path}")
    
    # 创建处理器
    processor = OCRProcessor(use_paddleocr=True, use_gpu=False, lang='ch')
    
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