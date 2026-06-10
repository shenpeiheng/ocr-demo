"""
PaddleOCR 在线 API 客户端
"""

import logging
import requests
import json
from typing import Dict, Any, Optional

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
            headers = {
                "Authorization": f"bearer {self.token}",
            }

            data = {
                "model": "PaddleOCR-VL-1.6",
                "optionalPayload": json.dumps({
                    "useDocOrientationClassify": False,
                    "useDocUnwarping": False,
                    "useChartRecognition": False,
                })
            }

            files = {"file": ("image.jpg", image_bytes, "image/jpeg")}

            response = requests.post(
                self.api_url,
                headers=headers,
                data=data,
                files=files,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                return {"success": True, "data": result}
            else:
                logger.error(f"PaddleOCR API 错误: HTTP {response.status_code}, {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

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

