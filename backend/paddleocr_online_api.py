"""
PaddleOCR 在线 API 客户端
"""

import logging
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PaddleOCROnlineClient:
    """PaddleOCR 在线 API 客户端"""

    def __init__(self, api_url: str, token: str, timeout: int = 30):
        self.api_url = api_url
        self.token = token
        self.timeout = timeout

    def recognize(self, image_bytes: bytes) -> Dict[str, Any]:
        """调用在线 API 识别图片"""
        try:
            import io

            headers = {
                "Authorization": f"bearer {self.token}",
            }

            data = {
                "model": "PP-OCRv5",
                "optionalPayload": json.dumps({
                    "useDocOrientationClassify": False,
                    "useDocUnwarping": False,
                    "useTextlineOrientation": False,
                })
            }

            files = {"file": ("image.jpg", io.BytesIO(image_bytes), "image/jpeg")}

            response = requests.post(
                self.api_url,
                headers=headers,
                data=data,
                files=files,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f"PaddleOCR API 错误: HTTP {response.status_code}, {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

            job_id = response.json()["data"]["jobId"]

            # 轮询结果
            import time
            for _ in range(30):
                result_response = requests.get(f"{self.api_url}/{job_id}", headers=headers, timeout=self.timeout)
                if result_response.status_code != 200:
                    break

                state = result_response.json()["data"]["state"]
                if state == "done":
                    jsonl_url = result_response.json()["data"]["resultUrl"]["jsonUrl"]
                    jsonl_response = requests.get(jsonl_url, timeout=self.timeout)
                    if jsonl_response.status_code == 200:
                        lines = jsonl_response.text.strip().split('\n')
                        if lines:
                            result = json.loads(lines[0])["result"]
                            return {"success": True, "data": result}
                    break
                elif state == "failed":
                    return {"success": False, "error": "OCR识别失败"}

                time.sleep(1)

            return {"success": False, "error": "识别超时"}

        except requests.exceptions.Timeout:
            logger.error("PaddleOCR API 超时")
            return {"success": False, "error": "请求超时"}
        except Exception as e:
            logger.error(f"PaddleOCR API 失败: {str(e)}")
            return {"success": False, "error": str(e)}


def create_paddleocr_online_client(api_url: str, token: Optional[str] = None) -> Optional[PaddleOCROnlineClient]:
    """创建 PaddleOCR 在线客户端"""
    if not token or not api_url:
        return None
    return PaddleOCROnlineClient(api_url, token)

