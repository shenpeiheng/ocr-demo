"""
PaddleOCR处理器 - 使用PaddleOCR PP-OCRv5模型进行工业图片识别
"""

import os
import time
import numpy as np
import cv2
from PIL import Image
from typing import Dict, List, Any, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaddleOCRProcessor:
    """PaddleOCR处理器类"""
    
    def __init__(self, lang='ch'):
        """
        初始化PaddleOCR处理器
        
        Args:
            lang: 识别语言 ('ch'中文, 'en'英文, 'chinese_cht'繁体中文)
        """
        self.lang = lang
        self.ocr = None
        self.initialized = False
        
        # 本地环境使用用户目录下的.paddleocr
        default_model_dir = os.path.expanduser('~/.paddleocr')
        
        model_dir = os.environ.get('PADDLEOCR_MODEL_DIR', default_model_dir)
        
        # PaddleOCR配置 - 只使用PaddleOCR 3.3.2支持的参数
        # 参考: https://github.com/PaddlePaddle/PaddleOCR
        # 使用PP-OCRv5模型以获得更好的识别效果
        self.config = {
            'lang': lang,
            'ocr_version': 'PP-OCRv5',  # 使用PP-OCRv5模型版本
            'text_det_box_thresh': 0.13,  # 进一步降低检测框阈值，检测更多小文本区域
            'text_det_unclip_ratio': 2.5,  # 增加检测框扩展比例，更好地包围文本
            'text_rec_score_thresh': 0.23,  # 降低识别置信度阈值，保留更多识别结果
            'text_det_limit_type': 'max',  # 检测限制类型
            'text_det_limit_side_len': 1920,  # 增加检测限制边长，处理高分辨率图像
            'text_det_thresh': 0.3,  # 二值化阈值
            'text_detection_model_dir': os.path.join(model_dir, 'det'),  # 检测模型目录
            'text_recognition_model_dir': os.path.join(model_dir, 'rec'),  # 识别模型目录
            'textline_orientation_model_dir': os.path.join(model_dir, 'cls'),  # 分类模型目录
        }
        
        # 尝试初始化PaddleOCR
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """初始化PaddleOCR"""
        try:
            from paddleocr import PaddleOCR
            logger.info(f"初始化PaddleOCR (语言: {self.lang}, 版本: PP-OCRv5)...")
            
            # 检测GPU可用性
            try:
                import paddle
                gpu_available = paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
                if gpu_available:
                    logger.info(f"检测到GPU可用，CUDA设备数量: {paddle.device.cuda.device_count()}")
                    device = 'gpu:0'
                else:
                    logger.info("未检测到GPU，使用CPU模式")
                    device = 'cpu'
            except Exception as gpu_error:
                logger.warning(f"GPU检测失败: {gpu_error}，使用CPU模式")
                device = 'cpu'
            
            # 只使用PaddleOCR 3.3.2支持的参数
            # 更多参数参考 https://blog.csdn.net/qq_38614074/article/details/149041813
            ocr_kwargs = {
                'lang': self.config['lang'],
                'ocr_version': self.config.get('ocr_version', 'PP-OCRv5'),  # 使用PP-OCRv5版本
                #'device': 'gpu:0',  # 使用GPU或CPU
                'text_det_box_thresh': self.config['text_det_box_thresh'],
                'text_det_unclip_ratio': self.config['text_det_unclip_ratio'],
                'text_rec_score_thresh': self.config['text_rec_score_thresh'],
                'text_det_limit_type': self.config['text_det_limit_type'],
                'text_det_limit_side_len': self.config['text_det_limit_side_len'],
                'text_det_thresh': self.config['text_det_thresh'],
                #'use_doc_orientation_classify': False,  # 禁用文档方向分类模块
                'use_doc_unwarping': False,  # 禁用文本图像矫正模块
                #'enable_hpi': True,
                #'enable_mkldnn': True, # CPU 备用时启用 MKL-DNN 加速
                #'cpu_threads': 8,
                #'use_textline_orientation': False,  # 禁用文本行方向分类模块
            }
            
            logger.info(f"PaddleOCR初始化参数: device={device}, text_det_box_thresh={self.config['text_det_box_thresh']}, "
                       f"text_det_unclip_ratio={self.config['text_det_unclip_ratio']}, "
                       f"text_rec_score_thresh={self.config['text_rec_score_thresh']}")
            
            # 添加模型目录参数（如果目录存在）
            # 只有当目录存在时才设置，否则让PaddleOCR使用默认缓存
            text_detection_model_dir = self.config.get('text_detection_model_dir')
            if text_detection_model_dir and os.path.exists(text_detection_model_dir):
                ocr_kwargs['text_detection_model_dir'] = text_detection_model_dir
            
            text_recognition_model_dir = self.config.get('text_recognition_model_dir')
            if text_recognition_model_dir and os.path.exists(text_recognition_model_dir):
                ocr_kwargs['text_recognition_model_dir'] = text_recognition_model_dir
            
            textline_orientation_model_dir = self.config.get('textline_orientation_model_dir')
            if textline_orientation_model_dir and os.path.exists(textline_orientation_model_dir):
                ocr_kwargs['textline_orientation_model_dir'] = textline_orientation_model_dir
            
            self.ocr = PaddleOCR(**ocr_kwargs)
            
            self.initialized = True
            logger.info("PaddleOCR初始化成功")
            
        except ImportError as e:
            logger.error(f"导入PaddleOCR失败: {e}")
            logger.error("请安装PaddleOCR: pip install paddlepaddle paddleocr")
            self.initialized = False
        except Exception as e:
            logger.error(f"PaddleOCR初始化失败: {e}")
            self.initialized = False
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """
        处理图片并进行OCR识别
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            识别结果字典
        """
        logger.info(f"开始处理图片: {image_path}")
        start_time = time.time()
        
        if not self.initialized or self.ocr is None:
            logger.error("PaddleOCR未初始化")
            return self._get_error_result("PaddleOCR未初始化")
        
        try:
            # 读取图片
            if not os.path.exists(image_path):
                return self._get_error_result(f"图片文件不存在: {image_path}")
            
            # 获取原始图片信息
            img = Image.open(image_path)
            img_width, img_height = img.size
            
            # 预处理图片（增强识别效果）
            processed_image = self.preprocess_image(image_path)
            
            # 获取预处理后的图像尺寸
            if processed_image is not None:
                processed_height, processed_width = processed_image.shape[:2]
                logger.info(f"原始图像尺寸: {img_width}x{img_height}, 预处理后尺寸: {processed_width}x{processed_height}")
                
                # 计算缩放比例（如果尺寸不同）
                scale_x = img_width / processed_width if processed_width > 0 else 1.0
                scale_y = img_height / processed_height if processed_height > 0 else 1.0
                
                if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
                    logger.info(f"图像缩放比例: X={scale_x:.3f}, Y={scale_y:.3f}")
            else:
                scale_x = scale_y = 1.0
                logger.warning("预处理图像为空，使用原始图像")
            
            # 使用PaddleOCR进行识别 - 使用predict()方法
            logger.info("正在进行OCR识别...")
            ocr_result = self.ocr.predict(processed_image)
            
            # 解析结果，并应用坐标缩放（如果需要）
            text_items = self._parse_ocr_result(ocr_result, scale_x, scale_y)
            
            # 分析工业图纸模式
            analysis_result = self.analyze_industrial_patterns(text_items)
            
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 构建结果
            results = {
                'success': True,
                'text_items': text_items,
                'total_items': len(text_items),
                'processing_time': round(processing_time, 2),
                'analysis': analysis_result,
                'image_info': {
                    'filename': os.path.basename(image_path),
                    'width': img_width,
                    'height': img_height,
                    'size': os.path.getsize(image_path)
                },
                'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'ocr_engine': 'PaddleOCR PP-OCRv5',
                'language': self.lang
            }
            
            logger.info(f"图片处理完成，识别到 {len(text_items)} 个文本项，耗时 {processing_time:.2f}秒")
            return results
            
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            return self._get_error_result(str(e))
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        预处理图片以增强OCR识别效果，特别针对工业图纸中的数字、字母和标识
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            预处理后的图片数组
        """
        try:
            # 使用OpenCV读取图片
            img = cv2.imread(image_path)
            
            if img is None:
                # 如果OpenCV无法读取，尝试用PIL读取
                pil_img = Image.open(image_path)
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            # 转换为RGB（PaddleOCR需要RGB格式）
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # 对于工业图纸，应用多种增强处理以提高识别率
            enhanced = img.copy()
            
            # 1. 转换为灰度图进行分析
            gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            
            # 2. 分析图像特性，决定最佳预处理策略
            # 计算图像的平均亮度和对比度
            mean_brightness = np.mean(gray)
            contrast = np.std(gray)
            
            logger.info(f"图像分析 - 平均亮度: {mean_brightness:.1f}, 对比度: {contrast:.1f}")
            
            # 3. 自适应预处理策略
            if mean_brightness < 100 or contrast < 40:
                # 低亮度或低对比度图像，需要更强的增强
                logger.info("检测到低亮度/低对比度图像，应用强增强处理")
                
                # 3.1 调整对比度 - CLAHE（限制对比度自适应直方图均衡化）
                lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))  # 增加clipLimit
                l = clahe.apply(l)
                lab = cv2.merge((l, a, b))
                enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
                
                # 3.2 调整亮度和对比度（更强的调整）
                alpha = 1.5  # 对比度控制 (1.0-3.0)
                beta = 30    # 亮度控制 (0-100)
                enhanced = cv2.convertScaleAbs(enhanced, alpha=alpha, beta=beta)
                
            else:
                # 正常图像，使用标准增强
                logger.info("检测到正常图像，应用标准增强处理")
                
                # 3.1 调整对比度 - CLAHE
                lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                l = clahe.apply(l)
                lab = cv2.merge((l, a, b))
                enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
                
                # 3.2 调整亮度和对比度
                alpha = 1.2  # 对比度控制
                beta = 15    # 亮度控制
                enhanced = cv2.convertScaleAbs(enhanced, alpha=alpha, beta=beta)
            
            # 4. 锐化处理 - 增强边缘（特别针对数字和字母）
            # 使用更强的锐化核来增强文本边缘
            kernel = np.array([[-1, -1, -1, -1, -1],
                               [-1,  2,  2,  2, -1],
                               [-1,  2,  8,  2, -1],
                               [-1,  2,  2,  2, -1],
                               [-1, -1, -1, -1, -1]]) / 8.0
            enhanced = cv2.filter2D(enhanced, -1, kernel)
            
            # 5. 降噪处理 - 保留边缘的非局部均值去噪
            enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
            
            # 6. 针对工业图纸的特殊处理
            # 6.1 边缘增强 - 特别针对线条和标识
            gray_enhanced = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray_enhanced, 50, 150)
            
            # 6.2 将边缘叠加回原图，增强线条可见性
            edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            enhanced = cv2.addWeighted(enhanced, 0.9, edges_colored, 0.1, 0)
            
            # 7. 最终转换为RGB
            enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
            
            logger.info("图片预处理完成，应用了自适应对比度增强、边缘锐化、智能降噪和线条增强")
            return enhanced_rgb
            
        except Exception as e:
            logger.warning(f"图片预处理失败: {e}, 使用原始图片")
            # 返回原始图片
            img = cv2.imread(image_path)
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None
    
    def _parse_ocr_result(self, ocr_result, scale_x=1.0, scale_y=1.0) -> List[Dict]:
        """
        解析PaddleOCR返回的结果，支持坐标缩放
        
        Args:
            ocr_result: PaddleOCR返回的结果
            scale_x: X轴缩放比例
            scale_y: Y轴缩放比例
            
        Returns:
            解析后的文本项列表
        """
        text_items = []
        
        if not ocr_result:
            return text_items
        
        try:
            # PaddleOCR 3.3.2返回格式: 包含OCRResult对象的列表
            # OCRResult是一个字典，包含rec_texts, rec_scores, rec_polys等字段
            if isinstance(ocr_result, list) and len(ocr_result) > 0:
                # 获取第一个OCRResult对象
                ocr_data = ocr_result[0]
                
                # 检查是否是OCRResult对象（字典）
                if isinstance(ocr_data, dict):
                    # 获取文本列表和置信度列表
                    rec_texts = ocr_data.get('rec_texts', [])
                    rec_scores = ocr_data.get('rec_scores', [])
                    rec_polys = ocr_data.get('rec_polys', [])
                    
                    logger.info(f"解析到 {len(rec_texts)} 个文本项，缩放比例: X={scale_x:.3f}, Y={scale_y:.3f}")
                    
                    # 遍历所有识别到的文本
                    for i in range(len(rec_texts)):
                        text = rec_texts[i]
                        confidence = float(rec_scores[i]) if i < len(rec_scores) else 0.8
                        
                        # 获取多边形坐标
                        poly = rec_polys[i] if i < len(rec_polys) else None
                        
                        # 计算边界框
                        try:
                            if poly is not None and isinstance(poly, np.ndarray):
                                # 多边形坐标数组，形状为 (n, 2)
                                # 应用缩放比例
                                scaled_poly = poly.copy()
                                scaled_poly[:, 0] = scaled_poly[:, 0] * scale_x
                                scaled_poly[:, 1] = scaled_poly[:, 1] * scale_y
                                
                                x_coords = scaled_poly[:, 0]
                                y_coords = scaled_poly[:, 1]
                                
                                left = int(np.min(x_coords))
                                top = int(np.min(y_coords))
                                right = int(np.max(x_coords))
                                bottom = int(np.max(y_coords))
                                width = right - left
                                height = bottom - top
                                
                                # 将缩放后的多边形转换为列表格式
                                box_points = scaled_poly.tolist()
                                
                                logger.debug(f"文本 '{text}' 坐标: left={left}, top={top}, width={width}, height={height}")
                            else:
                                # 如果没有多边形数据，使用默认值
                                left = top = right = bottom = width = height = 0
                                box_points = [[0, 0], [0, 0], [0, 0], [0, 0]]
                        except Exception as e:
                            logger.warning(f"解析多边形坐标失败: {e}, 使用默认值")
                            left = top = right = bottom = width = height = 0
                            box_points = [[0, 0], [0, 0], [0, 0], [0, 0]]
                        
                        # 确定文本类型
                        text_type = self._determine_text_type(text)
                        
                        text_items.append({
                            'id': i + 1,
                            'text': text,
                            'confidence': confidence,
                            'location': {
                                'left': left,
                                'top': top,
                                'width': width,
                                'height': height,
                                'right': right,
                                'bottom': bottom,
                                'points': box_points  # 保存缩放后的点坐标
                            },
                            'type': text_type
                        })
                else:
                    logger.warning(f"OCR结果格式不是字典: {type(ocr_data)}")
            else:
                logger.warning(f"OCR结果为空或格式不正确: {type(ocr_result)}")
                
        except Exception as e:
            logger.error(f"解析OCR结果失败: {e}")
            # 尝试回退到旧格式解析
            try:
                text_items = self._parse_ocr_result_legacy(ocr_result, scale_x, scale_y)
            except Exception as e2:
                logger.error(f"回退解析也失败: {e2}")
        
        return text_items
    
    def _parse_ocr_result_legacy(self, ocr_result, scale_x=1.0, scale_y=1.0) -> List[Dict]:
        """
        解析旧版PaddleOCR返回的结果（兼容性回退），支持坐标缩放
        
        Args:
            ocr_result: PaddleOCR返回的结果
            scale_x: X轴缩放比例
            scale_y: Y轴缩放比例
            
        Returns:
            解析后的文本项列表
        """
        text_items = []
        
        if not ocr_result or not ocr_result[0]:
            return text_items
        
        for i, item in enumerate(ocr_result[0]):
            if not item:
                continue
                
            # 旧版PaddleOCR返回格式: [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], (text, confidence)]
            box_points = item[0]  # 四个点的坐标
            text_info = item[1]   # (文本, 置信度)
            
            if len(text_info) >= 2:
                text = text_info[0]
                confidence = float(text_info[1])
            else:
                text = text_info[0] if isinstance(text_info[0], str) else ""
                confidence = 0.8
            
            # 计算边界框 - 添加类型检查和错误处理
            try:
                # 确保所有坐标点都是数字
                cleaned_points = []
                for point in box_points:
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        x = float(point[0]) if isinstance(point[0], (int, float, str)) and str(point[0]).replace('.', '').isdigit() else 0
                        y = float(point[1]) if isinstance(point[1], (int, float, str)) and str(point[1]).replace('.', '').isdigit() else 0
                        # 应用缩放比例
                        x = x * scale_x
                        y = y * scale_y
                        cleaned_points.append([x, y])
                    else:
                        cleaned_points.append([0, 0])
                
                points = np.array(cleaned_points, dtype=np.float32)
                x_coords = points[:, 0]
                y_coords = points[:, 1]
                
                left = int(np.min(x_coords))
                top = int(np.min(y_coords))
                right = int(np.max(x_coords))
                bottom = int(np.max(y_coords))
                width = right - left
                height = bottom - top
                
                # 更新缩放后的点坐标
                scaled_box_points = cleaned_points
            except Exception as e:
                logger.warning(f"解析边界框坐标失败: {e}, 使用默认值")
                left = top = right = bottom = width = height = 0
                scaled_box_points = [[0, 0], [0, 0], [0, 0], [0, 0]]
            
            # 确定文本类型
            text_type = self._determine_text_type(text)
            
            text_items.append({
                'id': i + 1,
                'text': text,
                'confidence': confidence,
                'location': {
                    'left': left,
                    'top': top,
                    'width': width,
                    'height': height,
                    'right': right,
                    'bottom': bottom,
                    'points': scaled_box_points  # 保存缩放后的点坐标
                },
                'type': text_type
            })
        
        return text_items
    
    def _determine_text_type(self, text: str) -> str:
        """
        根据文本内容确定类型，特别针对工业图纸中的数字、字母、字符和标识
        
        Args:
            text: 识别到的文本
            
        Returns:
            文本类型
        """
        text_lower = text.lower()
        text_clean = text.strip()
        
        # 1. 检查是否是尺寸标注（包含数字和尺寸单位/符号）
        dimension_patterns = [
            'φ', 'ø', 'dia', '×', '±', 'mm', 'cm', 'm', 'inch', '"', "'",
            'r', '半径', '直径', 'diameter', 'radius', '厚度', 'thickness',
            '宽度', 'width', '高度', 'height', '长度', 'length', '深', 'depth'
        ]
        dimension_symbols = ['φ', 'ø', '×', '±', '°', '▽', '△', '□', '◇']
        
        # 检查是否包含尺寸符号或单位，并且有数字
        has_dimension_symbol = any(symbol in text for symbol in dimension_symbols)
        has_dimension_pattern = any(pattern in text_lower for pattern in dimension_patterns)
        has_numbers = any(c.isdigit() for c in text)
        
        if (has_dimension_symbol or has_dimension_pattern) and has_numbers:
            return 'dimension'
        
        # 2. 检查是否是公差标注
        tolerance_patterns = [
            '±', '公差', 'tolerance', '+/-', 'h7', 'h6', 'g6', 'it7', 'it8', 'it9',
            'js', 'k6', 'm6', 'n6', 'p6', 'r6', 's6', 't6', 'u6', 'v6', 'x6', 'y6', 'z6',
            '配合', 'fit', '间隙', 'clearance', '过盈', 'interference'
        ]
        if any(pattern in text_lower for pattern in tolerance_patterns):
            return 'tolerance'
        
        # 3. 检查是否是材料信息
        material_patterns = [
            '钢', 'steel', '铝', 'aluminum', '铜', 'copper', '材料', 'material',
            '不锈钢', 'stainless', '铸铁', 'cast iron', '合金', 'alloy', '塑料', 'plastic',
            '45#', 'q235', 'q345', 'a3', 'a36', '304', '316', '6061', '7075'
        ]
        if any(pattern in text_lower for pattern in material_patterns):
            return 'material'
        
        # 4. 检查是否是技术要求
        technical_patterns = [
            '粗糙度', 'ra', '热处理', 'hrc', '调质', '去毛刺', '检验', '标准', 'gb/t',
            '淬火', 'quench', '回火', 'temper', '退火', 'anneal', '表面处理', 'surface',
            '镀锌', 'galvanized', '镀铬', 'chrome', '喷涂', 'paint', '焊接', 'weld',
            '倒角', 'chamfer', '圆角', 'fillet', '抛光', 'polish'
        ]
        if any(pattern in text_lower for pattern in technical_patterns):
            return 'technical'
        
        # 5. 检查是否是图纸信息
        drawing_patterns = [
            '图纸', 'drawing', '编号', 'no.', '版本', 'version', '比例', 'scale',
            '图号', 'dwg no.', '零件号', 'part no.', '项目', 'project', '名称', 'name',
            '设计', 'design', '审核', 'check', '批准', 'approve', '日期', 'date'
        ]
        if any(pattern in text_lower for pattern in drawing_patterns):
            return 'drawing_info'
        
        # 6. 检查是否是数量信息
        quantity_patterns = ['数量', 'qty', 'quantity', '件', 'pcs', '个', '套', 'set']
        if any(pattern in text_lower for pattern in quantity_patterns) and has_numbers:
            return 'quantity'
        
        # 7. 检查是否是角度标注
        if '°' in text or '度' in text_lower:
            return 'angle'
        
        # 8. 检查是否是表面粗糙度符号
        roughness_symbols = ['▽', '▽▽', '▽▽▽', 'ra', 'rz']
        if any(symbol in text for symbol in roughness_symbols):
            return 'surface_roughness'
        
        # 9. 检查是否是几何公差符号
        geometric_symbols = ['◎', '∥', '⊥', '∠', '⌒', '○', '□', '◇', '△']
        if any(symbol in text for symbol in geometric_symbols):
            return 'geometric_tolerance'
        
        # 10. 检查是否是焊接符号
        weld_patterns = ['焊缝', 'weld', '焊角', '焊脚', '焊接符号']
        if any(pattern in text_lower for pattern in weld_patterns):
            return 'weld_symbol'
        
        # 11. 纯数字或字母组合（可能是编号或代码）
        if len(text_clean) <= 10 and (text_clean.isdigit() or text_clean.isalpha()):
            return 'code'
        
        # 12. 包含特殊工业字符的组合
        industrial_chars = ['-', '/', '(', ')', '[', ']', '{', '}', '<', '>', '=', '+', '*', '#', '@']
        if any(char in text for char in industrial_chars) and (has_numbers or any(c.isalpha() for c in text)):
            return 'industrial_symbol'
        
        return 'text'
    
    def analyze_industrial_patterns(self, text_items: List[Dict]) -> Dict[str, Any]:
        """
        分析工业图纸模式，支持更多工业标识类型
        
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
        drawing_info_items = []
        quantity_items = []
        angle_items = []
        surface_roughness_items = []
        geometric_tolerance_items = []
        weld_symbol_items = []
        code_items = []
        industrial_symbol_items = []
        
        for item in text_items:
            item_type = item.get('type', 'text')
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
            
            # 分类存储
            if item_type == 'dimension':
                dimension_items.append(item)
            elif item_type == 'tolerance':
                tolerance_items.append(item)
            elif item_type == 'material':
                material_items.append(item)
            elif item_type == 'technical':
                technical_items.append(item)
            elif item_type == 'drawing_info':
                drawing_info_items.append(item)
            elif item_type == 'quantity':
                quantity_items.append(item)
            elif item_type == 'angle':
                angle_items.append(item)
            elif item_type == 'surface_roughness':
                surface_roughness_items.append(item)
            elif item_type == 'geometric_tolerance':
                geometric_tolerance_items.append(item)
            elif item_type == 'weld_symbol':
                weld_symbol_items.append(item)
            elif item_type == 'code':
                code_items.append(item)
            elif item_type == 'industrial_symbol':
                industrial_symbol_items.append(item)
        
        # 计算平均置信度
        confidences = [item.get('confidence', 0) for item in text_items]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # 计算数字和字母识别率
        digit_count = 0
        letter_count = 0
        special_char_count = 0
        
        for item in text_items:
            text = item.get('text', '')
            digit_count += sum(1 for c in text if c.isdigit())
            letter_count += sum(1 for c in text if c.isalpha())
            special_char_count += sum(1 for c in text if not c.isalnum() and c != ' ')
        
        return {
            'type_distribution': type_counts,
            'dimension_count': len(dimension_items),
            'tolerance_count': len(tolerance_items),
            'material_count': len(material_items),
            'technical_count': len(technical_items),
            'drawing_info_count': len(drawing_info_items),
            'quantity_count': len(quantity_items),
            'angle_count': len(angle_items),
            'surface_roughness_count': len(surface_roughness_items),
            'geometric_tolerance_count': len(geometric_tolerance_items),
            'weld_symbol_count': len(weld_symbol_items),
            'code_count': len(code_items),
            'industrial_symbol_count': len(industrial_symbol_items),
            'total_items': len(text_items),
            'average_confidence': round(avg_confidence, 3),
            'character_analysis': {
                'total_digits': digit_count,
                'total_letters': letter_count,
                'total_special_chars': special_char_count,
                'digit_ratio': round(digit_count / max(1, len(''.join(item.get('text', '') for item in text_items))), 3) if text_items else 0
            }
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
def create_paddle_ocr_processor(lang='ch'):
    """创建PaddleOCR处理器实例"""
    return PaddleOCRProcessor(lang=lang)


if __name__ == '__main__':
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # 使用示例图片
        image_path = "../frontend/uploads/399ecd60879e4b08b87cdc506d27624f.png"
        if not os.path.exists(image_path):
            print(f"示例图片不存在: {image_path}")
            print("请上传真实图片进行测试，或创建示例图片")
            print("用法: python paddle_ocr_processor.py <图片路径>")
            sys.exit(1)
    
    print("测试PaddleOCR处理器...")
    print(f"处理图片: {image_path}")
    
    # 创建处理器
    processor = PaddleOCRProcessor(lang='ch')
    
    if not processor.initialized:
        print("PaddleOCR初始化失败")
        sys.exit(1)
    
    # 处理图片
    result = processor.process_image(image_path)
    
    if result['success']:
        print(f"\n识别成功!")
        print(f"识别到 {result['total_items']} 个文本项")
        print(f"处理时间: {result['processing_time']}秒")
        
        # 显示分析结果
        analysis = result['analysis']
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
