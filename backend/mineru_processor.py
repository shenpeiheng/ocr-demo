"""
MinerU PDF解析适配器。

默认通过 ModelScope OpenAI-compatible API 调用 MinerU VLM 模型，并保留自建
HTTP 服务的兼容入口。
"""

import base64
import logging
import os
import time
from io import BytesIO
from typing import Any, Dict, List, Optional

from PIL import Image
import requests


logger = logging.getLogger(__name__)

DEFAULT_MODELSCOPE_BASE_URL = "https://api-inference.modelscope.cn/v1"
DEFAULT_MODELSCOPE_MINERU_MODEL = "OpenDataLab/MinerU2.5-2509-1.2B"
MODELSCOPE_REQUEST_MODES = {"modelscope", "modelscope_vl", "openai_vl"}
SUPPORTED_INLINE_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MINERU_MODEL_INPUT_MAX_DIMENSION = int(os.getenv("MINERU_MAX_IMAGE_DIMENSION", "2048"))
MINERU_MODEL_MAX_TOKENS = int(os.getenv("MINERU_MAX_TOKENS", "8192"))

DEFAULT_MODELSCOPE_PROMPT = (
    "Document parsing: convert this PDF page image into clean Markdown. "
    "Preserve reading order, headings, lists, tables, formulas, captions and visible text. "
    "Use Markdown tables when possible, HTML tables for complex tables, and LaTeX for formulas. "
    "Return only the Markdown content, without explanations or code fences."
)


class MinerUProcessor:
    """调用 MinerU PDF 解析服务并归一化结果。"""

    def __init__(
        self,
        api_url: str = "",
        api_key: str = "",
        model: str = DEFAULT_MODELSCOPE_MINERU_MODEL,
        timeout: int = 300,
        request_mode: str = "modelscope_vl",
    ):
        requested_mode = (request_mode or "modelscope_vl").strip().lower()
        provided_api_url = (api_url or "").strip()
        if requested_mode not in MODELSCOPE_REQUEST_MODES and not provided_api_url:
            logger.info("未配置自建MinerU服务地址，自动使用ModelScope MinerU模型")
            requested_mode = "modelscope_vl"

        self.request_mode = requested_mode
        default_api_url = DEFAULT_MODELSCOPE_BASE_URL if self._is_modelscope_mode() else ""
        self.api_url = (provided_api_url or default_api_url).strip()
        self.api_key = (api_key or "").strip()
        self.model = (model or DEFAULT_MODELSCOPE_MINERU_MODEL).strip()
        self.timeout = timeout
        self.initialized = bool(self.api_url and (self.api_key or not self._is_modelscope_mode()))

    def process_pdf(
        self,
        pdf_path: str,
        pdf_info: Optional[Dict[str, Any]] = None,
        max_pages: int = 50,
        output_dir: Optional[str] = None,
        dpi: int = 200,
    ) -> Dict[str, Any]:
        """解析 PDF 并返回兼容现有前端的结果结构。"""
        pdf_info = pdf_info or self._build_basic_pdf_info(pdf_path)

        if self._is_modelscope_mode():
            return self._process_pdf_with_modelscope_vl(
                pdf_path,
                pdf_info=pdf_info,
                max_pages=max_pages,
                output_dir=output_dir,
                dpi=dpi,
            )

        if not self.initialized:
            return self._get_error_result(
                "未配置 MinerU 服务地址，请设置 MINERU_API_URL 后重试",
                pdf_info,
            )

        if not os.path.exists(pdf_path):
            return self._get_error_result(f"PDF文件不存在: {pdf_path}", pdf_info)

        start_time = time.time()
        api_result = self._call_mineru_api(pdf_path, max_pages=max_pages)
        processing_time = round(time.time() - start_time, 2)

        if not api_result.get("success"):
            return self._get_error_result(api_result.get("error", "MinerU调用失败"), pdf_info)

        return self._normalize_mineru_response(
            api_result.get("data"),
            pdf_info=pdf_info,
            max_pages=max_pages,
            processing_time=processing_time,
        )

    def _is_modelscope_mode(self) -> bool:
        return self.request_mode in MODELSCOPE_REQUEST_MODES

    def _process_pdf_with_modelscope_vl(
        self,
        pdf_path: str,
        pdf_info: Dict[str, Any],
        max_pages: int,
        output_dir: Optional[str],
        dpi: int,
    ) -> Dict[str, Any]:
        if not self.api_key:
            return self._get_error_result(
                "未配置 ModelScope API Key，请设置 MINERU_API_KEY 或 MODELSCOPE_API_KEY 后重试",
                pdf_info,
            )

        if not os.path.exists(pdf_path):
            return self._get_error_result(f"PDF文件不存在: {pdf_path}", pdf_info)

        try:
            from pdf_processor import create_pdf_processor

            max_pages = max(1, int(max_pages or 1))
            dpi = max(72, int(dpi or 200))
            total_pages = int(pdf_info.get("total_pages") or 0)
            pages_to_process = min(total_pages, max_pages) if total_pages > 0 else max_pages

            pdf_converter = create_pdf_processor()
            if not pdf_converter.initialized:
                return self._get_error_result("PDF处理器未初始化，无法渲染PDF页面后调用MinerU模型", pdf_info)

            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            start_time = time.time()
            conversion_result = pdf_converter.convert_pdf_to_images(
                pdf_path,
                output_dir=output_dir,
                dpi=dpi,
                first_page=1,
                last_page=pages_to_process,
            )
            if not conversion_result.get("success"):
                return self._get_error_result(conversion_result.get("error", "PDF页面渲染失败"), pdf_info)

            image_paths = conversion_result.get("image_paths", [])
            if not image_paths:
                return self._get_error_result("PDF页面渲染失败，未生成可供MinerU模型识别的图片", pdf_info)

            page_results = []
            pages_summary = []
            all_text_items = []
            markdown_parts = []
            raw_responses = []

            for index, image_path in enumerate(image_paths, 1):
                logger.info("调用ModelScope MinerU模型解析页面 %s/%s: %s", index, len(image_paths), image_path)
                page_start = time.time()
                page_result = self._call_modelscope_vl_page(image_path)
                page_time = round(time.time() - page_start, 2)

                if page_result.get("success"):
                    markdown = (page_result.get("content") or "").strip()
                    page_items = self._markdown_to_text_items(markdown, page_number=index)
                    all_text_items.extend(page_items)
                    if markdown:
                        markdown_parts.append(markdown)
                    raw_responses.append(page_result.get("raw_response"))
                    page_results.append(
                        {
                            "success": True,
                            "page_number": index,
                            "text_items": page_items,
                            "markdown": markdown,
                            "processing_time": page_time,
                            "image_path": image_path,
                            "model_input_info": page_result.get("model_input_info", {}),
                        }
                    )
                    pages_summary.append(
                        {
                            "page_number": index,
                            "total_items": len(page_items),
                            "processing_time": page_time,
                            "success": True,
                        }
                    )
                    continue

                page_error = page_result.get("error", "MinerU模型解析失败")
                page_results.append(
                    {
                        "success": False,
                        "page_number": index,
                        "text_items": [],
                        "markdown": "",
                        "processing_time": page_time,
                        "image_path": image_path,
                        "error": page_error,
                    }
                )
                pages_summary.append(
                    {
                        "page_number": index,
                        "total_items": 0,
                        "processing_time": page_time,
                        "success": False,
                        "error": page_error,
                    }
                )

            successful_pages = [item for item in page_results if item.get("success")]
            if not successful_pages:
                first_error = next((item.get("error") for item in page_results if item.get("error")), "MinerU模型解析失败")
                return self._get_error_result(first_error, pdf_info)

            processing_time = round(time.time() - start_time, 2)
            combined_markdown = "\n\n".join(markdown_parts).strip()
            actual_pages = len(image_paths)
            conversion_info = dict(conversion_result.get("conversion_info") or {})
            conversion_info.update(
                {
                    "engine": "mineru",
                    "provider": "modelscope",
                    "model": self.model,
                    "image_paths": image_paths,
                }
            )

            return {
                "success": True,
                "pdf_info": pdf_info,
                "conversion_info": conversion_info,
                "ocr_results": page_results,
                "combined_results": {
                    "text_items": all_text_items,
                    "total_items": len(all_text_items),
                    "total_pages": actual_pages,
                    "total_processing_time": processing_time,
                    "markdown": combined_markdown,
                    "raw_text": combined_markdown,
                    "raw_response": raw_responses,
                },
                "pages_summary": pages_summary,
                "processing_info": {
                    "engine": "mineru",
                    "provider": "modelscope",
                    "model": self.model,
                    "max_pages": max_pages,
                    "actual_pages_processed": actual_pages,
                    "request_mode": self.request_mode,
                    "dpi": dpi,
                    "api_url": self._build_chat_completions_url(),
                },
            }
        except Exception as exc:
            logger.error("ModelScope MinerU处理失败: %s", exc)
            return self._get_error_result(f"ModelScope MinerU处理失败: {str(exc)}", pdf_info)

    def _call_mineru_api(self, pdf_path: str, max_pages: int) -> Dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            if self.request_mode == "json_base64":
                with open(pdf_path, "rb") as file_obj:
                    encoded_pdf = base64.b64encode(file_obj.read()).decode("utf-8")

                payload = {
                    "model": self.model,
                    "filename": os.path.basename(pdf_path),
                    "file": encoded_pdf,
                    "file_type": "pdf",
                    "max_pages": max_pages,
                    "output_format": "json",
                }
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
            else:
                form_data = {
                    "model": self.model,
                    "max_pages": str(max_pages),
                    "output_format": "json",
                    "return_content_list": "true",
                }
                with open(pdf_path, "rb") as file_obj:
                    files = {
                        "file": (os.path.basename(pdf_path), file_obj, "application/pdf"),
                    }
                    response = requests.post(
                        self.api_url,
                        headers=headers,
                        data=form_data,
                        files=files,
                        timeout=self.timeout,
                    )

            return self._parse_response(response)
        except requests.exceptions.Timeout:
            return {"success": False, "error": "MinerU API调用超时"}
        except Exception as exc:
            logger.error("MinerU API调用异常: %s", exc)
            return {"success": False, "error": f"MinerU API调用异常: {str(exc)}"}

    def _call_modelscope_vl_page(self, image_path: str) -> Dict[str, Any]:
        try:
            image_payload = self._prepare_image_for_modelscope(image_path)
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": DEFAULT_MODELSCOPE_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_payload['mime_type']};base64,{image_payload['base64']}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": MINERU_MODEL_MAX_TOKENS,
                "temperature": 0,
                "top_p": 0.01,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            response = requests.post(
                self._build_chat_completions_url(),
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            parsed = self._parse_modelscope_chat_response(response)
            if parsed.get("success"):
                parsed["model_input_info"] = {
                    "width": image_payload["api_width"],
                    "height": image_payload["api_height"],
                    "resized": image_payload["resized"],
                    "max_dimension": MINERU_MODEL_INPUT_MAX_DIMENSION,
                }
            return parsed
        except requests.exceptions.Timeout:
            return {"success": False, "error": "ModelScope MinerU模型调用超时"}
        except Exception as exc:
            logger.error("ModelScope MinerU模型调用异常: %s", exc)
            return {"success": False, "error": f"ModelScope MinerU模型调用异常: {str(exc)}"}

    def _build_chat_completions_url(self) -> str:
        api_url = (self.api_url or DEFAULT_MODELSCOPE_BASE_URL).rstrip("/")
        if api_url.endswith("/chat/completions"):
            return api_url
        return f"{api_url}/chat/completions"

    def _prepare_image_for_modelscope(self, image_path: str) -> Dict[str, Any]:
        with Image.open(image_path) as img:
            img.load()
            original_width, original_height = img.size
            original_format = img.format
            original_mime_type = Image.MIME.get(original_format, "image/png")
            max_dimension = max(original_width, original_height)

            if (
                max_dimension <= MINERU_MODEL_INPUT_MAX_DIMENSION
                and original_mime_type in SUPPORTED_INLINE_IMAGE_MIME_TYPES
            ):
                with open(image_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                return {
                    "base64": encoded_string,
                    "mime_type": original_mime_type,
                    "original_width": original_width,
                    "original_height": original_height,
                    "api_width": original_width,
                    "api_height": original_height,
                    "resized": False,
                }

            api_img = img.copy()
            resized = False
            if max_dimension > MINERU_MODEL_INPUT_MAX_DIMENSION:
                scale = MINERU_MODEL_INPUT_MAX_DIMENSION / max_dimension
                api_width = max(1, int(original_width * scale))
                api_height = max(1, int(original_height * scale))
                resample_filter = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
                api_img = api_img.resize((api_width, api_height), resample_filter)
                resized = True
                logger.info(
                    "MinerU模型输入图片超过限制，已压缩: %sx%s -> %sx%s",
                    original_width,
                    original_height,
                    api_width,
                    api_height,
                )
            else:
                api_width, api_height = original_width, original_height

            if api_img.mode in ("RGBA", "LA"):
                background = Image.new("RGB", api_img.size, (255, 255, 255))
                alpha = api_img.getchannel("A")
                background.paste(api_img.convert("RGB"), mask=alpha)
                api_img = background
            elif api_img.mode == "P":
                api_img = api_img.convert("RGBA")
                background = Image.new("RGB", api_img.size, (255, 255, 255))
                background.paste(api_img.convert("RGB"), mask=api_img.getchannel("A"))
                api_img = background
            elif api_img.mode not in ("RGB", "L"):
                api_img = api_img.convert("RGB")

            buffer = BytesIO()
            api_img.save(buffer, format="PNG", optimize=True)
            encoded_string = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return {
                "base64": encoded_string,
                "mime_type": "image/png",
                "original_width": original_width,
                "original_height": original_height,
                "api_width": api_width,
                "api_height": api_height,
                "resized": resized,
            }

    def _parse_modelscope_chat_response(self, response) -> Dict[str, Any]:
        if response.status_code < 200 or response.status_code >= 300:
            body_preview = response.text[:500] if response.text else ""
            return {
                "success": False,
                "error": f"ModelScope MinerU模型返回错误状态 {response.status_code}: {body_preview}",
            }

        try:
            data = response.json()
        except ValueError:
            return {"success": True, "content": response.text, "raw_response": response.text}

        if isinstance(data, dict) and data.get("error"):
            error = data.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("code") or str(error)
            else:
                message = str(error)
            return {"success": False, "error": message}

        content = ""
        if isinstance(data, dict):
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                first_choice = choices[0]
                message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
                content = message.get("content") if isinstance(message, dict) else ""
                if isinstance(content, list):
                    content = "\n".join(
                        item.get("text", "") for item in content if isinstance(item, dict) and item.get("text")
                    )
                if not content and isinstance(first_choice, dict):
                    content = first_choice.get("text", "")

        if not content:
            return {"success": False, "error": f"ModelScope响应中未找到文本内容: {str(data)[:500]}"}

        return {"success": True, "content": str(content).strip(), "raw_response": data}

    def _parse_response(self, response) -> Dict[str, Any]:
        if response.status_code < 200 or response.status_code >= 300:
            body_preview = response.text[:500] if response.text else ""
            return {
                "success": False,
                "error": f"MinerU API返回错误状态 {response.status_code}: {body_preview}",
            }

        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text}

        if isinstance(data, dict) and data.get("success") is False:
            return {"success": False, "error": data.get("error") or data.get("message") or "MinerU解析失败"}

        return {"success": True, "data": data}

    def _normalize_mineru_response(
        self,
        response_data: Any,
        pdf_info: Dict[str, Any],
        max_pages: int,
        processing_time: float,
    ) -> Dict[str, Any]:
        payload = self._unwrap_payload(response_data)
        if isinstance(payload, str):
            markdown = payload.strip()
        else:
            markdown = self._find_first_string(
                payload,
                ["md_content", "markdown", "markdown_content", "md", "raw_text", "text"],
            )
        structured_items = self._extract_structured_items(payload)

        text_items = self._build_text_items(structured_items)
        if not text_items and markdown:
            text_items = self._markdown_to_text_items(markdown)

        raw_text = markdown or "\n".join(item.get("text", "") for item in text_items if item.get("text"))
        actual_pages = self._guess_actual_pages(pdf_info, text_items, max_pages)
        pages_summary = self._build_pages_summary(text_items, actual_pages, processing_time)

        return {
            "success": True,
            "pdf_info": pdf_info,
            "conversion_info": {
                "engine": "mineru",
                "image_paths": [],
            },
            "ocr_results": [],
            "combined_results": {
                "text_items": text_items,
                "total_items": len(text_items),
                "total_pages": actual_pages,
                "total_processing_time": processing_time,
                "markdown": markdown or "",
                "raw_text": raw_text,
                "raw_response": response_data,
            },
            "pages_summary": pages_summary,
            "processing_info": {
                "engine": "mineru",
                "model": self.model,
                "max_pages": max_pages,
                "actual_pages_processed": actual_pages,
                "request_mode": self.request_mode,
            },
        }

    def _build_text_items(self, structured_items: List[Any]) -> List[Dict[str, Any]]:
        text_items = []
        for raw_item in structured_items:
            text = self._extract_item_text(raw_item)
            if not text:
                continue

            item_type = self._extract_item_type(raw_item)
            text_items.append(
                {
                    "id": len(text_items) + 1,
                    "text": text,
                    "confidence": self._extract_confidence(raw_item),
                    "location": self._extract_location(raw_item),
                    "type": item_type,
                    "page": self._extract_page_number(raw_item),
                    "source": "mineru",
                }
            )
        return text_items

    def _extract_structured_items(self, payload: Any) -> List[Any]:
        if isinstance(payload, list):
            return payload

        pages = self._find_first_list(payload, ["pages", "page_list"])
        if pages:
            page_items = self._extract_page_items(pages)
            if page_items:
                return page_items

        return self._find_first_list(
            payload,
            ["content_list", "blocks", "elements", "items", "layout", "paragraphs"],
        ) or []

    def _extract_page_items(self, pages: List[Any]) -> List[Any]:
        items = []
        for index, page in enumerate(pages, 1):
            if not isinstance(page, dict):
                continue

            page_number = self._extract_page_number(page, default=index)
            blocks = self._find_first_list(
                page,
                ["content_list", "blocks", "elements", "items", "paragraphs"],
                recursive=False,
            )
            if blocks:
                for block in blocks:
                    if isinstance(block, dict) and "page" not in block and "page_number" not in block:
                        block = dict(block)
                        block["page_number"] = page_number
                    items.append(block)
                continue

            page_text = self._find_first_string(page, ["markdown", "text", "content"], recursive=False)
            if page_text:
                items.append(
                    {
                        "text": page_text,
                        "type": "page_text",
                        "page_number": page_number,
                    }
                )
        return items

    def _extract_item_text(self, item: Any) -> str:
        if isinstance(item, str):
            return item.strip()
        if not isinstance(item, dict):
            return ""

        text_keys = [
            "text",
            "content",
            "markdown",
            "md_content",
            "table_body",
            "html",
            "latex",
            "equation",
            "caption",
        ]
        for key in text_keys:
            value = item.get(key)
            text = self._stringify_value(value)
            if text:
                return text

        caption_parts = []
        for key in ["table_caption", "image_caption", "figure_caption"]:
            caption = self._stringify_value(item.get(key))
            if caption:
                caption_parts.append(caption)
        return "\n".join(caption_parts).strip()

    def _extract_item_type(self, item: Any) -> str:
        if not isinstance(item, dict):
            return "text"
        return str(item.get("type") or item.get("category") or item.get("class") or "text")

    def _extract_confidence(self, item: Any) -> float:
        if isinstance(item, dict):
            for key in ["confidence", "score", "prob"]:
                value = item.get(key)
                if isinstance(value, (int, float)):
                    return round(float(value), 4)
        return 0.95

    def _extract_page_number(self, item: Any, default: int = 1) -> int:
        if not isinstance(item, dict):
            return default

        for key in ["page_number", "page", "page_no"]:
            value = item.get(key)
            if isinstance(value, int):
                return max(1, value)
            if isinstance(value, str) and value.isdigit():
                return max(1, int(value))

        for key in ["page_idx", "page_index"]:
            value = item.get(key)
            if isinstance(value, int):
                return max(1, value + 1)
            if isinstance(value, str) and value.isdigit():
                return max(1, int(value) + 1)

        return default

    def _extract_location(self, item: Any) -> Dict[str, int]:
        if not isinstance(item, dict):
            return self._empty_location()

        bbox = item.get("bbox") or item.get("box") or item.get("position") or item.get("coordinates")
        if isinstance(bbox, dict):
            left = int(bbox.get("left", bbox.get("x", bbox.get("x1", 0))) or 0)
            top = int(bbox.get("top", bbox.get("y", bbox.get("y1", 0))) or 0)
            width = int(bbox.get("width", 0) or 0)
            height = int(bbox.get("height", 0) or 0)
            right = int(bbox.get("right", bbox.get("x2", left + width)) or 0)
            bottom = int(bbox.get("bottom", bbox.get("y2", top + height)) or 0)
            if not width:
                width = max(0, right - left)
            if not height:
                height = max(0, bottom - top)
            return {"left": left, "top": top, "width": width, "height": height, "right": right, "bottom": bottom}

        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            if isinstance(bbox[0], (list, tuple)):
                xs = [point[0] for point in bbox if len(point) >= 2]
                ys = [point[1] for point in bbox if len(point) >= 2]
                if not xs or not ys:
                    return self._empty_location()
                left, right = int(min(xs)), int(max(xs))
                top, bottom = int(min(ys)), int(max(ys))
            else:
                left, top, right, bottom = [int(float(value)) for value in bbox[:4]]
            return {
                "left": left,
                "top": top,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
                "right": right,
                "bottom": bottom,
            }

        return self._empty_location()

    def _markdown_to_text_items(self, markdown: str, page_number: int = 1) -> List[Dict[str, Any]]:
        text_items = []
        for line in markdown.splitlines():
            text = line.strip()
            if not text:
                continue
            text_items.append(
                {
                    "id": len(text_items) + 1,
                    "text": text,
                    "confidence": 0.95,
                    "location": self._empty_location(),
                    "type": "table" if text.startswith("|") else "text",
                    "page": page_number,
                    "source": "mineru",
                }
            )
        return text_items

    def _build_pages_summary(
        self,
        text_items: List[Dict[str, Any]],
        actual_pages: int,
        processing_time: float,
    ) -> List[Dict[str, Any]]:
        if actual_pages <= 0:
            return []

        page_counts = {}
        for item in text_items:
            page = item.get("page", 1)
            page_counts[page] = page_counts.get(page, 0) + 1

        per_page_time = round(processing_time / actual_pages, 2) if actual_pages else 0
        return [
            {
                "page_number": page,
                "total_items": page_counts.get(page, 0),
                "processing_time": per_page_time,
                "success": True,
            }
            for page in range(1, actual_pages + 1)
        ]

    def _guess_actual_pages(self, pdf_info: Dict[str, Any], text_items: List[Dict[str, Any]], max_pages: int) -> int:
        total_pages = int(pdf_info.get("total_pages") or 0)
        max_item_page = max([item.get("page", 1) for item in text_items], default=0)
        if total_pages > 0:
            return min(total_pages, max_pages)
        return max_item_page

    def _unwrap_payload(self, data: Any) -> Any:
        current = data
        for key in ["data", "result", "output", "response"]:
            if isinstance(current, dict) and key in current:
                nested = current.get(key)
                if isinstance(nested, (dict, list, str)):
                    current = nested
        return current

    def _find_first_string(self, data: Any, keys: List[str], recursive: bool = True) -> str:
        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)
                text = self._stringify_value(value)
                if text:
                    return text

            if recursive:
                for value in data.values():
                    found = self._find_first_string(value, keys, recursive=True)
                    if found:
                        return found
        elif recursive and isinstance(data, list):
            for item in data:
                found = self._find_first_string(item, keys, recursive=True)
                if found:
                    return found
        return ""

    def _find_first_list(self, data: Any, keys: List[str], recursive: bool = True) -> List[Any]:
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []

        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value

        if recursive:
            for value in data.values():
                found = self._find_first_list(value, keys, recursive=True)
                if found:
                    return found
        return []

    def _stringify_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = [self._stringify_value(item) for item in value]
            return "\n".join(part for part in parts if part).strip()
        if isinstance(value, dict):
            return ""
        return str(value).strip()

    def _build_basic_pdf_info(self, pdf_path: str) -> Dict[str, Any]:
        return {
            "total_pages": 0,
            "metadata": {},
            "file_size": os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0,
            "filename": os.path.basename(pdf_path),
        }

    def _empty_location(self) -> Dict[str, int]:
        return {"left": 0, "top": 0, "width": 0, "height": 0, "right": 0, "bottom": 0}

    def _get_error_result(self, error_message: str, pdf_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "success": False,
            "error": error_message,
            "pdf_info": pdf_info or {},
            "conversion_info": {"engine": "mineru", "image_paths": []},
            "ocr_results": [],
            "combined_results": {
                "text_items": [],
                "total_items": 0,
                "total_pages": 0,
                "total_processing_time": 0,
                "markdown": "",
                "raw_text": "",
            },
            "pages_summary": [],
            "processing_info": {
                "engine": "mineru",
                "model": self.model,
            },
        }


def create_mineru_processor(**kwargs):
    """创建 MinerU 处理器实例。"""
    return MinerUProcessor(**kwargs)
