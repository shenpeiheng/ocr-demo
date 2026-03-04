"""
提示词管理器 - 管理机械工程图纸识别的专用提示词
"""

import os
import json
from typing import Dict, List, Any, Optional

class PromptManager:
    """提示词管理器类"""
    
    def __init__(self):
        """初始化提示词管理器"""
        self.prompts = self._load_default_prompts()
    
    def _load_default_prompts(self) -> Dict[str, Any]:
        """加载默认提示词"""
        return {
            'mechanical_drawing_standard': self._get_standard_mechanical_drawing_prompt(),
            'mechanical_drawing_detailed': self._get_detailed_mechanical_drawing_prompt(),
            'mechanical_drawing_simple': self._get_simple_mechanical_drawing_prompt(),
            'dimension_extraction': self._get_dimension_extraction_prompt(),
            'title_block_extraction': self._get_title_block_extraction_prompt(),
            'technical_requirements': self._get_technical_requirements_prompt(),
            'symbol_recognition': self._get_symbol_recognition_prompt()
        }
    
    def _get_standard_mechanical_drawing_prompt(self) -> str:
        """获取标准机械工程图纸识别提示词（用户指定的格式）"""
        return """请根据提供的机械工程图纸，执行以下任务：

1.  **全面识别**：仔细分析图纸，识别出图中出现的所有文字、数字、符号和标注信息，确保不遗漏任何细节。
2.  **按 OCR 顺序排序**：将所有识别到的信息项，严格按照从左到右、从上到下的 OCR 识别顺序进行排序。
3.  **Markdown 格式输出**：使用 Markdown 语法，以清晰、结构化的方式展示所有信息。
4.  **详细信息格式**：每个信息项必须包含以下字段：
    - **序号**：从 1 开始的连续整数。
    - **内容**：该信息项的具体文本、数字或符号（例如 `// 0.2 A` 或 `65`）。
    - **类型**：描述该信息属于哪个类型的区域（如：尺寸标注、表面粗糙度、视图标识、标题栏、技术要求等）。
    - **区域**：**精确描述**该信息所在的具体**位置名称**，例如："主视图左侧"、"C-C剖视图上部"、"标题栏左下角"、"三维模型图右侧"等。此字段应反映其在图纸上的**相对位置**，而非强制使用预设列表。
    - **坐标**：提供该信息在图纸上的近似像素坐标（x, y），单位为像素。坐标需精确到个位数。

**输出要求**：
- 将所有信息整合成一个完整的 Markdown 表格。
- 表格应包含上述所有字段。
- 请确保信息完整、准确，并严格遵循指定的格式和顺序。"""
    
    def _get_detailed_mechanical_drawing_prompt(self) -> str:
        """获取详细机械工程图纸识别提示词（增强版）"""
        return """你是一个专业的机械工程师和图纸识别专家。请分析提供的机械工程图纸，执行以下详细识别任务：

## 任务要求：
1. **全面扫描识别**：识别图纸中的所有视觉元素，包括：
   - 尺寸标注（线性尺寸、角度尺寸、直径、半径等）
   - 公差标注（尺寸公差、形位公差）
   - 表面粗糙度符号和数值
   - 焊接符号和标注
   - 材料标注和热处理要求
   - 视图标识（主视图、俯视图、剖视图等）
   - 标题栏信息（图号、名称、比例、设计者等）
   - 技术要求文本
   - 特殊符号（基准符号、加工符号、检验符号等）

2. **结构化输出**：将识别结果组织成Markdown表格，包含以下列：
   - **序号**：从1开始的连续编号
   - **内容**：识别的具体文本/数字/符号
   - **类型**：信息类别（尺寸标注、公差、粗糙度、材料、视图标识等）
   - **区域**：在图纸上的具体位置描述
   - **坐标**：近似像素坐标 (x, y)
   - **置信度**：你对识别准确性的估计（0-1之间）

3. **排序规则**：严格按照从左到右、从上到下的顺序排列识别结果。

4. **坐标估算**：对于每个识别项，根据其在图纸上的相对位置，估算近似的像素坐标。

## 输出格式：
请以Markdown表格形式输出，确保表格格式正确，所有字段完整。"""
    
    def _get_simple_mechanical_drawing_prompt(self) -> str:
        """获取简化机械工程图纸识别提示词"""
        return """请识别机械工程图纸中的文字、数字和符号，并按从左到右、从上到下的顺序列出。

输出格式：Markdown表格
表格列：序号 | 内容 | 类型 | 位置 | 坐标

请确保识别完整准确。"""
    
    def _get_dimension_extraction_prompt(self) -> str:
        """获取尺寸标注提取专用提示词"""
        return """请专门提取机械工程图纸中的所有尺寸标注信息，包括：
1. 线性尺寸（长度、宽度、高度）
2. 直径和半径尺寸（标注φ、R、Ø的尺寸）
3. 角度尺寸
4. 螺纹尺寸
5. 倒角尺寸

对于每个尺寸标注，请提供：
- 尺寸数值
- 尺寸类型（线性/直径/半径/角度等）
- 标注位置
- 近似坐标

以Markdown表格形式输出，包含：序号、尺寸值、单位、类型、位置、坐标。"""
    
    def _get_title_block_extraction_prompt(self) -> str:
        """获取标题栏信息提取专用提示词"""
        return """请提取机械工程图纸标题栏中的所有信息，通常包括：
1. 图号/零件号
2. 零件名称
3. 材料
4. 比例
5. 设计者
6. 审核者
7. 批准者
8. 日期
9. 公司/部门名称
10. 重量
11. 其他相关信息

以Markdown表格形式输出，包含：序号、字段名称、字段值、位置、坐标。"""
    
    def _get_technical_requirements_prompt(self) -> str:
        """获取技术要求提取专用提示词"""
        return """请提取机械工程图纸中的技术要求部分，包括：
1. 加工要求
2. 热处理要求
3. 表面处理要求
4. 检验要求
5. 装配要求
6. 其他特殊要求

将每条技术要求作为独立项列出，包含：序号、要求内容、类型、位置、坐标。"""
    
    def _get_symbol_recognition_prompt(self) -> str:
        """获取符号识别专用提示词"""
        return """请识别机械工程图纸中的所有特殊符号，包括：
1. 表面粗糙度符号（▽, ▽▽, ▽▽▽等）
2. 形位公差符号（◎, ∥, ⊥, ∠等）
3. 焊接符号
4. 基准符号
5. 加工符号
6. 检验符号
7. 其他工业符号

对于每个符号，请提供：序号、符号描述、符号含义、位置、坐标。"""
    
    def get_prompt(self, prompt_name: str = 'mechanical_drawing_standard') -> str:
        """
        获取指定名称的提示词
        
        Args:
            prompt_name: 提示词名称
            
        Returns:
            提示词字符串
        """
        return self.prompts.get(prompt_name, self.prompts['mechanical_drawing_standard'])
    
    def get_all_prompts(self) -> Dict[str, str]:
        """获取所有提示词"""
        return self.prompts
    
    def add_custom_prompt(self, name: str, prompt: str) -> bool:
        """
        添加自定义提示词
        
        Args:
            name: 提示词名称
            prompt: 提示词内容
            
        Returns:
            是否添加成功
        """
        if name and prompt:
            self.prompts[name] = prompt
            return True
        return False
    
    def remove_prompt(self, name: str) -> bool:
        """
        删除提示词
        
        Args:
            name: 提示词名称
            
        Returns:
            是否删除成功
        """
        if name in self.prompts and name not in ['mechanical_drawing_standard']:
            del self.prompts[name]
            return True
        return False
    
    def save_prompts_to_file(self, filepath: str) -> bool:
        """
        保存提示词到文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否保存成功
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存提示词失败: {e}")
            return False
    
    def load_prompts_from_file(self, filepath: str) -> bool:
        """
        从文件加载提示词
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否加载成功
        """
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    loaded_prompts = json.load(f)
                    self.prompts.update(loaded_prompts)
                return True
        except Exception as e:
            print(f"加载提示词失败: {e}")
        
        return False
    
    def generate_prompt_for_drawing_type(self, drawing_type: str, requirements: List[str] = None) -> str:
        """
        根据图纸类型生成定制提示词
        
        Args:
            drawing_type: 图纸类型（如：零件图、装配图、钣金图、焊接图等）
            requirements: 特定要求列表
            
        Returns:
            定制化的提示词
        """
        base_prompt = self.get_prompt('mechanical_drawing_standard')
        
        # 根据图纸类型添加特定说明
        type_specific = ""
        if drawing_type == '零件图':
            type_specific = "这是一张机械零件图，请重点关注尺寸标注、公差、表面粗糙度和材料信息。"
        elif drawing_type == '装配图':
            type_specific = "这是一张机械装配图，请重点关注零件编号、装配关系、配合尺寸和技术要求。"
        elif drawing_type == '钣金图':
            type_specific = "这是一张钣金零件图，请重点关注展开尺寸、折弯线、孔位和钣金特定符号。"
        elif drawing_type == '焊接图':
            type_specific = "这是一张焊接图，请重点关注焊接符号、焊缝尺寸、焊接方法和焊接要求。"
        elif drawing_type == '液压原理图':
            type_specific = "这是一张液压原理图，请重点关注液压符号、管路连接、元件标识和技术参数。"
        else:
            type_specific = f"这是一张{drawing_type}，请根据图纸特点进行识别。"
        
        # 添加特定要求
        requirements_text = ""
        if requirements:
            requirements_text = "\n额外要求：\n" + "\n".join([f"- {req}" for req in requirements])
        
        # 组合提示词
        custom_prompt = f"{type_specific}\n\n{base_prompt}{requirements_text}"
        
        return custom_prompt


# 创建全局实例
prompt_manager = PromptManager()

# 便捷函数
def get_prompt(name='mechanical_drawing_standard'):
    """获取提示词（便捷函数）"""
    return prompt_manager.get_prompt(name)

def get_all_prompts():
    """获取所有提示词（便捷函数）"""
    return prompt_manager.get_all_prompts()

def add_custom_prompt(name, prompt):
    """添加自定义提示词（便捷函数）"""
    return prompt_manager.add_custom_prompt(name, prompt)


if __name__ == '__main__':
    # 测试代码
    print("提示词管理器测试")
    print("=" * 50)
    
    # 显示所有可用提示词
    prompts = get_all_prompts()
    print(f"可用提示词数量: {len(prompts)}")
    print("提示词列表:")
    for name in prompts.keys():
        print(f"  - {name}")
    
    print("\n" + "=" * 50)
    
    # 获取标准提示词
    standard_prompt = get_prompt('mechanical_drawing_standard')
    print(f"标准提示词长度: {len(standard_prompt)} 字符")
    print("标准提示词预览:")
    print(standard_prompt[:200] + "...")
    
    print("\n" + "=" * 50)
    
    # 测试定制提示词生成
    custom_prompt = prompt_manager.generate_prompt_for_drawing_type(
        '零件图',
        ['重点关注公差标注', '提取所有表面粗糙度']
    )
    print(f"定制提示词长度: {len(custom_prompt)} 字符")
    print("定制提示词预览:")
    print(custom_prompt[:200] + "...")