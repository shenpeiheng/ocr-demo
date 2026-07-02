"""
AI 会议纪要生成器 - 使用 OpenAI 兼容 API
"""

import os
import logging
import requests
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISummaryProcessor:
    """AI 会议纪要处理器"""

    def __init__(self, api_key=None, base_url=None):
        """
        初始化 AI 纪要处理器

        Args:
            api_key: API密钥（默认为环境变量 MODELSCOPE_API_KEY）
            base_url: API基础URL（默认为环境变量 MODELSCOPE_BASE_URL）
        """
        self.api_key = api_key or os.getenv('MODELSCOPE_API_KEY', "ms-83c39231-b66e-4ed8-8a2b-52c9ded22a51")
        self.base_url = base_url or os.getenv('MODELSCOPE_BASE_URL', "https://api-inference.modelscope.cn/v1")

        if not self.api_key:
            logger.warning("未设置API密钥，请设置 MODELSCOPE_API_KEY 环境变量")
            self.initialized = False
            return

        self.initialized = True
        logger.info(f"AI 纪要处理器初始化成功 (base_url: {self.base_url})")

    def generate_summary(self, transcript: str, model: str = "gpt-4o") -> Dict[str, Any]:
        """
        生成会议纪要

        Args:
            transcript: 原始转录文本
            model: AI 模型名称

        Returns:
            包含 success 和 summary 的字典
        """
        if not self.initialized:
            return {"success": False, "error": "AI 处理器未初始化"}

        # 模型映射
        model_map = {
            "deepseek": "deepseek-ai/DeepSeek-V4-Flash",
            "qwen": "Qwen/Qwen2.5-72B-Instruct",
            "qwen-vl": "Qwen/Qwen3-VL-235B-A22B-Instruct"
        }

        actual_model = model_map.get(model, model_map["deepseek"])

        # 构建提示词
        prompt = self._build_meeting_summary_prompt(transcript)

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": actual_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                summary = data["choices"][0]["message"]["content"]
                return {"success": True, "summary": summary}
            else:
                error_msg = f"API 错误: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"生成纪要失败: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _build_meeting_summary_prompt(self, transcript: str) -> str:
        """构建会议纪要提示词"""
        return f"""请根据以下会议转录内容，生成一份结构化的会议纪要。

会议转录：
{transcript}

请按照以下格式输出：

### 会议概述
[用1-2句话概括会议主题和目的]

### 关键讨论点
- [讨论点1]
- [讨论点2]
- [讨论点3]

### 决策事项
- [决策1]
- [决策2]

### 行动计划
- [行动项1：负责人 + 截止时间]
- [行动项2：负责人 + 截止时间]

### 问题与疑问
请整理会议中提出但尚未明确结论的问题、疑问、需要进一步确认或讨论的事项。
- [问题/疑问1]
- [问题/疑问2]
- [问题/疑问3]

### 待解决问题
请列出已经明确需要后续跟进解决的问题。
- [待解决问题1]
- [待解决问题2]

请使用中文输出，保持简洁专业。

注意：
1. 不要遗漏会议中任何提出的问题或疑问，即使最终没有讨论出结论，也请记录。
2. 如果会议中没有提出问题或疑问，请填写"无"。
3. 如果能够识别问题的提出人，可在问题后标注（提出人：XXX）。
4. 对于行动计划，如果无法确定负责人或截止时间，可标注"待确定"。
"""


# 全局单例
ai_summary_processor = AISummaryProcessor()
