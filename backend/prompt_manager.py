"""
提示词管理器 - 管理机械工程图纸识别的专用提示词。
"""

import json
import os
from typing import Any, Dict, List

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

    def _get_output_contract(self) -> str:
        """统一的输出契约，确保提示词和解析器约定一致。"""
        return """输出规则（必须严格遵守）：
1. 先输出一个 Markdown 表格，表头固定为：`序号 | 内容 | 类型 | 区域 | 坐标`。
2. 每一行只对应一个识别项，禁止把多个内容合并到同一行。
3. `坐标` 必须使用 `(left, top, width, height)` 格式：
   - `left`、`top` 为左上角像素坐标；
   - `width`、`height` 为边界框宽高；
   - 所有值必须是整数；
   - 优先给出基于原始图像分辨率的绝对像素坐标；
   - 如果你只能输出归一化坐标，请保证数值范围为 `[0, 1000]`，且仍使用同样的四元组格式。
4. `类型` 要尽量使用业务语义，如：尺寸标注、形位公差、表面粗糙度、标题栏、技术要求、视图标识、材料、符号。
5. `区域` 必须写相对位置描述，如：主视图左上、剖视图中部、标题栏右下、技术要求区上方。
6. 不要输出解释性前言、寒暄语或额外章节；如需补充结构化数据，请放在表格之后。"""

    def _get_standard_mechanical_drawing_prompt(self) -> str:
        """获取标准机械工程图纸识别提示词。"""
        return f"""请根据提供的机械工程图纸，执行以下任务：

1. 全面识别图中的所有文字、数字、符号、尺寸、公差、技术要求和标题栏信息，尽量不要遗漏。
2. 严格按照从左到右、从上到下的 OCR 顺序排序。
3. 对每一项给出可落地的业务类型，不要全部归为“文本”。
4. 对每一项补充清晰的相对位置描述，便于人工复核。

重点关注：
- 尺寸标注和公差是否成对出现；
- 形位公差、粗糙度、基准符号等是否被误识别为普通文本；
- 标题栏、明细栏、技术要求区不要遗漏；
- 相邻但含义不同的标注要拆成独立行。

{self._get_output_contract()}"""
    
    def _get_detailed_mechanical_drawing_prompt(self) -> str:
        """获取详细机械工程图纸识别提示词（增强版）。"""
        return f"""你是一个专业的机械工程师和图纸识别专家。请分析提供的机械工程图纸，执行以下详细识别任务：

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

2. **结构化输出**：输出时优先保留业务语义，不要用“未知”“其他”敷衍分类。
3. **排序规则**：严格按照从左到右、从上到下的顺序排列识别结果。
4. **歧义处理**：如果某个标注模糊，请仍输出该项，但在类型或区域中体现“不确定”。
5. **避免合并**：一个框内如果同时有尺寸值和公差值，应拆成独立项。

{self._get_output_contract()}

补充要求：
- 如能判断置信度，可在表格之后补充说明，但不要改动表格字段。
- 优先保证识别完整性，其次再追求分类精细度。"""
    
    def _get_simple_mechanical_drawing_prompt(self) -> str:
        """获取简化机械工程图纸识别提示词。"""
        return f"""请识别机械工程图纸中的文字、数字和符号，并按从左到右、从上到下的顺序列出。

要求：
- 不遗漏标题栏、尺寸、公差、符号和技术要求；
- 类型尽量写明确，不要全部写“文本”；
- 区域写相对位置描述。

{self._get_output_contract()}"""
    
    def _get_dimension_extraction_prompt(self) -> str:
        """获取尺寸标注提取专用提示词。"""
        return f"""请专门提取机械工程图纸中的所有尺寸标注信息，包括：
1. 线性尺寸（长度、宽度、高度）
2. 直径和半径尺寸（标注φ、R、Ø的尺寸）
3. 角度尺寸
4. 螺纹尺寸
5. 倒角尺寸

对于每个尺寸标注，请提供：
- 尺寸数值
- 尺寸类型（线性/直径/半径/角度等）
- 标注位置描述
- 对应坐标

额外要求：
- 如果尺寸值与公差写在一起，请拆成两行；
- 单位缺省时不要臆造，只提取图上实际可见内容；
- 直径、半径、角度符号必须保留。

输出时请尽量让 `类型` 指向尺寸类别，如：线性尺寸、角度尺寸、直径尺寸、螺纹尺寸。

{self._get_output_contract()}"""
    
    def _get_title_block_extraction_prompt(self) -> str:
        """获取标题栏信息提取专用提示词。"""
        return f"""请提取机械工程图纸标题栏中的所有信息，通常包括：
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

要求：
- 标题栏中的标签名和值请拆开理解，但输出时 `内容` 保留票面可见文本；
- `类型` 请写成字段类别，如：图号、材料、比例、日期、设计者；
- 如果值为空白，不要臆造。

{self._get_output_contract()}"""
    
    def _get_technical_requirements_prompt(self) -> str:
        """获取技术要求提取专用提示词。"""
        return f"""请提取机械工程图纸中的技术要求部分，包括：
1. 加工要求
2. 热处理要求
3. 表面处理要求
4. 检验要求
5. 装配要求
6. 其他特殊要求

要求：
- 每一条技术要求单独成行；
- 如果一条要求跨多行，请合并成完整语义后再输出；
- 不要把普通标题误识别成技术要求正文。

{self._get_output_contract()}"""
    
    def _get_symbol_recognition_prompt(self) -> str:
        """获取符号识别专用提示词。"""
        return f"""请识别机械工程图纸中的所有特殊符号，包括：
1. 表面粗糙度符号（▽, ▽▽, ▽▽▽等）
2. 形位公差符号（◎, ∥, ⊥, ∠等）
3. 焊接符号
4. 基准符号
5. 加工符号
6. 检验符号
7. 其他工业符号

要求：
- `内容` 写实际识别到的符号或符号组合；
- `类型` 写符号类别，如：粗糙度符号、焊接符号、形位公差；
- `区域` 写相对位置；
- 如能判断符号含义，可在表格后补充说明，但不要改动表格字段。

{self._get_output_contract()}"""
    
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
