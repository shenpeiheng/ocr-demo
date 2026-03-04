"""
OpenAI VL处理器 - 使用OpenAI兼容的视觉语言模型进行机械工程图纸识别
支持ModelScope API（中国版OpenAI兼容API）
"""

import os
import time
import base64
import json
import logging
from typing import Dict, List, Any, Optional
from PIL import Image
import requests

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        self.model = model or os.getenv('MODELSCOPE_MODEL', 'Qwen/Qwen3-VL-30B-A3B-Instruct')
        
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
            # 读取图片并转换为base64
            image_base64 = self._image_to_base64(image_path)
            
            # 获取图片尺寸信息
            img = Image.open(image_path)
            img_width, img_height = img.size
            
            # 使用默认提示词（如果未提供）
            if prompt is None:
                prompt = self._get_default_mechanical_drawing_prompt()
            
            # 调用OpenAI VL API
            logger.info("调用OpenAI VL API进行识别...")
            response = self._call_openai_vl_api(image_base64, prompt)
            
            # 解析API响应
            if response.get('success', False):
                # 解析响应内容
                parsed_results = self._parse_api_response(response['content'], img_width, img_height)
                
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
                    'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'ocr_engine': 'OpenAI VL',
                    'model': self.model,
                    'prompt_used': prompt[:100] + "..." if len(prompt) > 100 else prompt,
                    'raw_response': response.get('content', '')[:500] + "..." if len(response.get('content', '')) > 500 else response.get('content', '')
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
    
    def _get_default_mechanical_drawing_prompt(self) -> str:
        """
        获取默认的机械工程图纸识别提示词
        
        Returns:
            提示词字符串
        """
        return """请根据提供的机械工程图纸，执行以下任务：

1.  **全面识别**：仔细分析图纸，识别出图中出现的所有文字、数字、符号和标注信息，确保不遗漏任何细节。
2.  **按 OCR 顺序排序**：将所有识别到的信息项，严格按照从左到右、从上到下的 OCR 识别顺序进行排序。
3.  **Markdown 格式输出**：使用 Markdown 语法，以清晰、结构化的方式展示所有信息。
4.  **详细信息格式**：每个信息项必须包含以下字段：
    - **序号**：从 1 开始的连续整数。
    - **内容**：该信息项的具体文本、数字或符号（例如 `// 0.2 A` 或 `65`）。
    - **类型**：描述该信息属于哪个类型的区域（如：尺寸标注、表面粗糙度、视图标识、标题栏、技术要求等）。
    - **区域**：**精确描述**该信息所在的具体**位置名称**，例如："主视图左侧"、"C-C剖视图上部"、"标题栏左下角"、"三维模型图右侧"等。此字段应反映其在图纸上的**相对位置**，而非强制使用预设列表。
    - **坐标**：提供该信息在图纸上的左上角像素坐标及边界框尺寸，格式为 (left, top, width, height)，单位为像素。其中 left 和 top 为边界框左上角坐标，width 和 height 为边界框宽高。所有数值必须为整数，且基于原始输入图像分辨率，保证绝对不能超过图片的分辨率。

**输出要求**：
- 将所有信息整合成一个完整的 Markdown 表格。
- 表格应包含上述所有字段。
- 请确保信息完整、准确，并严格遵循指定的格式和顺序。"""
    
    def _call_openai_vl_api(self, image_base64: str, prompt: str) -> Dict[str, Any]:
        """
        调用OpenAI VL API
        
        Args:
            image_base64: base64编码的图片
            prompt: 提示词
            
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
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4000,
                "temperature": 0.1
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
                if '|' in line and ('---' in line or '序号' in line or '内容' in line):
                    in_table = True
                    table_lines.append(line)
                elif in_table and '|' in line:
                    table_lines.append(line)
                elif in_table and '|' not in line and line.strip():
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
        解析坐标文本，支持三种格式：
        1. Qwen-VL 原生格式: <box>(x1,y1),(x2,y2)</box>
        2. 方括号角点格式: [x1, y1, x2, y2]
        3. 传统宽高格式: (left, top, width, height)
        返回归一化到 [0,1000] 的 (left, top, width, height)
        """
        try:
            import re
            
            # 格式1: Qwen-VL 的 <box>(x1,y1),(x2,y2)</box>
            box_match = re.search(r'<box>\s*\(\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\)\s*,\s*\(\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\)\s*</box>', coord_text, re.IGNORECASE)
            if box_match:
                x1 = float(box_match.group(1))
                y1 = float(box_match.group(2))
                x2 = float(box_match.group(3))
                y2 = float(box_match.group(4))
                left = min(x1, x2)
                top = min(y1, y2)
                width = abs(x2 - x1)
                height = abs(y2 - y1)
                return left, top, width, height
            
            # 格式2: 方括号 [x1, y1, x2, y2] —— 这是你日志中出现的格式！
            bracket_match = re.search(r'\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]', coord_text)
            if bracket_match:
                x1 = int(bracket_match.group(1))
                y1 = int(bracket_match.group(2))
                x2 = int(bracket_match.group(3))
                y2 = int(bracket_match.group(4))
                left = min(x1, x2)
                top = min(y1, y2)
                width = abs(x2 - x1)
                height = abs(y2 - y1)
                return left, top, width, height
            
            # 格式3: 传统 (left, top, width, height)
            tuple_match = re.search(r'\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', coord_text)
            if tuple_match:
                return int(tuple_match.group(1)), int(tuple_match.group(2)), int(tuple_match.group(3)), int(tuple_match.group(4))
            
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