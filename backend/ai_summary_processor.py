"""
AI 会议纪要生成器 - 使用 OpenAI 兼容 API
"""

import logging
import requests
from typing import Dict, Any
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISummaryProcessor:
    """AI 会议纪要处理器"""

    def __init__(self, api_key=None, base_url=None):
        """
        初始化 AI 纪要处理器（api_key 和 base_url 现由调用方根据模型动态传入）
        """
        self.api_key = api_key or ''
        self.base_url = base_url or ''
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

        actual_model = Config.resolve_llm_model(model)
        actual_url = Config.resolve_llm_url(model)
        actual_key = Config.resolve_llm_key(model) or self.api_key

        # 构建提示词
        prompt = self._build_meeting_summary_prompt(transcript)

        try:
            response = requests.post(
                f"{actual_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {actual_key}",
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
