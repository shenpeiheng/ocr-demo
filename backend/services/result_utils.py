"""
OCR/PDF 结果处理公共函数。
"""

import base64
import io
import json
import os

import cv2
import numpy as np
from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFont


def draw_ocr_boxes(image_path, text_items):
    """在图片上绘制 OCR 框和序号标签。"""
    try:
        pil_img = Image.open(image_path).convert("RGB")
        img_width, img_height = pil_img.size
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(script_dir)
        project_root = os.path.dirname(backend_dir)
        font_paths = [
            os.path.join(project_root, "frontend", "static", "fonts", "NotoSansSC.ttf"),
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/yahei.ttf",
            "C:/Windows/Fonts/msyhbd.ttc",
        ]
        font_large = None
        font_small = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font_large = ImageFont.truetype(font_path, 20)
                    font_small = ImageFont.truetype(font_path, 16)
                    break
                except Exception:
                    continue
        if font_large is None:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        box_color_bgr = (0, 0, 255)
        label_bg_bgr = (255, 255, 255)
        label_text_color = (0, 0, 0)

        for index, item in enumerate(text_items):
            location = item.get("location", {})
            left = int(location.get("left", 0))
            top = int(location.get("top", 0))
            width = int(location.get("width", 50))
            height = int(location.get("height", 20))

            left = max(0, min(left, img_width - 1))
            top = max(0, min(top, img_height - 1))
            right = min(left + width, img_width)
            bottom = min(top + height, img_height)

            if right <= left or bottom <= top:
                continue

            cv2.rectangle(img_cv, (left, top), (right, bottom), box_color_bgr, 2)

            label = f"#{index + 1}"
            pil_tmp = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            draw_tmp = ImageDraw.Draw(pil_tmp)
            bbox = draw_tmp.textbbox((0, 0), label, font=font_small)
            label_w = bbox[2] - bbox[0] + 12
            label_h = bbox[3] - bbox[1] + 6

            label_x = left
            label_y = top - label_h - 2
            if label_y < 0:
                label_y = top + 2

            cv2.rectangle(
                img_cv,
                (label_x, label_y),
                (label_x + label_w, label_y + label_h),
                label_bg_bgr,
                -1,
            )
            cv2.rectangle(
                img_cv,
                (label_x, label_y),
                (label_x + label_w, label_y + label_h),
                box_color_bgr,
                1,
            )

            pil_tmp = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            draw_tmp = ImageDraw.Draw(pil_tmp)
            draw_tmp.text(
                (label_x + 6, label_y + 3),
                label,
                fill=label_text_color,
                font=font_small,
            )
            img_cv = cv2.cvtColor(np.array(pil_tmp), cv2.COLOR_RGB2BGR)

        final_img = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        output_buffer = io.BytesIO()
        final_img.save(output_buffer, format="JPEG", quality=95)
        img_base64 = base64.b64encode(output_buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_base64}"
    except Exception as exc:
        print(f"[draw_ocr_boxes] 错误: {exc}")
        import traceback

        traceback.print_exc()
        return None


def format_results_as_json(results):
    """将 OCR 结果格式化为结构化 JSON 字符串。"""
    try:
        text_items = results.get("text_items", [])
        image_info = results.get("image_info", {})
        analysis = results.get("analysis", {})

        formatted = {
            "识别统计": {
                "总识别项数": results.get("total_items", 0),
                "处理时间(秒)": results.get("processing_time", 0),
                "OCR引擎": results.get("ocr_engine", "unknown"),
                "图片宽度": image_info.get("width", 0),
                "图片高度": image_info.get("height", 0),
            },
            "类型分布": analysis.get("type_distribution", {}),
            "识别详情": [],
        }

        for index, item in enumerate(text_items):
            location = item.get("location", {})
            formatted["识别详情"].append(
                {
                    "序号": index + 1,
                    "内容": item.get("text", ""),
                    "类型": item.get("type", "text"),
                    "区域": item.get("region", ""),
                    "坐标": {
                        "left": location.get("left", 0),
                        "top": location.get("top", 0),
                        "width": location.get("width", 0),
                        "height": location.get("height", 0),
                    },
                    "置信度": item.get("confidence", 0),
                }
            )

        return json.dumps(formatted, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[format_results_as_json] 错误: {exc}")
        return json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2)


def generate_excel(results, excel_path):
    """生成图片 OCR 结果 Excel。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "OCR识别结果"

    headers = ["序号", "坐标X", "坐标Y", "宽度", "高度", "内容", "置信度", "类型"]
    if "region" in results.get("text_items", [{}])[0]:
        headers.append("区域")
    ws.append(headers)

    for index, item in enumerate(results.get("text_items", []), 1):
        location = item.get("location", {})
        row_data = [
            index,
            location.get("left", 0),
            location.get("top", 0),
            location.get("width", 0),
            location.get("height", 0),
            item.get("text", ""),
            item.get("confidence", 0),
            item.get("type", "text"),
        ]
        if "region" in item:
            row_data.append(item.get("region", ""))
        ws.append(row_data)

    _adjust_sheet_widths(wb)
    wb.save(excel_path)


def generate_pdf_excel(pdf_result, excel_path):
    """生成 PDF OCR 结果 Excel。"""
    wb = Workbook()

    ws_summary = wb.active
    ws_summary.title = "PDF处理汇总"

    pdf_info = pdf_result.get("pdf_info", {})
    processing_info = pdf_result.get("processing_info", {})
    combined_results = pdf_result.get("combined_results", {})

    ws_summary.append(["PDF文件信息", ""])
    ws_summary.append(["文件名", pdf_info.get("filename", "")])
    ws_summary.append(["总页数", pdf_info.get("total_pages", 0)])
    ws_summary.append(["文件大小", f"{pdf_info.get('file_size', 0)} 字节"])
    ws_summary.append([])
    ws_summary.append(["处理信息", ""])
    ws_summary.append(["DPI", processing_info.get("dpi", 200)])
    ws_summary.append(["最大处理页数", processing_info.get("max_pages", 10)])
    ws_summary.append(["实际处理页数", processing_info.get("actual_pages_processed", 0)])
    ws_summary.append([])
    ws_summary.append(["识别结果汇总", ""])
    ws_summary.append(["总识别项数", combined_results.get("total_items", 0)])
    ws_summary.append(["总处理时间", f"{combined_results.get('total_processing_time', 0)} 秒"])

    ws_pages = wb.create_sheet(title="页面汇总")
    ws_pages.append(["页码", "识别项数", "处理时间(秒)", "处理状态"])
    for page in pdf_result.get("pages_summary", []):
        ws_pages.append(
            [
                page.get("page_number", 0),
                page.get("total_items", 0),
                page.get("processing_time", 0),
                "成功" if page.get("success", False) else "失败",
            ]
        )

    ws_details = wb.create_sheet(title="详细识别结果")
    detail_headers = ["页码", "序号", "坐标X", "坐标Y", "宽度", "高度", "内容", "置信度", "类型"]
    if "region" in combined_results.get("text_items", [{}])[0]:
        detail_headers.append("区域")
    ws_details.append(detail_headers)

    for index, item in enumerate(combined_results.get("text_items", []), 1):
        location = item.get("location", {})
        row_data = [
            item.get("page", 1),
            index,
            location.get("left", 0),
            location.get("top", 0),
            location.get("width", 0),
            location.get("height", 0),
            item.get("text", ""),
            item.get("confidence", 0),
            item.get("type", "text"),
        ]
        if "region" in item:
            row_data.append(item.get("region", ""))
        ws_details.append(row_data)

    _adjust_sheet_widths(wb)
    wb.save(excel_path)


def _adjust_sheet_widths(workbook):
    for worksheet in workbook.worksheets:
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            worksheet.column_dimensions[column_letter].width = min(max_length + 2, 50)
