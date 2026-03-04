"""
Markdown格式化器 - 将OCR识别结果格式化为Markdown表格
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

class MarkdownFormatter:
    """Markdown格式化器类"""
    
    def __init__(self):
        """初始化Markdown格式化器"""
        pass
    
    def format_ocr_results(self, ocr_results: Dict[str, Any], include_raw: bool = False) -> str:
        """
        格式化OCR识别结果为Markdown
        
        Args:
            ocr_results: OCR识别结果字典
            include_raw: 是否包含原始响应
            
        Returns:
            Markdown格式的字符串
        """
        if not ocr_results.get('success', False):
            return self._format_error_result(ocr_results)
        
        markdown = "# 机械工程图纸识别结果\n\n"
        
        # 添加元数据
        markdown += self._format_metadata(ocr_results)
        
        # 添加主要表格
        markdown += self._format_main_table(ocr_results)
        
        # 添加分析结果
        markdown += self._format_analysis(ocr_results)
        
        # 添加统计信息
        markdown += self._format_statistics(ocr_results)
        
        # 可选：包含原始响应
        if include_raw and 'raw_response' in ocr_results:
            markdown += self._format_raw_response(ocr_results['raw_response'])
        
        return markdown
    
    def _format_metadata(self, ocr_results: Dict[str, Any]) -> str:
        """格式化元数据"""
        metadata = "## 处理信息\n\n"
        
        # 基本元数据
        metadata += f"- **处理时间**: {ocr_results.get('processed_at', '未知')}\n"
        metadata += f"- **OCR引擎**: {ocr_results.get('ocr_engine', '未知')}\n"
        
        if 'model' in ocr_results:
            metadata += f"- **模型**: {ocr_results['model']}\n"
        
        if 'processing_time' in ocr_results:
            metadata += f"- **处理耗时**: {ocr_results['processing_time']}秒\n"
        
        # 图片信息
        image_info = ocr_results.get('image_info', {})
        if image_info:
            metadata += f"- **文件名**: {image_info.get('filename', '未知')}\n"
            metadata += f"- **图片尺寸**: {image_info.get('width', 0)}×{image_info.get('height', 0)}像素\n"
            metadata += f"- **文件大小**: {self._format_file_size(image_info.get('size', 0))}\n"
        
        metadata += "\n"
        return metadata
    
    def _format_main_table(self, ocr_results: Dict[str, Any]) -> str:
        """格式化主表格"""
        text_items = ocr_results.get('text_items', [])
        
        if not text_items:
            return "## 识别结果\n\n未识别到任何文本信息。\n\n"
        
        table = "## 识别结果\n\n"
        table += "| 序号 | 内容 | 类型 | 区域 | 坐标 | 置信度 |\n"
        table += "|------|------|------|------|------|--------|\n"
        
        for item in text_items:
            index = item.get('id', 0)
            content = self._escape_markdown(item.get('text', ''))
            item_type = self._escape_markdown(item.get('type', 'text'))
            region = self._escape_markdown(item.get('region', item.get('location_description', '未知区域')))
            
            # 坐标
            location = item.get('location', {})
            x = location.get('left', 0)
            y = location.get('top', 0)
            coordinates = f"({x}, {y})"
            
            # 置信度
            confidence = item.get('confidence', 0)
            confidence_str = f"{confidence:.3f}" if isinstance(confidence, (int, float)) else str(confidence)
            
            table += f"| {index} | {content} | {item_type} | {region} | {coordinates} | {confidence_str} |\n"
        
        table += "\n"
        return table
    
    def _format_analysis(self, ocr_results: Dict[str, Any]) -> str:
        """格式化分析结果"""
        analysis = ocr_results.get('analysis', {})
        
        if not analysis:
            return ""
        
        analysis_text = "## 分析结果\n\n"
        
        # 类型分布
        type_dist = analysis.get('type_distribution', {})
        if type_dist:
            analysis_text += "### 类型分布\n\n"
            for type_name, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    analysis_text += f"- **{type_name}**: {count}项\n"
            analysis_text += "\n"
        
        # 区域分布
        region_dist = analysis.get('region_distribution', {})
        if region_dist:
            analysis_text += "### 区域分布\n\n"
            for region, count in sorted(region_dist.items(), key=lambda x: x[1], reverse=True)[:10]:  # 只显示前10个
                analysis_text += f"- **{region}**: {count}项\n"
            analysis_text += "\n"
        
        # 特定类型统计
        special_counts = [
            ('dimension_count', '尺寸标注'),
            ('tolerance_count', '公差标注'),
            ('material_count', '材料信息'),
            ('technical_count', '技术要求'),
            ('surface_roughness_count', '表面粗糙度'),
            ('geometric_tolerance_count', '形位公差'),
            ('weld_symbol_count', '焊接符号')
        ]
        
        analysis_text += "### 关键信息统计\n\n"
        for key, label in special_counts:
            if key in analysis and analysis[key] > 0:
                analysis_text += f"- **{label}**: {analysis[key]}项\n"
        
        # 平均置信度
        if 'average_confidence' in analysis:
            analysis_text += f"- **平均置信度**: {analysis['average_confidence']:.3f}\n"
        
        analysis_text += "\n"
        return analysis_text
    
    def _format_statistics(self, ocr_results: Dict[str, Any]) -> str:
        """格式化统计信息"""
        text_items = ocr_results.get('text_items', [])
        total_items = len(text_items)
        
        if total_items == 0:
            return ""
        
        stats = "## 统计信息\n\n"
        stats += f"- **总识别项数**: {total_items}\n"
        
        # 字符统计
        total_chars = 0
        digit_chars = 0
        letter_chars = 0
        symbol_chars = 0
        
        for item in text_items:
            text = item.get('text', '')
            total_chars += len(text)
            digit_chars += sum(1 for c in text if c.isdigit())
            letter_chars += sum(1 for c in text if c.isalpha())
            symbol_chars += sum(1 for c in text if not c.isalnum() and c != ' ')
        
        if total_chars > 0:
            stats += f"- **总字符数**: {total_chars}\n"
            stats += f"- **数字字符**: {digit_chars} ({digit_chars/total_chars*100:.1f}%)\n"
            stats += f"- **字母字符**: {letter_chars} ({letter_chars/total_chars*100:.1f}%)\n"
            stats += f"- **符号字符**: {symbol_chars} ({symbol_chars/total_chars*100:.1f}%)\n"
        
        # 坐标范围
        if text_items:
            x_coords = [item.get('location', {}).get('left', 0) for item in text_items]
            y_coords = [item.get('location', {}).get('top', 0) for item in text_items]
            
            if x_coords and y_coords:
                min_x, max_x = min(x_coords), max(x_coords)
                min_y, max_y = min(y_coords), max(y_coords)
                stats += f"- **X坐标范围**: {min_x} - {max_x}\n"
                stats += f"- **Y坐标范围**: {min_y} - {max_y}\n"
                stats += f"- **分布区域**: {max_x - min_x} × {max_y - min_y} 像素\n"
        
        stats += "\n"
        return stats
    
    def _format_raw_response(self, raw_response: str) -> str:
        """格式化原始响应"""
        if not raw_response:
            return ""
        
        response = "## 原始响应\n\n"
        response += "```markdown\n"
        response += raw_response[:2000]  # 限制长度
        if len(raw_response) > 2000:
            response += "\n... (响应过长，已截断)"
        response += "\n```\n\n"
        
        return response
    
    def _format_error_result(self, ocr_results: Dict[str, Any]) -> str:
        """格式化错误结果"""
        error = "# 识别失败\n\n"
        error += f"**错误信息**: {ocr_results.get('error', '未知错误')}\n\n"
        
        if 'processed_at' in ocr_results:
            error += f"**处理时间**: {ocr_results['processed_at']}\n"
        
        if 'ocr_engine' in ocr_results:
            error += f"**OCR引擎**: {ocr_results['ocr_engine']}\n"
        
        return error
    
    def _escape_markdown(self, text: str) -> str:
        """转义Markdown特殊字符"""
        if not isinstance(text, str):
            text = str(text)
        
        # 需要转义的字符
        escape_chars = ['\\', '`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!', '|']
        
        for char in escape_chars:
            text = text.replace(char, '\\' + char)
        
        return text
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def save_to_file(self, markdown_content: str, filepath: str) -> bool:
        """
        保存Markdown内容到文件
        
        Args:
            markdown_content: Markdown内容
            filepath: 文件路径
            
        Returns:
            是否保存成功
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            return True
        except Exception as e:
            print(f"保存Markdown文件失败: {e}")
            return False
    
    def format_comparison(self, results1: Dict[str, Any], results2: Dict[str, Any], 
                         label1: str = "结果1", label2: str = "结果2") -> str:
        """
        格式化两个OCR结果的比较
        
        Args:
            results1: 第一个OCR结果
            results2: 第二个OCR结果
            label1: 第一个结果的标签
            label2: 第二个结果的标签
            
        Returns:
            比较结果的Markdown
        """
        markdown = "# OCR结果比较\n\n"
        
        # 基本信息比较
        markdown += "## 基本信息比较\n\n"
        markdown += f"| 项目 | {label1} | {label2} | 差异 |\n"
        markdown += "|------|----------|----------|------|\n"
        
        items1 = results1.get('text_items', [])
        items2 = results2.get('text_items', [])
        
        markdown += f"| 识别项数 | {len(items1)} | {len(items2)} | {len(items1) - len(items2)} |\n"
        
        if 'processing_time' in results1 and 'processing_time' in results2:
            time1 = results1['processing_time']
            time2 = results2['processing_time']
            markdown += f"| 处理时间 | {time1}秒 | {time2}秒 | {time1 - time2:.2f}秒 |\n"
        
        if 'ocr_engine' in results1 and 'ocr_engine' in results2:
            markdown += f"| OCR引擎 | {results1['ocr_engine']} | {results2['ocr_engine']} | - |\n"
        
        markdown += "\n"
        
        # 共同识别项
        common_items = []
        items1_texts = [item.get('text', '').strip() for item in items1]
        items2_texts = [item.get('text', '').strip() for item in items2]
        
        for text in items1_texts:
            if text in items2_texts and text:  # 非空文本
                common_items.append(text)
        
        markdown += f"## 共同识别项 ({len(common_items)}项)\n\n"
        if common_items:
            for i, text in enumerate(common_items[:20], 1):  # 只显示前20个
                markdown += f"{i}. {text}\n"
            if len(common_items) > 20:
                markdown += f"... 还有 {len(common_items) - 20} 项未显示\n"
        else:
            markdown += "无共同识别项\n"
        
        markdown += "\n"
        
        # 各自独有的识别项
        unique_to_1 = [text for text in items1_texts if text not in items2_texts and text]
        unique_to_2 = [text for text in items2_texts if text not in items1_texts and text]
        
        markdown += f"## {label1} 独有识别项 ({len(unique_to_1)}项)\n\n"
        if unique_to_1:
            for i, text in enumerate(unique_to_1[:10], 1):  # 只显示前10个
                markdown += f"{i}. {text}\n"
            if len(unique_to_1) > 10:
                markdown += f"... 还有 {len(unique_to_1) - 10} 项未显示\n"
        else:
            markdown += "无独有识别项\n"
        
        markdown += f"\n## {label2} 独有识别项 ({len(unique_to_2)}项)\n\n"
        if unique_to_2:
            for i, text in enumerate(unique_to_2[:10], 1):
                markdown += f"{i}. {text}\n"
            if len(unique_to_2) > 10:
                markdown += f"... 还有 {len(unique_to_2) - 10} 项未显示\n"
        else:
            markdown += "无独有识别项\n"
        
        return markdown


# 创建全局实例
markdown_formatter = MarkdownFormatter()

# 便捷函数
def format_results(ocr_results, include_raw=False):
    """格式化OCR结果（便捷函数）"""
    return markdown_formatter.format_ocr_results(ocr_results, include_raw)

def save_markdown(markdown_content, filepath):
    """保存Markdown到文件（便捷函数）"""
    return markdown_formatter.save_to_file(markdown_content, filepath)


if __name__ == '__main__':
    # 测试代码
    print("Markdown格式化器测试")
    print("=" * 50)
    
    # 创建测试数据
    test_results = {
        'success': True,
        'text_items': [
            {
                'id': 1,
                'text': 'φ25',
                'confidence': 0.95,
                'type': '尺寸标注',
                'region': '主视图右侧',
                'location': {'left': 150, 'top': 200, 'width': 30, 'height': 15}
            },
            {
                'id': 2,
                'text': 'Ra 1.6',
                'confidence': 0.92,
                'type': '表面粗糙度',
                'region': '俯视图上部',
                'location': {'left': 300, 'top': 100, 'width': 40, 'height': 15}
            },
            {
                'id': 3,
                'text': '45#钢',
                'confidence': 0.88,
                'type': '材料信息',
                'region': '标题栏中部',
                'location': {'left': 500, 'top': 600, 'width': 35, 'height': 15}
            }
        ],
        'total_items': 3,
        'processing_time': 2.5,
        'analysis': {
            'type_distribution': {'尺寸标注': 1, '表面粗糙度': 1, '材料信息': 1},
            'region_distribution': {'主视图右侧': 1, '俯视图上部': 1, '标题栏中部': 1},
            'dimension_count': 1,
            'average_confidence': 0.917
        },
        'image_info': {
            'filename': 'test_drawing.png',
            'width': 800,
            'height': 600,
            'size': 102400
        },
        'processed_at': '2024-01-01 10:30:00',
        'ocr_engine': 'OpenAI VL',
        'model': 'Qwen/Qwen3-VL-30B-A3B-Instruct'
    }
    
    # 格式化测试数据
    markdown_output = markdown_formatter.format_ocr_results(test_results)
    
    print("生成的Markdown预览:")
    print("=" * 50)
    print(markdown_output[:500] + "..." if len(markdown_output) > 500 else markdown_output)
    
    print("\n" + "=" * 50)
    print(f"Markdown总长度: {len(markdown_output)} 字符")