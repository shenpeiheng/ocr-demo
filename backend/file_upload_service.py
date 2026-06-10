"""
文件上传服务 - 将本地文件上传到 tmpfile.link
"""

import logging
import os
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)


class FileUploadService:
    """文件上传服务 - tmpfile.link"""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """上传文件到 tmpfile.link"""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}

        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return {"success": False, "error": "文件大小为 0"}

        logger.info(f"准备上传文件到 tmpfile.link: {file_path} ({file_size} bytes)")

        try:
            filename = os.path.basename(file_path)

            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "application/pdf")}
                response = requests.post(
                    "https://tmpfile.link/api/upload",
                    files=files,
                    timeout=self.timeout
                )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"tmpfile.link 响应: {result}")
                url = result.get("downloadLink", "").strip()
                if url:
                    logger.info(f"上传成功: {url}")
                    return {"success": True, "url": url}
                else:
                    logger.error(f"上传失败: 未返回下载链接，响应: {result}")
                    return {"success": False, "error": "未返回下载链接"}
            else:
                logger.error(f"上传失败: HTTP {response.status_code}, 响应: {response.text[:500]}")
                return {"success": False, "error": f"上传失败: HTTP {response.status_code}"}

        except requests.exceptions.Timeout:
            logger.error("上传超时")
            return {"success": False, "error": "上传超时"}
        except Exception as e:
            logger.error(f"上传失败: {str(e)}")
            return {"success": False, "error": f"上传失败: {str(e)}"}


def create_file_upload_service() -> FileUploadService:
    """创建文件上传服务实例"""
    return FileUploadService()
