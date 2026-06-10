"""
MinerU 官方 API 集成
使用 MinerU 官方网站的 API Token
文档: https://mineru.net/apiManage/docs
"""
import subprocess
import json
import time
import logging
from typing import Optional, Dict, Any, List
import os
import tempfile

logger = logging.getLogger(__name__)


class MinerUOfficialAPI:
    """MinerU 官方 API 客户端"""

    def __init__(self, token: str, api_url: str = "https://mineru.net/api/v4/extract"):
        """
        初始化 MinerU 官方 API 客户端

        Args:
            token: MinerU API Token (从 https://mineru.net/apiManage 获取)
            api_url: MinerU API 基础 URL
        """
        self.token = token
        self.api_url = api_url.rstrip("/")

    def parse_pdf_file(
        self,
        pdf_path: str,
        model_version: str = "vlm",
        enable_formula: bool = True,
        enable_table: bool = True,
        is_ocr: bool = True,
        language: str = "ch",
        page_ranges: Optional[str] = None,
        extra_formats: Optional[List[str]] = None,
        max_wait_time: int = 300
    ) -> Dict[str, Any]:
        """直接上传 PDF 文件解析（精准模式）- 使用 curl"""
        import os
        try:
            if not os.path.exists(pdf_path):
                return {"success": False, "error": f"文件不存在: {pdf_path}"}

            task_url = f"{self.api_url}/task"

            # 构建 curl 命令
            cmd = [
                'curl', '-k', '-X', 'POST', task_url,
                '-H', f'Authorization: Bearer {self.token}',
                '-F', f'file=@{pdf_path}',
                '-F', f'model_version={model_version}',
                '-F', f'enable_formula={str(enable_formula).lower()}',
                '-F', f'enable_table={str(enable_table).lower()}',
                '-F', f'is_ocr={str(is_ocr).lower()}',
                '-F', f'language={language}',
            ]

            if page_ranges:
                cmd.extend(['-F', f'page_ranges={page_ranges}'])
            if extra_formats:
                cmd.extend(['-F', f'extra_formats={",".join(extra_formats)}'])

            logger.info(f"上传 PDF 到 MinerU 官方 API: {pdf_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                return {"success": False, "error": f"curl 失败: {result.stderr}"}

            data = json.loads(result.stdout)
            if data.get("code") != 0:
                error_msg = data.get("msg", "创建任务失败")
                logger.error(f"MinerU 任务创建失败: {error_msg}")
                return {"success": False, "error": error_msg}

            task_id = data["data"]["task_id"]
            logger.info(f"MinerU 任务创建成功，task_id: {task_id}")

            return self._poll_task_result(task_id, max_wait_time)

        except subprocess.TimeoutExpired:
            logger.error("上传超时")
            return {"success": False, "error": "上传超时"}
        except json.JSONDecodeError as e:
            logger.error(f"解析响应失败: {e}")
            return {"success": False, "error": f"解析响应失败: {str(e)}"}
        except Exception as e:
            logger.error(f"MinerU 解析异常: {str(e)}")
            return {"success": False, "error": f"解析异常: {str(e)}"}

    def parse_pdf_url(
        self,
        file_url: str,
        model_version: str = "vlm",
        enable_formula: bool = True,
        enable_table: bool = True,
        is_ocr: bool = True,
        language: str = "ch",
        page_ranges: Optional[str] = None,
        extra_formats: Optional[List[str]] = None,
        max_wait_time: int = 300
    ) -> Dict[str, Any]:
        """通过 URL 解析 PDF - 使用 curl"""
        try:
            task_url = f"{self.api_url}/task"

            payload = {
                "url": file_url,
                "model_version": model_version,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
                "is_ocr": is_ocr,
                "language": language,
            }

            if page_ranges:
                payload["page_ranges"] = page_ranges
            if extra_formats:
                payload["extra_formats"] = extra_formats

            logger.info(f"创建 MinerU 解析任务: {file_url}")

            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
                json.dump(payload, f)
                payload_file = f.name

            try:
                cmd = [
                    'curl', '-k', '-X', 'POST', task_url,
                    '-H', f'Authorization: Bearer {self.token}',
                    '-H', 'Content-Type: application/json',
                    '-d', f'@{payload_file}'
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    return {"success": False, "error": f"请求失败: {result.stderr}"}

                logger.info(f"MinerU API 响应: {result.stdout}")
                data = json.loads(result.stdout)

                if data.get("code") != 0:
                    error_msg = data.get("msg", "创建任务失败")
                    logger.error(f"MinerU 任务创建失败: {error_msg}, 完整响应: {data}")
                    return {"success": False, "error": error_msg}

                task_id = data["data"]["task_id"]
                logger.info(f"MinerU 任务创建成功，task_id: {task_id}")

                return self._poll_task_result(task_id, max_wait_time)

            finally:
                os.unlink(payload_file)

        except subprocess.TimeoutExpired:
            logger.error("MinerU API 请求超时")
            return {"success": False, "error": "请求超时"}
        except Exception as e:
            logger.error(f"MinerU API 请求失败: {str(e)}")
            return {"success": False, "error": f"请求失败: {str(e)}"}

    def _poll_task_result(
        self,
        task_id: str,
        max_wait_time: int = 300,
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """轮询任务结果 - 使用 curl"""
        query_url = f"{self.api_url}/task/{task_id}"
        start_time = time.time()
        attempt = 0

        while time.time() - start_time < max_wait_time:
            attempt += 1
            try:
                cmd = ['curl', '-k', '-X', 'GET', query_url, '-H', f'Authorization: Bearer {self.token}']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode != 0:
                    logger.error(f"查询任务失败: {result.stderr}")
                    time.sleep(poll_interval)
                    continue

                data = json.loads(result.stdout)
                if data.get("code") != 0:
                    logger.error(f"查询任务失败: {data.get('msg')}")
                    return {"success": False, "error": data.get("msg", "查询任务失败")}

                state = data["data"].get("state")
                logger.info(f"任务状态 (尝试 {attempt}): {state}")

                if state == "done":
                    logger.info(f"任务完成，返回数据: {data['data']}")

                    zip_url = data["data"].get("full_zip_url")
                    markdown_url = data["data"].get("markdown_url")

                    return {
                        "success": True,
                        "task_id": task_id,
                        "state": state,
                        "full_zip_url": zip_url,
                        "markdown_url": markdown_url,
                        "result_url": data["data"].get("result_url"),
                        "extra_files": data["data"].get("extra_files", {}),
                        "message": "解析完成"
                    }
                elif state == "failed":
                    error = data["data"].get("error", "解析失败")
                    logger.error(f"MinerU 解析失败: {error}")
                    return {"success": False, "task_id": task_id, "state": state, "error": error}
                elif state in ["pending", "processing", "running"]:
                    time.sleep(poll_interval)
                    continue
                else:
                    logger.warning(f"未知任务状态: {state}")
                    time.sleep(poll_interval)
                    continue

            except Exception as e:
                logger.error(f"查询任务异常: {str(e)}")
                time.sleep(poll_interval)
                continue

        elapsed = round(time.time() - start_time, 2)
        logger.error(f"任务查询超时，已等待 {elapsed} 秒")
        return {"success": False, "task_id": task_id, "error": f"解析超时（已等待 {elapsed} 秒）"}

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态（单次查询，不轮询）

        Args:
            task_id: 任务 ID

        Returns:
            任务状态字典
        """
        try:
            query_url = f"{self.api_url}/task/{task_id}"
            response = requests.get(query_url, headers=self.headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get("code") != 200:
                return {
                    "success": False,
                    "error": result.get("msg", "查询失败")
                }

            return {
                "success": True,
                "data": result["data"]
            }

        except Exception as e:
            logger.error(f"查询任务状态异常: {str(e)}")
            return {
                "success": False,
                "error": f"查询异常: {str(e)}"
            }

    def download_and_extract_zip(self, zip_url: str, output_dir: str) -> Dict[str, Any]:
        """下载并解压 ZIP，返回所有文件路径"""
        try:
            import zipfile
            logger.info(f"下载 ZIP: {zip_url}")

            cmd = ['curl', '-k', '-L', '-X', 'GET', zip_url]
            result = subprocess.run(cmd, capture_output=True, timeout=120)

            if result.returncode != 0:
                return {"success": False, "error": f"下载失败: {result.stderr}"}

            os.makedirs(output_dir, exist_ok=True)
            zip_path = os.path.join(output_dir, "result.zip")

            with open(zip_path, 'wb') as f:
                f.write(result.stdout)

            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(output_dir)

            os.unlink(zip_path)

            # 查找 Markdown 和 JSON 文件
            md_file = None
            json_file = None
            images_dir = None

            for root, dirs, files in os.walk(output_dir):
                for f in files:
                    if f.endswith('.md'):
                        md_file = os.path.join(root, f)
                    elif f.endswith('.json'):
                        json_file = os.path.join(root, f)
                if 'images' in dirs:
                    images_dir = os.path.join(root, 'images')

            return {
                "success": True,
                "markdown_path": md_file,
                "json_path": json_file,
                "images_dir": images_dir,
                "output_dir": output_dir
            }

        except Exception as e:
            logger.error(f"下载解压失败: {str(e)}")
            return {"success": False, "error": str(e)}
        """下载 Markdown 结果 - 使用 curl，支持 zip"""
        try:
            # 如果是 zip 文件，下载并解压
            if markdown_url.endswith('.zip'):
                import zipfile
                logger.info(f"下载并解压 ZIP: {markdown_url}")

                cmd = ['curl', '-k', '-L', '-X', 'GET', markdown_url]
                result = subprocess.run(cmd, capture_output=True, timeout=60)

                if result.returncode != 0:
                    return {"success": False, "error": f"下载失败: {result.stderr}"}

                # 保存到临时文件并解压
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                    tmp.write(result.stdout)
                    zip_path = tmp.name

                try:
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        # 查找 .md 文件
                        md_files = [f for f in z.namelist() if f.endswith('.md')]
                        if not md_files:
                            return {"success": False, "error": "ZIP 中未找到 Markdown 文件"}

                        # 读取第一个 .md 文件
                        markdown_content = z.read(md_files[0]).decode('utf-8')
                        logger.info(f"从 ZIP 中提取 Markdown: {md_files[0]}")

                        return {
                            "success": True,
                            "markdown": markdown_content,
                            "length": len(markdown_content)
                        }
                finally:
                    os.unlink(zip_path)

            else:
                # 直接下载 Markdown
                cmd = ['curl', '-k', '-X', 'GET', markdown_url]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                if result.returncode != 0:
                    return {"success": False, "error": f"下载失败: {result.stderr}"}

                markdown_content = result.stdout
                return {
                    "success": True,
                    "markdown": markdown_content,
                    "length": len(markdown_content)
                }

        except Exception as e:
            logger.error(f"下载 Markdown 失败: {str(e)}")
            return {"success": False, "error": f"下载失败: {str(e)}"}


def create_mineru_official_client(token: str, api_url: str = "https://mineru.net/api/v4/extract") -> MinerUOfficialAPI:
    """
    创建 MinerU 官方 API 客户端

    Args:
        token: MinerU API Token
        api_url: MinerU API 基础 URL

    Returns:
        MinerUOfficialAPI 实例
    """
    return MinerUOfficialAPI(token, api_url)
