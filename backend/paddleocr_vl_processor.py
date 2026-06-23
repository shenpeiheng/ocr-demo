"""
PaddleOCR-VL PDF 处理器（异步任务模式）
"""

import logging
import time
import requests
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PaddleOCRVLProcessor:
    """PaddleOCR-VL PDF 处理器"""

    def __init__(self, api_url: str, token: str, timeout: int = 600):
        self.api_url = api_url
        self.token = token
        self.timeout = timeout

    def process_pdf(self, pdf_path: str, model: str = "PaddleOCR-VL-1.6", **kwargs) -> Dict[str, Any]:
        """处理 PDF 文件"""
        try:
            headers = {"Authorization": f"bearer {self.token}"}

            data = {
                "model": model,
                "optionalPayload": json.dumps({
                    "useDocOrientationClassify": False,
                    "useDocUnwarping": False,
                    "useChartRecognition": False,
                })
            }

            with open(pdf_path, "rb") as f:
                files = {"file": f}
                response = requests.post(self.api_url, headers=headers, data=data, files=files, timeout=30)

            if response.status_code != 200:
                logger.error(f"提交任务失败: {response.status_code}, {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}"}

            job_id = response.json()["data"]["jobId"]
            logger.info(f"任务已提交: {job_id}")

            # 轮询任务状态
            start_time = time.time()
            poll_count = 0
            while time.time() - start_time < self.timeout:
                poll_count += 1
                status_response = requests.get(f"{self.api_url}/{job_id}", headers=headers, timeout=30)
                if status_response.status_code != 200:
                    logger.error(f"查询状态失败: {status_response.status_code}")
                    return {"success": False, "error": "查询任务状态失败"}

                state = status_response.json()["data"]["state"]
                elapsed = int(time.time() - start_time)
                logger.info(f"轮询 #{poll_count}，状态: {state}，已等待: {elapsed}s")

                if state == "done":
                    jsonl_url = status_response.json()["data"]["resultUrl"]["jsonUrl"]
                    jsonl_response = requests.get(jsonl_url, timeout=30)

                    markdown_content = ""
                    full_results = []
                    text_items = []
                    lines = jsonl_response.text.strip().split('\n')

                    logger.info(f"PaddleOCR-VL JSONL 总行数: {len(lines)}")

                    page_idx = 0
                    for line in lines:
                        if not line.strip():
                            continue
                        page_result = json.loads(line)["result"]
                        full_results.append(page_result)

                        # 检查是哪种模型
                        layout_results = page_result.get("layoutParsingResults", [])
                        logger.info(f"layoutParsingResults 数量: {len(layout_results)}")

                        # PP-OCRv6：没有 layoutParsingResults，有 ocrResults
                        if not layout_results and "ocrResults" in page_result:
                            ocr_results = page_result.get("ocrResults", [])
                            for ocr_page in ocr_results:
                                page_idx += 1
                                pruned = ocr_page.get("prunedResult", {})
                                texts = pruned.get("rec_texts", [])
                                boxes = pruned.get("rec_boxes", [])
                                scores = pruned.get("rec_scores", [])

                                page_text = []
                                for i, text in enumerate(texts):
                                    if text:
                                        page_text.append(text)
                                        text_items.append({
                                            "text": text,
                                            "page": page_idx,
                                            "confidence": scores[i] if i < len(scores) else 1.0,
                                            "bbox": boxes[i] if i < len(boxes) else [],
                                            "label": "text",
                                        })
                                markdown_content += "\n".join(page_text) + "\n\n"
                                logger.info(f"PP-OCRv6：页面 {page_idx} 提取 {len(page_text)} 个文本块")
                            continue

                        # PaddleOCR-VL-1.6：有 layoutParsingResults
                        for res in layout_results:
                            page_idx += 1
                            md_text = res["markdown"]["text"]
                            # 替换相对路径为完整 URL
                            images_map = res["markdown"].get("images", {})
                            for img_path, img_url in images_map.items():
                                md_text = md_text.replace(f'src="{img_path}"', f'src="{img_url}"')
                            markdown_content += md_text + "\n\n"

                            # 提取文本到 text_items
                            parsing_list = res.get("prunedResult", {}).get("parsing_res_list", [])
                            page_text_count = 0

                            for block in parsing_list:
                                block_label = block.get("block_label", "")
                                block_content = block.get("block_content", "").strip()

                                # 跳过图片块，其他所有文本块都保留
                                if block_label not in ["image", "figure"] and block_content:
                                    text_items.append({
                                        "text": block_content,
                                        "page": page_idx,
                                        "confidence": 1.0,
                                        "bbox": block.get("block_bbox", []),
                                        "label": block_label,
                                    })
                                    page_text_count += 1

                            logger.info(f"PaddleOCR-VL-1.6：页面 {page_idx} 提取 {page_text_count} 个文本块")

                    logger.info(f"总共提取了 {len(text_items)} 个文本块")

                    return {
                        "success": True,
                        "raw_text": markdown_content,
                        "markdown": markdown_content,
                        "combined_results": {
                            "markdown": markdown_content,
                            "text_items": text_items,
                            "total_items": len(text_items),
                            "layoutParsingResults": full_results,
                        },
                        "json_result": {"jobId": job_id, "resultUrl": jsonl_url},
                    }

                elif state == "failed":
                    error_msg = status_response.json()["data"].get("errorMsg", "未知错误")
                    logger.error(f"任务失败: {error_msg}")
                    return {"success": False, "error": error_msg}

                time.sleep(5)

            return {"success": False, "error": "任务超时"}

        except Exception as e:
            logger.error(f"PaddleOCR-VL 处理失败: {str(e)}")
            return {"success": False, "error": str(e)}


def create_paddleocr_vl_processor(api_url: str, token: str, timeout: int = 600) -> Optional[PaddleOCRVLProcessor]:
    """创建 PaddleOCR-VL 处理器"""
    if not api_url or not token:
        return None
    return PaddleOCRVLProcessor(api_url, token, timeout)
