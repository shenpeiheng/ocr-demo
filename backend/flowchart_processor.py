"""
流程图识别处理器。

将流程图图片交给视觉语言模型识别，并把模型输出归一化为固定表格字段。
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List


logger = logging.getLogger(__name__)

FLOWCHART_COLUMNS = ["流程", "流程说明", "流程ID", "流程描述", "操作方式", "部门"]

FLOWCHART_PROMPT = """
你是企业流程图识别专家。请识别图片中的泳道流程图，并输出可直接生成Excel的结构化数据。

识别目标：
1. 读取流程图标题、右上角流程编号、泳道部门、每个流程节点编号和节点文字。
2. 先读取图片中的图例/操作方式说明区域，建立“标识/logo -> 图例右侧文字”的映射，再逐个节点匹配节点旁边或节点内的标识/logo。
3. 部门字段必须来自节点所在泳道，例如销售部、工程部、工模部、成本部、PE/IE。
4. 流程字段填写整张流程图的流程编号，例如 1-1-1。
5. 流程说明填写整张流程图标题或流程名称，例如 项目启动创建流程。
6. 流程ID填写单个节点的完整编号，例如 1-1-1.1、1-1-1.2；如果图中节点只写 1、2、3，请用流程编号拼成完整ID。
7. 流程描述填写节点框内完整文字，保留中文、英文、编号和关键业务名词。
8. 只要节点框、菱形判断框、开始/结束框内有 1、2、3、4 或 1.、2.、3.、4.、1、2、3、4 等数字开头编号，就必须作为流程节点读取出来，即使该节点没有任何操作图标/标识。
9. 操作方式字段的唯一来源是图例中“匹配到的标识/logo右侧文字”。节点上的标识/logo匹配图例成功，就把图例右侧文字原样填入操作方式，不要改写、不要简繁转换。
10. 参考图例映射示例：纸张图标 -> 纸质文件和手工操作；邮件/电话类图标 -> 电邮沟通；BPCS logo -> BPCS和手工操作；ETOR logo -> ETOR系统和手工操作。
11. 如果某个节点没有明确对应的标识/logo，或标识/logo无法与图例匹配，操作方式必须留空。不要根据相邻节点、部门、流程描述、节点文字中的 BPCS/ETOR 字样或经验推断。
12. 连线箭头旁边的文字属于流转条件或分支条件，例如：同意、不同意、通过、不通过、Yes、No。不要把这些文字当作独立流程节点。
13. 如果能判断连线文字从哪个节点引出，请把条件合并到该节点的流程描述末尾，格式为：节点描述（流转条件：条件1 -> 目标节点；条件2 -> 目标节点）。例如：4.审批（流转条件：同意 -> 5.审批；不同意 -> 3.在BPCS中开领料单）。
14. 如果只能识别到连线文字但无法确定目标节点，也要保留在流程描述末尾，格式为：节点描述（流转条件：同意 / 不同意）。

只返回JSON，不要解释，不要Markdown代码块。格式必须为：
{
  "rows": [
    {
      "流程": "1-1-1",
      "流程说明": "项目启动创建流程",
      "流程ID": "1-1-1.1",
      "流程描述": "发送Project Confirmation Notification form",
      "操作方式": "纸质文件和手工操作",
      "部门": "销售部"
    }
  ]
}
""".strip()

FIELD_ALIASES = {
    "流程": ["流程", "流程编号", "流程代码", "flow", "process", "process_code"],
    "流程说明": ["流程说明", "流程名称", "流程名", "标题", "flow_name", "process_name"],
    "流程ID": ["流程ID", "流程id", "流程节点ID", "节点ID", "步骤ID", "id", "flow_id", "process_id", "step_id"],
    "流程描述": ["流程描述", "节点描述", "步骤描述", "描述", "内容", "text", "description", "step_description"],
    "操作方式": ["操作方式", "处理方式", "作业方式", "方式", "operation", "operation_method"],
    "部门": ["部门", "负责部门", "泳道", "dept", "department"],
}


def process_flowchart_images(image_entries: List[Dict[str, Any]], ocr_processor) -> Dict[str, Any]:
    """批量识别流程图图片。"""
    start_time = time.time()
    all_rows = []
    file_results = []

    for index, entry in enumerate(image_entries, 1):
        image_path = entry["path"]
        original_filename = entry.get("original_filename") or os.path.basename(image_path)
        logger.info("开始识别流程图 %s/%s: %s", index, len(image_entries), image_path)

        image_start = time.time()
        result = ocr_processor.process_image_with_engine(image_path, "openai_vl", FLOWCHART_PROMPT)
        image_time = round(time.time() - image_start, 2)

        if not result.get("success"):
            file_results.append(
                {
                    "success": False,
                    "filename": entry["filename"],
                    "original_filename": original_filename,
                    "image_url": f"/uploads/{entry['filename']}",
                    "rows": [],
                    "total_rows": 0,
                    "processing_time": image_time,
                    "error": result.get("error", "流程图识别失败"),
                }
            )
            continue

        raw_response = result.get("raw_response", "")
        rows = normalize_flowchart_rows(parse_flowchart_response(raw_response))
        for row in rows:
            row["来源图片"] = original_filename
            row["图片文件"] = entry["filename"]

        all_rows.extend(rows)
        file_results.append(
            {
                "success": True,
                "filename": entry["filename"],
                "original_filename": original_filename,
                "image_url": f"/uploads/{entry['filename']}",
                "rows": rows,
                "total_rows": len(rows),
                "processing_time": image_time,
                "image_info": result.get("image_info", {}),
                "model_input_info": result.get("model_input_info", {}),
                "raw_response_preview": raw_response[:500],
            }
        )

    successful_files = [item for item in file_results if item.get("success")]
    processing_time = round(time.time() - start_time, 2)
    departments = sorted({row.get("部门", "") for row in all_rows if row.get("部门")})
    flow_codes = sorted({row.get("流程", "") for row in all_rows if row.get("流程")})

    return {
        "success": bool(successful_files),
        "rows": all_rows,
        "total_rows": len(all_rows),
        "files": file_results,
        "stats": {
            "image_count": len(image_entries),
            "successful_images": len(successful_files),
            "flow_count": len(flow_codes),
            "department_count": len(departments),
            "processing_time": processing_time,
        },
        "processing_info": {
            "engine": "openai_vl",
            "prompt_type": "flowchart",
            "columns": FLOWCHART_COLUMNS,
        },
    }


def parse_flowchart_response(content: str) -> List[Dict[str, Any]]:
    """解析模型返回，支持JSON对象、JSON数组和Markdown表格。"""
    if not content or not content.strip():
        return []

    json_payload = _extract_json_payload(content)
    if json_payload is not None:
        return _flatten_json_payload(json_payload)

    return _parse_markdown_table(content)


def normalize_flowchart_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized_rows = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            continue

        row = {column: _get_first_value(raw_row, FIELD_ALIASES[column]) for column in FLOWCHART_COLUMNS}
        row = {key: _clean_cell(value) for key, value in row.items()}

        flow_id = row.get("流程ID", "")
        step_number = _extract_leading_step_number(row.get("流程描述", ""))
        if not flow_id and step_number:
            row["流程ID"] = f"{row['流程']}.{step_number}" if row.get("流程") else step_number
            flow_id = row["流程ID"]

        if not row.get("流程") and flow_id:
            match = re.match(r"^(\d+(?:-\d+)+)", flow_id)
            if match:
                row["流程"] = match.group(1)

        if row.get("流程") and flow_id and _is_short_step_id(flow_id):
            row["流程ID"] = f"{row['流程']}.{_extract_leading_step_number(flow_id)}"

        if any(row.values()):
            normalized_rows.append(row)

    return normalized_rows


def _extract_json_payload(content: str):
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_index = text.find(start_char)
        if start_index < 0:
            continue
        end_index = _find_balanced_end(text, start_index, start_char, end_char)
        if end_index < 0:
            continue
        try:
            return json.loads(text[start_index : end_index + 1])
        except json.JSONDecodeError:
            continue

    return None


def _find_balanced_end(text: str, start_index: int, start_char: str, end_char: str) -> int:
    depth = 0
    in_string = False
    escape = False
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == start_char:
            depth += 1
        elif char == end_char:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _flatten_json_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    common_values = {
        "流程": _get_first_value(payload, FIELD_ALIASES["流程"]),
        "流程说明": _get_first_value(payload, FIELD_ALIASES["流程说明"]),
    }

    for key in ["rows", "data", "items", "result", "results", "流程明细", "识别结果", "流程节点"]:
        value = payload.get(key)
        if isinstance(value, list):
            rows = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                merged = dict(common_values)
                merged.update(item)
                rows.append(merged)
            return rows

    if any(_get_first_value(payload, FIELD_ALIASES[column]) for column in FLOWCHART_COLUMNS):
        return [payload]

    return []


def _parse_markdown_table(content: str) -> List[Dict[str, str]]:
    table_lines = [line.strip() for line in content.splitlines() if "|" in line]
    if len(table_lines) < 2:
        return []

    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows = []
    for line in table_lines[1:]:
        if re.fullmatch(r"[\s|:\-]+", line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(dict(zip(headers, cells)))
    return rows


def _get_first_value(row: Dict[str, Any], keys: List[str]) -> str:
    lower_key_map = {str(key).strip().lower(): key for key in row.keys()}
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key])

        matched_key = lower_key_map.get(key.lower())
        if matched_key and row.get(matched_key) is not None:
            return str(row[matched_key])

    return ""


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _is_short_step_id(value: str) -> bool:
    return bool(_extract_leading_step_number(value)) and not re.search(r"\d-\d", str(value))


def _extract_leading_step_number(value: str) -> str:
    match = re.match(r"^\s*(\d{1,3})(?=[^\d-]|$)", str(value or ""))
    return match.group(1) if match else ""
