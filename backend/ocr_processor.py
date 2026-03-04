"""
OCR处理器 - 支持多种OCR引擎的工业图片识别系统
支持PaddleOCR PP-OCRv5和OpenAI VL（ModelScope API）
"""

import os
import time
from typing import Dict, List, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRProcessor:
    """OCR处理器类，支持多种OCR引擎"""
    
    def __init__(self, engine=None, lang='ch'):
        """
        初始化OCR处理器
        
        Args:
            engine: OCR引擎类型 ('paddleocr', 'openai_vl', 'auto')
                   auto: 根据环境变量OCR_ENGINE自动选择
            lang: 识别语言 ('ch'中文, 'en'英文) - 仅对PaddleOCR有效
        """
        self.lang = lang
        self.engine_type = engine or os.getenv('OCR_ENGINE', 'paddleocr').lower()
        self.paddle_processor = None
        self.openai_vl_processor = None
        self.current_engine = None
        
        # 初始化选定的引擎
        self._initialize_engine()
    
    def _initialize_engine(self):
        """初始化OCR引擎"""
        if self.engine_type == 'auto':
            # 根据环境变量自动选择
            env_engine = os.getenv('OCR_ENGINE', 'paddleocr').lower()
            if env_engine in ['openai', 'openai_vl', 'modelscope']:
                self.engine_type = 'openai_vl'
            else:
                self.engine_type = 'paddleocr'
        
        if self.engine_type == 'paddleocr':
            self._initialize_paddleocr()
        elif self.engine_type in ['openai_vl', 'openai', 'modelscope']:
            self._initialize_openai_vl()
        else:
            logger.warning(f"未知的OCR引擎类型: {self.engine_type}，默认使用PaddleOCR")
            self._initialize_paddleocr()
    
    def _initialize_paddleocr(self):
        """初始化PaddleOCR处理器"""
        try:
            from paddle_ocr_processor import PaddleOCRProcessor
            self.paddle_processor = PaddleOCRProcessor(lang=self.lang)
            if self.paddle_processor.initialized:
                self.current_engine = 'paddleocr'
                logger.info("PaddleOCR处理器初始化成功")
            else:
                raise RuntimeError("PaddleOCR初始化失败")
        except ImportError as e:
            logger.error(f"导入PaddleOCR处理器失败: {e}")
            logger.error("请安装PaddleOCR: pip install paddlepaddle paddleocr")
            raise RuntimeError(f"PaddleOCR未安装: {e}")
        except Exception as e:
            logger.error(f"PaddleOCR处理器初始化失败: {e}")
            raise RuntimeError(f"PaddleOCR初始化失败: {e}")
    
    def _initialize_openai_vl(self):
        """初始化OpenAI VL处理器"""
        try:
            from openai_vl_processor import OpenAIVLProcessor
            self.openai_vl_processor = OpenAIVLProcessor()
            if self.openai_vl_processor.initialized:
                self.current_engine = 'openai_vl'
                logger.info("OpenAI VL处理器初始化成功")
            else:
                logger.warning("OpenAI VL处理器初始化失败，尝试使用PaddleOCR作为备选")
                self._initialize_paddleocr()
        except ImportError as e:
            logger.error(f"导入OpenAI VL处理器失败: {e}")
            logger.error("OpenAI VL处理器依赖缺失，尝试使用PaddleOCR")
            self._initialize_paddleocr()
        except Exception as e:
            logger.error(f"OpenAI VL处理器初始化失败: {e}")
            logger.error("尝试使用PaddleOCR作为备选")
            self._initialize_paddleocr()
    
    def process_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        """
        处理图片并进行OCR识别
        
        Args:
            image_path: 图片文件路径
            prompt: 提示词（仅对OpenAI VL有效）
            
        Returns:
            识别结果字典
        """
        logger.info(f"开始处理图片: {image_path}，使用引擎: {self.current_engine}")
        
        try:
            if self.current_engine == 'paddleocr' and self.paddle_processor:
                return self.paddle_processor.process_image(image_path)
            elif self.current_engine == 'openai_vl' and self.openai_vl_processor:
                return self.openai_vl_processor.process_image(image_path, prompt)
            else:
                logger.error(f"当前引擎 {self.current_engine} 未正确初始化")
                return self._get_error_result(f"OCR引擎 {self.current_engine} 未正确初始化")
                
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            return self._get_error_result(str(e))
    
    def process_image_with_engine(self, image_path: str, engine: str, prompt: str = None) -> Dict[str, Any]:
        """
        使用指定引擎处理图片
        
        Args:
            image_path: 图片文件路径
            engine: 指定使用的引擎 ('paddleocr' 或 'openai_vl')
            prompt: 提示词（仅对OpenAI VL有效）
            
        Returns:
            识别结果字典
        """
        logger.info(f"使用指定引擎 {engine} 处理图片: {image_path}")
        
        try:
            if engine == 'paddleocr':
                # 确保PaddleOCR处理器已初始化
                if not self.paddle_processor:
                    self._initialize_paddleocr()
                return self.paddle_processor.process_image(image_path)
                
            elif engine == 'openai_vl':
                # 确保OpenAI VL处理器已初始化
                if not self.openai_vl_processor:
                    self._initialize_openai_vl()
                return self.openai_vl_processor.process_image(image_path, prompt)
                
            else:
                logger.error(f"不支持的引擎类型: {engine}")
                return self._get_error_result(f"不支持的引擎类型: {engine}")
                
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
                'confidence': item.get('confidence', 0),
                'region': item.get('region', '')  # OpenAI VL特有字段
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
    
    def generate_markdown_table(self, text_items: List[Dict]) -> str:
        """
        生成Markdown表格格式的输出
        
        Args:
            text_items: 文本项列表
            
        Returns:
            Markdown表格字符串
        """
        if not text_items:
            return "未识别到任何文本信息。"
        
        # 表头
        markdown = "| 序号 | 内容 | 类型 | 区域 | 坐标 |\n"
        markdown += "|------|------|------|------|------|\n"
        
        # 表格内容
        for item in text_items:
            index = item.get('id', 0)
            content = item.get('text', '')
            item_type = item.get('type', 'text')
            region = item.get('region', item.get('location_description', '未知区域'))
            
            # 获取坐标
            location = item.get('location', {})
            x = location.get('left', 0)
            y = location.get('top', 0)
            coordinates = f"({x}, {y})"
            
            # 转义Markdown特殊字符
            content_escaped = content.replace('|', '\\|')
            item_type_escaped = item_type.replace('|', '\\|')
            region_escaped = region.replace('|', '\\|')
            
            markdown += f"| {index} | {content_escaped} | {item_type_escaped} | {region_escaped} | {coordinates} |\n"
        
        # 添加统计信息
        markdown += f"\n**统计信息**: 共识别到 {len(text_items)} 个信息项。\n"
        
        # 类型分布
        type_counts = {}
        for item in text_items:
            item_type = item.get('type', 'text')
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
        
        if type_counts:
            markdown += "**类型分布**: "
            type_list = [f"{k}({v})" for k, v in type_counts.items()]
            markdown += ", ".join(type_list) + "\n"
        
        return markdown
    
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
            'ocr_engine': self.current_engine or 'unknown'
        }
    
    def batch_process(self, image_paths: List[str], prompts: List[str] = None) -> List[Dict[str, Any]]:
        """
        批量处理图片
        
        Args:
            image_paths: 图片路径列表
            prompts: 提示词列表（仅对OpenAI VL有效）
            
        Returns:
            处理结果列表
        """
        results = []
        for i, image_path in enumerate(image_paths):
            prompt = prompts[i] if prompts and i < len(prompts) else None
            result = self.process_image(image_path, prompt)
            results.append(result)
        return results
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取当前引擎信息"""
        return {
            'current_engine': self.current_engine,
            'engine_type': self.engine_type,
            'language': self.lang,
            'paddleocr_available': self.paddle_processor is not None,
            'openai_vl_available': self.openai_vl_processor is not None
        }


# 工厂函数，便于使用
def create_ocr_processor(engine=None, lang='ch'):
    """创建OCR处理器实例"""
    return OCRProcessor(engine=engine, lang=lang)


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
            print("用法: python ocr_processor.py <图片路径> [引擎类型]")
            sys.exit(1)
    
    # 获取引擎参数
    engine_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("测试OCR处理器...")
    print(f"处理图片: {image_path}")
    print(f"引擎类型: {engine_arg or '自动选择'}")
    
    try:
        # 创建处理器
        processor = OCRProcessor(engine=engine_arg, lang='ch')
        
        # 显示引擎信息
        engine_info = processor.get_engine_info()
        print(f"\n引擎信息:")
        print(f"  当前引擎: {engine_info['current_engine']}")
        print(f"  PaddleOCR可用: {engine_info['paddleocr_available']}")
        print(f"  OpenAI VL可用: {engine_info['openai_vl_available']}")
        
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
                if 'region' in item:
                    print(f"     区域: {item['region']}")
            
            # 生成Markdown表格
            print(f"\nMarkdown表格预览:")
            markdown_table = processor.generate_markdown_table(result['text_items'][:10])  # 只显示前10行
            print(markdown_table[:500] + "..." if len(markdown_table) > 500 else markdown_table)
            
        else:
            print(f"\n识别失败: {result.get('error', '未知错误')}")
    except Exception as e:
        print(f"\nOCR处理器初始化失败: {e}")
        print("请检查相关依赖是否正确安装")
        sys.exit(1)