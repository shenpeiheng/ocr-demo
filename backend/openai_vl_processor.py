"""
OpenAI VL处理器 - 使用OpenAI兼容的视觉语言模型进行机械工程图纸识别
支持ModelScope API（中国版OpenAI兼容API）
"""

import os
import time
import base64
import json
import logging
from io import BytesIO
from typing import Dict, List, Any, Optional
from PIL import Image
import requests
from prompt_manager import get_prompt
from config import Config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_INPUT_MAX_DIMENSION = int(os.getenv('MODELSCOPE_MAX_IMAGE_DIMENSION', '2048'))
SUPPORTED_INLINE_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

class OpenAIVLProcessor:
    """OpenAI视觉语言模型处理器类"""
    
    def __init__(self, api_key=None, base_url=None, model=None):
        """
        初始化OpenAI VL处理器
        
        Args:
            api_key: API密钥（默认为环境变量MODELSCOPE_API_KEY）
            base_url: API基础URL（默认为环境变量MODELSCOPE_BASE_URL）
            model: 模型名称（默认为环境变量MODELSCOPE_MODEL）
        """
        # 从环境变量获取配置
        self.api_key = api_key or os.getenv('MODELSCOPE_API_KEY',"ms-83c39231-b66e-4ed8-8a2b-52c9ded22a51")
        self.base_url = base_url or os.getenv('MODELSCOPE_BASE_URL',"https://api-inference.modelscope.cn/v1")
        self.model = model or Config.MODELSCOPE_MODEL
        
        # 验证配置
        if not self.api_key:
            logger.warning("未设置API密钥，请设置MODELSCOPE_API_KEY环境变量")
            self.initialized = False
            return
            
        if not self.base_url:
            logger.warning("未设置API基础URL，使用默认ModelScope API")
            self.base_url = "https://api-inference.modelscope.cn/v1"
            
        self.initialized = True
        logger.info(f"OpenAI VL处理器初始化成功 (模型: {self.model}, API: {self.base_url})")
    
    def process_image(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        """
        处理图片并使用OpenAI VL进行识别
        
        Args:
            image_path: 图片文件路径
            prompt: 自定义提示词（如果为None则使用默认机械工程图纸提示词）
            
        Returns:
            识别结果字典
        """
        logger.info(f"开始使用OpenAI VL处理图片: {image_path}")
        start_time = time.time()
        
        if not self.initialized:
            logger.error("OpenAI VL处理器未初始化")
            return self._get_error_result("OpenAI VL处理器未初始化")
        
        try:
            # 准备模型输入图，超出模型限制时按比例压缩
            image_payload = self._prepare_image_for_api(image_path)
            image_base64 = image_payload['base64']
            img_width = image_payload['original_width']
            img_height = image_payload['original_height']
            api_img_width = image_payload['api_width']
            api_img_height = image_payload['api_height']
            
            # 使用默认提示词（如果未提供）
            if prompt is None:
                prompt = self._get_default_mechanical_drawing_prompt()
            
            # 调用OpenAI VL API
            logger.info("调用OpenAI VL API进行识别...")
            response = self._call_openai_vl_api(image_base64, prompt, image_payload['mime_type'])
            
            # 解析API响应
            if response.get('success', False):
                # 解析响应内容
                parsed_results = self._parse_api_response(response['content'], api_img_width, api_img_height)
                if image_payload['resized']:
                    self._scale_text_items_to_original(
                        parsed_results.get('text_items', []),
                        img_width / api_img_width,
                        img_height / api_img_height
                    )
                
                # 计算处理时间
                processing_time = time.time() - start_time
                
                # 构建结果
                results = {
                    'success': True,
                    'text_items': parsed_results.get('text_items', []),
                    'total_items': parsed_results.get('total_items', 0),
                    'processing_time': round(processing_time, 2),
                    'analysis': parsed_results.get('analysis', {}),
                    'image_info': {
                        'filename': os.path.basename(image_path),
                        'width': img_width,
                        'height': img_height,
                        'size': os.path.getsize(image_path)
                    },
                    'model_input_info': {
                        'width': api_img_width,
                        'height': api_img_height,
                        'resized': image_payload['resized'],
                        'max_dimension': MODEL_INPUT_MAX_DIMENSION
                    },
                    'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'ocr_engine': 'OpenAI VL',
                    'model': self.model,
                    'prompt_used': prompt[:100] + "..." if len(prompt) > 100 else prompt,
                    'raw_response': response.get('content', '')
                }
                
                logger.info(f"OpenAI VL处理完成，识别到 {results['total_items']} 个信息项，耗时 {processing_time:.2f}秒")
                return results
            else:
                logger.error(f"OpenAI VL API调用失败: {response.get('error', '未知错误')}")
                return self._get_error_result(f"API调用失败: {response.get('error', '未知错误')}")
                
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            return self._get_error_result(str(e))
    
    def _image_to_base64(self, image_path: str) -> str:
        """
        将图片转换为base64编码
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            base64编码的图片字符串
        """
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
        except Exception as e:
            logger.error(f"图片转换为base64失败: {e}")
            raise

    def _prepare_image_for_api(self, image_path: str) -> Dict[str, Any]:
        """
        准备视觉模型输入图片，保证宽高不超过模型限制。
        """
        try:
            with Image.open(image_path) as img:
                img.load()
                original_width, original_height = img.size
                original_format = img.format
                original_mime_type = Image.MIME.get(original_format, 'image/png')
                max_dimension = max(original_width, original_height)

                if max_dimension <= MODEL_INPUT_MAX_DIMENSION and original_mime_type in SUPPORTED_INLINE_IMAGE_MIME_TYPES:
                    with open(image_path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

                    return {
                        'base64': encoded_string,
                        'mime_type': original_mime_type,
                        'original_width': original_width,
                        'original_height': original_height,
                        'api_width': original_width,
                        'api_height': original_height,
                        'resized': False
                    }

                api_img = img.copy()
                resized = False
                if max_dimension > MODEL_INPUT_MAX_DIMENSION:
                    scale = MODEL_INPUT_MAX_DIMENSION / max_dimension
                    api_width = max(1, int(original_width * scale))
                    api_height = max(1, int(original_height * scale))
                    resample_filter = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS')
                    api_img = api_img.resize((api_width, api_height), resample_filter)
                    resized = True
                    logger.info(
                        f"图片尺寸超过模型限制，已按比例压缩: "
                        f"{original_width}x{original_height} -> {api_width}x{api_height}"
                    )
                else:
                    api_width, api_height = original_width, original_height

                if api_img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', api_img.size, (255, 255, 255))
                    alpha = api_img.getchannel('A')
                    background.paste(api_img.convert('RGB'), mask=alpha)
                    api_img = background
                elif api_img.mode == 'P':
                    api_img = api_img.convert('RGBA')
                    background = Image.new('RGB', api_img.size, (255, 255, 255))
                    background.paste(api_img.convert('RGB'), mask=api_img.getchannel('A'))
                    api_img = background
                elif api_img.mode not in ('RGB', 'L'):
                    api_img = api_img.convert('RGB')

                buffer = BytesIO()
                api_img.save(buffer, format='PNG', optimize=True)
                encoded_string = base64.b64encode(buffer.getvalue()).decode('utf-8')

                return {
                    'base64': encoded_string,
                    'mime_type': 'image/png',
                    'original_width': original_width,
                    'original_height': original_height,
                    'api_width': api_width,
                    'api_height': api_height,
                    'resized': resized
                }
        except Exception as e:
            logger.error(f"准备模型输入图片失败: {e}")
            raise

    def _scale_text_items_to_original(self, text_items: List[Dict], scale_x: float, scale_y: float) -> None:
        """
        将模型输入图上的坐标映射回原图坐标，保证前端叠框位置一致。
        """
        if not text_items:
            return

        for item in text_items:
            location = item.get('location')
            if not isinstance(location, dict):
                continue

            for key in ('left', 'width', 'right'):
                value = location.get(key)
                if isinstance(value, (int, float)):
                    location[key] = int(round(value * scale_x))

            for key in ('top', 'height', 'bottom'):
                value = location.get(key)
                if isinstance(value, (int, float)):
                    location[key] = int(round(value * scale_y))
    
    def _get_default_mechanical_drawing_prompt(self) -> str:
        """
        获取默认的机械工程图纸识别提示词
        
        Returns:
            提示词字符串
        """
        return get_prompt('mechanical_drawing_standard')
    
    def _call_openai_vl_api(self, image_base64: str, prompt: str, mime_type: str = 'image/jpeg') -> Dict[str, Any]:
        """
        调用OpenAI VL API
        
        Args:
            image_base64: base64编码的图片
            prompt: 提示词
            mime_type: 图片MIME类型
            
        Returns:
            API响应字典
        """
        try:
            # 构建API请求
            url = f"{self.base_url}/chat/completions"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 8000,  # 增加到8000以获取更完整的输出
                "temperature": 0.01  # 降低到0.01以提高确定性和精度
            }
            
            logger.info(f"发送OpenAI VL API请求到: {url}")
            logger.info(f"使用模型: {self.model}")
            
            # 发送请求
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            # 检查响应
            if response.status_code == 200:
                response_data = response.json()
                
                # 提取响应内容
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    content = response_data['choices'][0]['message']['content']
                    
                    # 记录使用情况
                    usage = response_data.get('usage', {})
                    logger.info(f"API调用成功 - 令牌使用: 输入{usage.get('prompt_tokens', 0)} / 输出{usage.get('completion_tokens', 0)}")
                    
                    return {
                        'success': True,
                        'content': content,
                        'usage': usage
                    }
                else:
                    logger.error(f"API响应格式异常: {response_data}")
                    return {
                        'success': False,
                        'error': f"API响应格式异常: {response_data}"
                    }
            else:
                logger.error(f"API调用失败: 状态码 {response.status_code}, 响应: {response.text}")
                return {
                    'success': False,
                    'error': f"API调用失败: 状态码 {response.status_code}",
                    'details': response.text[:500]
                }
                
        except requests.exceptions.Timeout:
            logger.error("API调用超时")
            return {
                'success': False,
                'error': "API调用超时"
            }
        except Exception as e:
            logger.error(f"API调用异常: {e}")
            return {
                'success': False,
                'error': f"API调用异常: {str(e)}"
            }
    
    def _parse_api_response(self, response_content: str, img_width: int, img_height: int) -> Dict[str, Any]:
        """
        解析OpenAI VL API的响应内容
        
        Args:
            response_content: API返回的文本内容
            img_width: 图片宽度
            img_height: 图片高度
            
        Returns:
            解析后的结果字典
        """
        try:
            logger.info("开始解析OpenAI VL API响应...")
            
            # 首先尝试提取Markdown表格
            text_items = []
            
            # 查找Markdown表格的开始和结束
            lines = response_content.split('\n')
            in_table = False
            table_lines = []
            
            for line in lines:
                # 检测表格开始：包含 | 且包含 ---（分隔线）或 序号/内容/坐标 等表头关键字
                has_pipe = '|' in line
                is_table_header = '---' in line or '序号' in line or '内容' in line or '坐标' in line or '类型' in line or '区域' in line
                
                if has_pipe and (is_table_header or in_table):
                    if not in_table:
                        # 检查这一行是否真的是表格（至少2个 |）
                        if line.count('|') >= 2:
                            in_table = True
                            table_lines.append(line)
                    else:
                        table_lines.append(line)
                elif in_table and has_pipe:
                    table_lines.append(line)
                elif in_table and not has_pipe and line.strip():
                    # 表格结束
                    break
            
            # 解析表格行
            if len(table_lines) >= 3:  # 至少表头、分隔线和一行数据
                # 跳过表头和分隔线
                for i in range(2, len(table_lines)):
                    line = table_lines[i].strip()
                    if not line or not '|' in line:
                        continue
                    
                    # 分割表格单元格
                    cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                    
                    if len(cells) >= 5:  # 至少有序号、内容、类型、区域、坐标
                        try:
                            # 解析序号
                            index = int(cells[0]) if cells[0].isdigit() else len(text_items) + 1
                            
                            # 内容
                            content = cells[1]
                            
                            # 类型
                            item_type = cells[2]
                            
                            # 区域
                            region = cells[3]
                            
                            # 坐标 - 尝试解析坐标字符串
                            coord_text = cells[4]
                            left, top, width, height = self._parse_coordinates(coord_text, img_width, img_height, region)
                            
                            # 添加到结果列表
                            text_items.append({
                                'id': index,
                                'text': content,
                                'confidence': 0.95,  # OpenAI VL没有置信度，使用默认高值
                                'location': {
                                    'left': left,
                                    'top': top,
                                    'width': width,  # 使用解析出的宽度
                                    'height': height,  # 使用解析出的高度
                                    'right': width,
                                    'bottom': height
                                },
                                'type': item_type,
                                'region': region,
                                'coordinates_text': coord_text
                            })
                        except Exception as e:
                            logger.warning(f"解析表格行失败: {line}, 错误: {e}")
                            continue
            
            # 如果表格解析失败，尝试其他格式
            if not text_items:
                logger.warning("Markdown表格解析失败，尝试其他格式解析")
                text_items = self._parse_fallback_format(response_content, img_width, img_height)
            
            # 尝试从JSON代码块中提取更多信息（即使表格已经解析到了一些）
            json_items = self._parse_json_format(response_content, img_width, img_height)
            if json_items:
                # 合并JSON提取的项（去重）
                existing_texts = {item.get('text', '') for item in text_items}
                for item in json_items:
                    if item.get('text', '') not in existing_texts:
                        text_items.append(item)
                        existing_texts.add(item.get('text', ''))
                logger.info(f"从JSON补充了 {len(json_items)} 个项，合并后共 {len(text_items)} 个")
            
            # 分析结果
            analysis_result = self._analyze_results(text_items)
            
            return {
                'text_items': text_items,
                'total_items': len(text_items),
                'analysis': analysis_result,
                'raw_response_preview': response_content[:200] + "..." if len(response_content) > 200 else response_content
            }
            
        except Exception as e:
            logger.error(f"解析API响应失败: {e}")
            # 返回空结果
            return {
                'text_items': [],
                'total_items': 0,
                'analysis': {},
                'error': f"解析失败: {str(e)}"
            }
    
    def _parse_coordinates(self, coord_text: str, img_width: int, img_height: int, region: str) -> tuple:
        """
        解析坐标文本，支持多种格式，返回 (left, top, width, height) 绝对像素坐标。
        
        Qwen-VL 系列模型的 <box> 格式坐标范围为 [0, 1000]（归一化坐标），
        需要映射到实际图片尺寸。
        """
        try:
            import re
            
            # 格式1: Qwen-VL 原生 <box> 格式
            # 模型输出格式极其不稳定，可能的各种变体：
            #   <box>(x1,y1),(x2,y2)</box>
            #   <box>x1,y1,x2,y2</box>
            #   <box>x1,y1),(x2,y2</box>  (括号不匹配)
            #   <box>(x1,y1,x2,y2)</box>
            # 通用方案：提取 <box> 和 </box> 之间的所有数字，取前4个
            box_match = None
            box_content = re.search(r'<box>(.*?)</box>', coord_text, re.IGNORECASE | re.DOTALL)
            if box_content:
                inner = box_content.group(1)
                # 提取所有数字（整数或小数）
                nums = re.findall(r'(\d+\.?\d*)', inner)
                if len(nums) >= 4:
                    box_match = [float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3])]
            if box_match:
                if isinstance(box_match, list):
                    x1, y1, x2, y2 = box_match
                else:
                    x1 = float(box_match.group(1))
                    y1 = float(box_match.group(2))
                    x2 = float(box_match.group(3))
                    y2 = float(box_match.group(4))
                
                # 判断坐标范围：如果最大值 <= 1000，说明是归一化坐标 [0, 1000]，需要映射
                max_val = max(x1, y1, x2, y2)
                if max_val <= 1000:
                    # 归一化坐标 [0, 1000] -> 绝对像素坐标
                    scale_x = img_width / 1000.0
                    scale_y = img_height / 1000.0
                    abs_x1 = x1 * scale_x
                    abs_y1 = y1 * scale_y
                    abs_x2 = x2 * scale_x
                    abs_y2 = y2 * scale_y
                else:
                    # 已经是绝对像素坐标
                    abs_x1, abs_y1, abs_x2, abs_y2 = x1, y1, x2, y2
                
                left = int(min(abs_x1, abs_x2))
                top = int(min(abs_y1, abs_y2))
                width = int(abs(abs_x2 - abs_x1))
                height = int(abs(abs_y2 - abs_y1))
                logger.info(f"<box>坐标: ({x1},{y1},{x2},{y2}) -> 绝对像素: ({left},{top},{width},{height}), 图片尺寸: {img_width}x{img_height}")
                return left, top, width, height
            
            # 格式2: 方括号 [x1, y1, x2, y2]
            bracket_match = re.search(r'\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]', coord_text)
            if bracket_match:
                x1 = int(bracket_match.group(1))
                y1 = int(bracket_match.group(2))
                x2 = int(bracket_match.group(3))
                y2 = int(bracket_match.group(4))
                
                # 同样判断是否归一化坐标
                max_val = max(x1, y1, x2, y2)
                if max_val <= 1000:
                    scale_x = img_width / 1000.0
                    scale_y = img_height / 1000.0
                    abs_x1 = x1 * scale_x
                    abs_y1 = y1 * scale_y
                    abs_x2 = x2 * scale_x
                    abs_y2 = y2 * scale_y
                else:
                    abs_x1, abs_y1, abs_x2, abs_y2 = float(x1), float(y1), float(x2), float(y2)
                
                left = int(min(abs_x1, abs_x2))
                top = int(min(abs_y1, abs_y2))
                width = int(abs(abs_x2 - abs_x1))
                height = int(abs(abs_y2 - abs_y1))
                return left, top, width, height
            
            # 格式3: 圆括号 (v1, v2, v3, v4)
            # 可能是角点格式 (x1,y1,x2,y2) 或宽高格式 (left,top,width,height)
            tuple_match = re.search(r'\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', coord_text)
            if tuple_match:
                v1 = int(tuple_match.group(1))
                v2 = int(tuple_match.group(2))
                v3 = int(tuple_match.group(3))
                v4 = int(tuple_match.group(4))
                
                # 先判断是否归一化坐标 [0, 1000]
                max_val = max(v1, v2, v3, v4)
                is_normalized = (max_val <= 1000)
                
                # 智能判断角点格式 (x1,y1,x2,y2) vs 宽高格式 (left,top,width,height)
                width_guess = abs(v3 - v1)
                height_guess = abs(v4 - v2)
                
                is_corner = False
                if v3 > v1 and v4 > v2:
                    if width_guess < v3 * 0.8 and height_guess < v4 * 0.8:
                        is_corner = True
                    elif img_width > 100 and width_guess < img_width * 0.3 and height_guess < img_height * 0.3:
                        is_corner = True
                
                if is_corner:
                    # 角点格式：v1,y1是左上角，v3,y2是右下角
                    raw_x1, raw_y1, raw_x2, raw_y2 = v1, v2, v3, v4
                else:
                    # 宽高格式：v1,y1是左上角，v3是宽度，v4是高度
                    raw_x1, raw_y1 = v1, v2
                    raw_x2 = v1 + v3
                    raw_y2 = v2 + v4
                
                # 归一化坐标映射
                if is_normalized:
                    scale_x = img_width / 1000.0
                    scale_y = img_height / 1000.0
                    abs_x1 = raw_x1 * scale_x
                    abs_y1 = raw_y1 * scale_y
                    abs_x2 = raw_x2 * scale_x
                    abs_y2 = raw_y2 * scale_y
                else:
                    abs_x1, abs_y1, abs_x2, abs_y2 = raw_x1, raw_y1, raw_x2, raw_y2
                
                left = int(min(abs_x1, abs_x2))
                top = int(min(abs_y1, abs_y2))
                width = int(abs(abs_x2 - abs_x1))
                height = int(abs(abs_y2 - abs_y1))
                
                logger.info(f"圆括号坐标: ({v1},{v2},{v3},{v4}) -> 角点={is_corner}, 归一化={is_normalized} -> 绝对像素: ({left},{top},{width},{height}), 图片: {img_width}x{img_height}")
                return left, top, width, height
            
            # 都不匹配
            logger.warning(f"无法解析坐标: {coord_text}，使用默认位置")
            return 100, 100, 50, 20
            
        except Exception as e:
            logger.warning(f"坐标解析异常: {e}，使用默认坐标")
            return 100, 100, 50, 20
    
    def _estimate_coordinates_from_region(self, region: str, img_width: int, img_height: int) -> tuple:
        """
        根据区域描述估算坐标
        
        Args:
            region: 区域描述文本
            img_width: 图片宽度
            img_height: 图片高度
            
        Returns:
            估算的 (x, y) 坐标
        """
        # 默认居中
        x, y = img_width, img_height
        
        region_lower = region.lower()
        
        return x, y
    
    def _parse_fallback_format(self, response_content: str, img_width: int, img_height: int) -> List[Dict]:
        """
        回退格式解析（当Markdown表格解析失败时）
        
        Args:
            response_content: API返回的文本内容
            img_width: 图片宽度
            img_height: 图片高度
            
        Returns:
            文本项列表
        """
        import re
        text_items = []
        
        try:
            # 尝试按行解析，查找有序列表
            lines = response_content.split('\n')
            current_index = 1
            
            for line in lines:
                line = line.strip()
                
                # 匹配有序列表项，如 "1. 内容: xxx, 类型: xxx, 区域: xxx, 坐标: xxx"
                if re.match(r'^\d+\.\s+', line):
                    # 提取内容
                    content_match = re.search(r'内容\s*[:：]\s*(.+?)(?:,|$)', line)
                    type_match = re.search(r'类型\s*[:：]\s*(.+?)(?:,|$)', line)
                    region_match = re.search(r'区域\s*[:：]\s*(.+?)(?:,|$)', line)
                    coord_match = re.search(r'坐标\s*[:：]\s*(.+?)(?:,|$)', line)
                    
                    if content_match:
                        content = content_match.group(1).strip()
                        item_type = type_match.group(1).strip() if type_match else 'text'
                        region = region_match.group(1).strip() if region_match else '未知区域'
                        coord_text = coord_match.group(1).strip() if coord_match else '(0, 0)'
                        
                        # 解析坐标
                        left, top, width, height = self._parse_coordinates(coord_text, img_width, img_height, region)
                        
                        text_items.append({
                            'id': current_index,
                            'text': content,
                            'confidence': 0.9,
                            'location': {
                                'left': left,
                                'top': top,
                                'width': width,
                                'height': height,
                                'right': width,
                                'bottom': height
                            },
                            'type': item_type,
                            'region': region,
                            'coordinates_text': coord_text
                        })
                        
                        current_index += 1
        
        except Exception as e:
            logger.warning(f"回退格式解析失败: {e}")
        
        return text_items
    
    def _parse_json_format(self, response_content: str, img_width: int, img_height: int) -> List[Dict]:
        """
        从JSON格式的响应中提取文本项（当Markdown表格解析失败时的最后尝试）
        
        Args:
            response_content: API返回的文本内容
            img_width: 图片宽度
            img_height: 图片高度
            
        Returns:
            文本项列表
        """
        import re
        import json as json_lib
        text_items = []
        
        try:
            # 尝试提取 ```json ... ``` 代码块
            json_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_content, re.DOTALL)
            if json_block_match:
                json_str = json_block_match.group(1).strip()
            else:
                # 尝试直接解析整个响应
                json_str = response_content.strip()
            
            # 尝试解析JSON
            # 先尝试标准JSON解析
            try:
                data = json_lib.loads(json_str)
            except:
                # 尝试修复非标准JSON（如键名没有引号）
                # 将 { key: value } 转为 { "key": "value" }
                fixed = re.sub(r'(\w+)(?=\s*:)', r'"\1"', json_str)
                # 将单引号转为双引号
                fixed = fixed.replace("'", '"')
                try:
                    data = json_lib.loads(fixed)
                except:
                    data = None
            
            if data and isinstance(data, dict):
                # 递归提取所有字符串值作为text_items
                index = 1
                def extract_values(obj, path=""):
                    nonlocal index
                    items = []
                    if isinstance(obj, dict):
                        # 检查是否有bounding_box或bbox字段（安全帽、目标检测等）
                        bbox = None
                        for key in ['bounding_box', 'bbox', 'box', 'location', 'coordinates']:
                            if key in obj and isinstance(obj[key], list) and len(obj[key]) >= 4:
                                bbox = obj[key]
                                break
                        
                        for key, value in obj.items():
                            current_path = f"{path}.{key}" if path else str(key)
                            if isinstance(value, str) and len(value) > 0 and len(value) < 100:
                                # 如果有bounding_box，使用真实坐标
                                if bbox:
                                    try:
                                        nums = [float(x) for x in bbox[:4]]
                                        max_val = max(nums)
                                        if max_val <= 1000:
                                            scale_x = img_width / 1000.0
                                            scale_y = img_height / 1000.0
                                            abs_x1, abs_y1 = nums[0] * scale_x, nums[1] * scale_y
                                            abs_x2, abs_y2 = nums[2] * scale_x, nums[3] * scale_y
                                        else:
                                            abs_x1, abs_y1, abs_x2, abs_y2 = nums
                                        loc_left = int(min(abs_x1, abs_x2))
                                        loc_top = int(min(abs_y1, abs_y2))
                                        loc_w = int(abs(abs_x2 - abs_x1))
                                        loc_h = int(abs(abs_y2 - abs_y1))
                                    except:
                                        loc_left = 100 + (index * 30) % (img_width - 100)
                                        loc_top = 100 + (index * 20) % (img_height - 100)
                                        loc_w, loc_h = 80, 20
                                else:
                                    loc_left = 100 + (index * 30) % (img_width - 100)
                                    loc_top = 100 + (index * 20) % (img_height - 100)
                                    loc_w, loc_h = 80, 20
                                
                                items.append({
                                    'id': index,
                                    'text': value,
                                    'confidence': 0.9,
                                    'location': {
                                        'left': loc_left,
                                        'top': loc_top,
                                        'width': loc_w,
                                        'height': loc_h
                                    },
                                    'type': current_path,
                                    'region': current_path,
                                    'coordinates_text': f"({loc_left}, {loc_top}, {loc_w}, {loc_h})"
                                })
                                index += 1
                            elif isinstance(value, (dict, list)):
                                items.extend(extract_values(value, current_path))
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            items.extend(extract_values(item, f"{path}[{i}]"))
                    return items
                
                text_items = extract_values(data)
                if text_items:
                    logger.info(f"从JSON中提取了 {len(text_items)} 个文本项")
        except Exception as e:
            logger.warning(f"JSON格式解析失败: {e}")
        
        return text_items
    
    def _analyze_results(self, text_items: List[Dict]) -> Dict[str, Any]:
        """
        分析识别结果
        
        Args:
            text_items: 文本项列表
            
        Returns:
            分析结果字典
        """
        # 统计不同类型
        type_counts = {}
        type_categories = {
            'dimension': ['尺寸标注', '尺寸', 'dimension', '大小'],
            'surface_roughness': ['表面粗糙度', '粗糙度', 'ra', 'surface'],
            'view_identifier': ['视图标识', '视图', 'view', '剖视图'],
            'title_block': ['标题栏', '标题', 'title'],
            'technical_requirement': ['技术要求', '技术', 'technical'],
            'material': ['材料', 'material', '材质'],
            'tolerance': ['公差', 'tolerance', '±'],
            'symbol': ['符号', 'symbol', '标记'],
            'text': ['文本', '文字', 'text']
        }
        
        # 初始化计数
        for category in type_categories:
            type_counts[category] = 0
        
        # 分类统计
        for item in text_items:
            item_type = item.get('type', '').lower()
            matched = False
            
            for category, keywords in type_categories.items():
                if any(keyword.lower() in item_type for keyword in keywords):
                    type_counts[category] += 1
                    matched = True
                    break
            
            if not matched:
                type_counts['text'] += 1
        
        # 计算区域分布
        region_counts = {}
        for item in text_items:
            region = item.get('region', '未知区域')
            region_counts[region] = region_counts.get(region, 0) + 1
        
        return {
            'type_distribution': type_counts,
            'region_distribution': region_counts,
            'total_items': len(text_items),
            'unique_regions': len(region_counts)
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
            'ocr_engine': 'OpenAI VL',
            'model': self.model
        }
    
    def batch_process(self, image_paths: List[str], prompts: List[str] = None) -> List[Dict[str, Any]]:
        """
        批量处理图片
        
        Args:
            image_paths: 图片路径列表
            prompts: 提示词列表（可选）
            
        Returns:
            处理结果列表
        """
        results = []
        
        if prompts is None:
            prompts = [None] * len(image_paths)
        
        for i, image_path in enumerate(image_paths):
            prompt = prompts[i] if i < len(prompts) else None
            result = self.process_image(image_path, prompt)
            results.append(result)
        
        return results


# 工厂函数，便于使用
def create_openai_vl_processor(api_key=None, base_url=None, model=None):
    """创建OpenAI VL处理器实例"""
    return OpenAIVLProcessor(api_key=api_key, base_url=base_url, model=model)


if __name__ == '__main__':
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # 使用示例图片
        image_path = "../frontend/uploads/0f18b42635ec40d4bf2c8c3fbe61f404.png"
        if not os.path.exists(image_path):
            print(f"示例图片不存在: {image_path}")
            print("请上传真实图片进行测试，或创建示例图片")
            print("用法: python openai_vl_processor.py <图片路径>")
            sys.exit(1)
    
    print("测试OpenAI VL处理器...")
    print(f"处理图片: {image_path}")
    
    # 创建处理器
    processor = OpenAIVLProcessor()
    
    if not processor.initialized:
        print("OpenAI VL处理器初始化失败")
        print("请检查MODELSCOPE_API_KEY环境变量是否设置")
        sys.exit(1)
    
    # 处理图片
    result = processor.process_image(image_path)
    
    if result['success']:
        print(f"\n识别成功!")
        print(f"OCR引擎: {result.get('ocr_engine', '未知')}")
        print(f"模型: {result.get('model', '未知')}")
        print(f"识别到 {result['total_items']} 个信息项")
        print(f"处理时间: {result['processing_time']}秒")
        
        # 显示分析结果
        analysis = result.get('analysis', {})
        print(f"\n分析结果:")
        type_dist = analysis.get('type_distribution', {})
        for type_name, count in type_dist.items():
            if count > 0:
                print(f"  {type_name}: {count}")
        
        # 显示前5个识别结果
        print(f"\n前5个识别结果:")
        for i, item in enumerate(result['text_items'][:5], 1):
            print(f"  {i}. [{item['type']}] {item['text']}")
            print(f"     区域: {item.get('region', '未知')}")
            print(f"     位置: ({item['location']['left']}, {item['location']['top']})")
        
        # 显示原始响应预览
        print(f"\n原始响应预览:")
        print(result.get('raw_response', '')[:200])
        
    else:
        print(f"\n识别失败: {result.get('error', '未知错误')}")
