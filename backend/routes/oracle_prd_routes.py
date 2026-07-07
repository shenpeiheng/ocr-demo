"""
Oracle PRD 页面相关接口。
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from datetime import datetime
from functools import lru_cache
from html import escape as html_escape
from json import JSONDecoder
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List
from uuid import uuid4

import requests
from flask import Blueprint, Response, jsonify, request, send_file, stream_with_context

from config import Config

oracle_prd_bp = Blueprint("oracle_prd", __name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
ORACLE_PRD_DIR = ROOT_DIR / "frontend" / "oracle_prd"
DOCX_PATH = ORACLE_PRD_DIR / "AI开发需求-自动生成Oracle EBS Forms可交互原型及PRD文档.docx"
ZIP_PATH = ORACLE_PRD_DIR / "ebs-forms-design.zip"
EXTRACTED_SKILL_DIR = ORACLE_PRD_DIR / "ebs-forms-design"
EXPORTS_DIR = ORACLE_PRD_DIR / "exports"
EXAMPLE_HTML_PATH = ORACLE_PRD_DIR / "供应商对账功能_原型.html"


def _resolve_model(model_alias: str = "") -> str:
    """把前端传入的模型别名解析为真实模型 id，未知或缺省时回退到默认模型。"""
    return Config.resolve_llm_model(model_alias)


ALLOWED_EXTERNAL_SCRIPT_URLS = (
    "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js",
    "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js",
)
RUNTIME_HELPER_JS = r"""
(function () {
  function ensureToast() {
    var toast = document.getElementById('prototype-runtime-toast');
    if (toast) {
      return toast;
    }
    toast = document.createElement('div');
    toast.id = 'prototype-runtime-toast';
    toast.style.cssText = 'position:fixed;top:16px;right:16px;z-index:99999;max-width:420px;padding:10px 14px;background:rgba(33,37,41,.92);color:#fff;font:12px/1.6 "Microsoft YaHei",sans-serif;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.22);display:none;white-space:pre-wrap;';
    document.body.appendChild(toast);
    return toast;
  }

  function showMsg(message) {
    var toast = ensureToast();
    toast.textContent = message || '演示功能已触发';
    toast.style.display = 'block';
    window.clearTimeout(showMsg.__timer__);
    showMsg.__timer__ = window.setTimeout(function () {
      toast.style.display = 'none';
    }, 2600);
  }

  if (typeof window.showMsg !== 'function') {
    window.showMsg = showMsg;
  }

  [
    ['captureCurrentScreenshot', '当前原型未接入截图引擎，这里先保留演示入口。'],
    ['batchScreenshot', '批量截图为演示占位，导出目录后可继续接入真实能力。'],
    ['generateDesignDoc', 'PRD 生成为演示占位，请在当前页面继续补充业务规则。'],
    ['zoomPage', '缩放功能未定义，当前用演示提示代替。'],
    ['resetZoom', '缩放重置为演示占位。'],
    ['toggleFullscreen', '全屏操作已触发，若浏览器拦截请手动使用浏览器全屏。'],
    ['toggleFocus', '聚焦模式为演示占位。'],
    ['showHelp', '帮助面板为演示占位。'],
    ['toggleToolbar', '工具栏折叠功能未定义，当前用演示提示代替。']
  ].forEach(function (item) {
    if (typeof window[item[0]] !== 'function') {
      window[item[0]] = function () {
        window.showMsg(item[1]);
      };
    }
  });

  window.addEventListener('error', function (event) {
    if (!event || !event.message) {
      return;
    }
    window.showMsg('原型脚本提示：' + event.message);
    event.preventDefault();
  });

  window.addEventListener('unhandledrejection', function (event) {
    var reason = event && event.reason ? String(event.reason) : '未知 Promise 错误';
    window.showMsg('原型脚本提示：' + reason);
    event.preventDefault();
  });
})();
""".strip()


def _normalize_modelscope_chat_url(model_key: str = "") -> str:
    """根据模型 key 获取对应的 API URL，回退到全局配置。"""
    base_url = Config.resolve_llm_url(model_key)
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url.rstrip('/')}/chat/completions"


def _extract_docx_text(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path) as zf:
        xml_content = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    text = re.sub(r"</w:p>", "\n", xml_content)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _ensure_skill_extracted() -> Path:
    skill_file = EXTRACTED_SKILL_DIR / "SKILL.md"
    template_file = EXTRACTED_SKILL_DIR / "templates" / "basic-prototype.html"
    if skill_file.exists() and template_file.exists():
        return EXTRACTED_SKILL_DIR

    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(ORACLE_PRD_DIR)
    return EXTRACTED_SKILL_DIR


@lru_cache(maxsize=1)
def load_oracle_prd_bundle() -> Dict[str, Any]:
    if not DOCX_PATH.exists():
        raise FileNotFoundError(f"未找到需求文档: {DOCX_PATH}")
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"未找到 skill 压缩包: {ZIP_PATH}")

    skill_root = _ensure_skill_extracted()
    document_text = _extract_docx_text(DOCX_PATH)
    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8", errors="ignore")
    forms_spec_text = (skill_root / "references" / "forms_design_spec.md").read_text(encoding="utf-8", errors="ignore")
    toolbar_text = (skill_root / "references" / "global-toolbar.md").read_text(encoding="utf-8", errors="ignore")
    screenshot_text = (skill_root / "references" / "screenshot-feature.md").read_text(encoding="utf-8", errors="ignore")
    template_html = (skill_root / "templates" / "basic-prototype.html").read_text(encoding="utf-8", errors="ignore")

    example_html = ""
    if EXAMPLE_HTML_PATH.exists():
        example_html = EXAMPLE_HTML_PATH.read_text(encoding="utf-8", errors="ignore")
    else:
        examples_dir = skill_root / "examples"
        if examples_dir.exists():
            example_file = next((path for path in examples_dir.glob("*.html") if path.is_file()), None)
            if example_file:
                example_html = example_file.read_text(encoding="utf-8", errors="ignore")

    preview_html = example_html or template_html

    return {
        "document_title": "AI开发需求 - 自动生成Oracle EBS Form可交互原型及PRD文档",
        "document_text": document_text,
        "document_excerpt": document_text[:6000],
        "skill_text": skill_text,
        "skill_excerpt": skill_text[:6000],
        "forms_spec_excerpt": forms_spec_text[:5000],
        "toolbar_excerpt": toolbar_text[:3000],
        "screenshot_excerpt": screenshot_text[:5000],
        "template_excerpt": template_html[:4000],
        "example_html": example_html,
        "example_excerpt": (example_html or template_html)[:12000],
        "skill_root": str(skill_root),
        "preview_html": preview_html,
    }


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced_match:
        try:
            return json.loads(fenced_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_index = text.find("{")
    if brace_index >= 0:
        decoder = JSONDecoder()
        try:
            parsed, _ = decoder.raw_decode(text[brace_index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {}


def _sanitize_identifier(text: str, prefix: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(text or "").strip().lower())
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        value = prefix
    if not value.startswith(prefix):
        value = f"{prefix}-{value}"
    return value[:64]


def _build_text_block_html(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    lines = [html_escape(line.strip()) for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return ""
    return "".join(f"<p>{line}</p>" for line in lines[:12])


def _build_default_overview_content(analysis: Dict[str, Any], prototype_title: str) -> str:
    display_markdown = str(analysis.get("display_markdown", "") or "").strip()
    prototype_requirements = str(analysis.get("prototype_requirements", "") or "").strip()
    summary_html = _build_text_block_html(display_markdown) or "<p>请继续补充业务需求、关键字段和处理规则。</p>"
    requirement_html = _build_text_block_html(prototype_requirements) or "<p>当前尚未提炼出明确的页面约束，建议继续补充流程与状态规则。</p>"

    return f"""
<div class="overview-card">
  <div class="section-title">需求概览</div>
  <div class="summary-row">
    <div class="summary-item"><span>原型主题</span><strong>{html_escape(prototype_title)}</strong></div>
    <div class="summary-item"><span>当前阶段</span><strong>{html_escape(str(analysis.get("phase", "") or "prototype"))}</strong></div>
  </div>
</div>
<div class="overview-card">
  <div class="section-title">需求摘要</div>
  <div class="form-grid">
    <div class="form-item" style="grid-column: 1 / -1;">
      {summary_html}
    </div>
  </div>
</div>
<div class="overview-card">
  <div class="section-title">设计约束</div>
  <div class="form-grid">
    <div class="form-item" style="grid-column: 1 / -1;">
      {requirement_html}
    </div>
  </div>
</div>
""".strip()


def _build_default_help_html(analysis: Dict[str, Any], prototype_title: str) -> str:
    display_markdown = str(analysis.get("display_markdown", "") or "").strip()
    prototype_requirements = str(analysis.get("prototype_requirements", "") or "").strip()
    return f"""
<div style="font-size:10pt;line-height:1.8;">
  <p><b>{html_escape(prototype_title)}</b></p>
  <p>当前原型基于已确认需求自动生成，页面结构、按钮和导航均可继续迭代。</p>
  <p><b>需求摘要：</b></p>
  {_build_text_block_html(display_markdown) or '<p>暂无摘要。</p>'}
  <p><b>补充说明：</b></p>
  {_build_text_block_html(prototype_requirements) or '<p>暂无补充说明。</p>'}
</div>
""".strip()


def _normalize_prototype_blueprint(raw: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}

    prototype_title = str(
        raw.get("prototype_title")
        or raw.get("title")
        or raw.get("page_title")
        or analysis.get("display_title")
        or "Oracle EBS 原型"
    ).strip() or "Oracle EBS 原型"
    version_text = str(raw.get("version_text") or f"{prototype_title} v1.0").strip() or f"{prototype_title} v1.0"

    raw_panes = raw.get("panes") or raw.get("pages") or raw.get("tabs") or raw.get("screens") or []
    normalized_panes: List[Dict[str, str]] = []
    title_to_pane_id: Dict[str, str] = {}

    if isinstance(raw_panes, list):
        for index, pane in enumerate(raw_panes):
            if not isinstance(pane, dict):
                continue

            title = str(
                pane.get("title")
                or pane.get("label")
                or pane.get("name")
                or pane.get("pane_name")
                or f"功能页面{index + 1}"
            ).strip() or f"功能页面{index + 1}"

            raw_pane_id = str(
                pane.get("pane_id")
                or pane.get("id")
                or pane.get("tab_id")
                or pane.get("key")
                or ""
            ).strip()
            pane_id = raw_pane_id or _sanitize_identifier(title, "tab")
            if index == 0 and ("overview" in pane_id.lower() or "总览" in title or "概览" in title):
                pane_id = "tab-overview"

            content_html = str(
                pane.get("content_html")
                or pane.get("html")
                or pane.get("content")
                or pane.get("body_html")
                or ""
            ).strip()
            if not content_html:
                content_html = f"""
<div class="overview-card">
  <div class="section-title">{html_escape(title)}</div>
  <div class="form-grid">
    <div class="form-item" style="grid-column: 1 / -1;">
      {_build_text_block_html(pane.get("doc_desc") or pane.get("description") or pane.get("summary") or analysis.get("display_markdown") or '') or '<p>待补充页面内容。</p>'}
    </div>
  </div>
</div>
""".strip()

            doc_desc = str(
                pane.get("doc_desc")
                or pane.get("description")
                or pane.get("summary")
                or f"{title}功能说明"
            ).strip() or f"{title}功能说明"

            normalized_panes.append({
                "pane_id": pane_id,
                "title": title,
                "doc_desc": doc_desc,
                "content_html": content_html,
            })
            title_to_pane_id[title] = pane_id

    overview_pane = next((pane for pane in normalized_panes if pane.get("pane_id") == "tab-overview"), None)
    if not overview_pane:
        overview_title = str(
            (raw.get("root_item") or {}).get("title")
            or analysis.get("display_title")
            or f"{prototype_title}总览"
        ).strip() or f"{prototype_title}总览"
        overview_pane = {
            "pane_id": "tab-overview",
            "title": overview_title,
            "doc_desc": f"{overview_title}页面说明",
            "content_html": _build_default_overview_content(analysis, prototype_title),
        }
        normalized_panes.insert(0, overview_pane)

    raw_root_item = raw.get("root_item") or raw.get("root") or {}
    root_item = {
        "pane_id": "tab-overview",
        "label": str(raw_root_item.get("label") or "总览").strip() or "总览",
        "title": str(raw_root_item.get("title") or overview_pane.get("title") or f"{prototype_title}总览").strip() or f"{prototype_title}总览",
    }

    raw_groups = raw.get("groups") or raw.get("modules") or raw.get("nav_groups") or []
    normalized_groups: List[Dict[str, Any]] = []
    if isinstance(raw_groups, list):
        for group_index, group in enumerate(raw_groups):
            if not isinstance(group, dict):
                continue

            group_label = str(
                group.get("label")
                or group.get("title")
                or group.get("name")
                or f"功能分组{group_index + 1}"
            ).strip() or f"功能分组{group_index + 1}"
            group_id = str(group.get("group_id") or group.get("id") or "").strip() or _sanitize_identifier(group_label, "folder")

            raw_children = group.get("children") or group.get("items") or group.get("pages") or []
            normalized_children: List[Dict[str, str]] = []
            if isinstance(raw_children, list):
                for child_index, child in enumerate(raw_children):
                    if not isinstance(child, dict):
                        continue

                    child_title = str(
                        child.get("title")
                        or child.get("label")
                        or child.get("name")
                        or f"{group_label}页面{child_index + 1}"
                    ).strip() or f"{group_label}页面{child_index + 1}"
                    child_pane_id = str(
                        child.get("pane_id")
                        or child.get("id")
                        or child.get("tab_id")
                        or title_to_pane_id.get(child_title)
                        or _sanitize_identifier(child_title, "tab")
                    ).strip()
                    normalized_children.append({
                        "pane_id": child_pane_id,
                        "label": str(child.get("label") or child_title).strip() or child_title,
                        "title": child_title,
                        "doc_desc": str(child.get("doc_desc") or f"{child_title}功能说明").strip() or f"{child_title}功能说明",
                    })

            if normalized_children:
                normalized_groups.append({
                    "group_id": group_id,
                    "label": group_label,
                    "children": normalized_children,
                })

    if not normalized_groups:
        leaf_panes = [pane for pane in normalized_panes if pane.get("pane_id") != "tab-overview"]
        if leaf_panes:
            normalized_groups.append({
                "group_id": "folder-main",
                "label": "功能页面",
                "children": [
                    {
                        "pane_id": pane["pane_id"],
                        "label": pane["title"],
                        "title": pane["title"],
                        "doc_desc": pane["doc_desc"],
                    }
                    for pane in leaf_panes
                ],
            })

    help_html = str(raw.get("help_html") or raw.get("help") or "").strip() or _build_default_help_html(analysis, prototype_title)

    return {
        "prototype_title": prototype_title,
        "version_text": version_text,
        "root_item": root_item,
        "groups": normalized_groups,
        "panes": normalized_panes,
        "help_html": help_html,
    }


def _is_usable_blueprint(blueprint: Dict[str, Any]) -> bool:
    if not isinstance(blueprint, dict) or not blueprint:
        return False
    panes = blueprint.get("panes") or []
    root_item = blueprint.get("root_item") or {}
    if not panes or not root_item:
        return False
    return any(str(pane.get("pane_id", "")).strip() == "tab-overview" for pane in panes)


def _sanitize_fragment_html(fragment: str) -> str:
    text = (fragment or "").strip()
    if not text:
        return ""

    text = re.sub(r"<script\b.*?</script>", "", text, flags=re.S | re.I)
    text = re.sub(r"<style\b.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<(?:!DOCTYPE|html|head|body)\b.*?>", "", text, flags=re.S | re.I)
    text = re.sub(r"</(?:html|head|body)>", "", text, flags=re.S | re.I)
    text = re.sub(r"\s+on[a-zA-Z]+\s*=\s*\"[^\"]*\"", "", text)
    text = re.sub(r"\s+on[a-zA-Z]+\s*=\s*'[^']*'", "", text)
    return text.strip()


def _extract_html_block(source_html: str, css_class: str) -> str:
    match = re.search(
        rf"(<div class=\"{re.escape(css_class)}\">.*?</div>)",
        source_html or "",
        re.S | re.I,
    )
    return match.group(1).strip() if match else ""


def _extract_style_block(source_html: str) -> str:
    match = re.search(r"<style>(.*?)</style>", source_html or "", re.S | re.I)
    return match.group(1).strip() if match else ""


def _extract_icon_data_uri(source_html: str) -> str:
    match = re.search(r"(data:image/png;base64,[A-Za-z0-9+/=]+)", source_html or "")
    return match.group(1) if match else ""


def _extract_existing_prototype_context(existing_html: str) -> str:
    text = (existing_html or "").strip()
    if not text:
        return ""

    title_match = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    title = title_match.group(1).strip() if title_match else ""

    nav_match = re.search(r"<div class=\"nav-panel\">(.*?)</div>\s*</div>\s*<div class=\"view-panel\">", text, re.S | re.I)
    nav_excerpt = nav_match.group(1).strip()[:5000] if nav_match else ""

    content_start = text.find('<div class="view-content"')
    content_excerpt = ""
    if content_start >= 0:
        content_excerpt = text[content_start:content_start + 18000]
    else:
        content_excerpt = text[:18000]

    parts = []
    if title:
        parts.append(f"现有原型标题：{title}")
    if nav_excerpt:
        parts.append("现有原型导航片段：\n" + nav_excerpt)
    if content_excerpt:
        parts.append("现有原型内容片段：\n" + content_excerpt)
    return "\n\n".join(parts)


def _build_loaded_export_context(
    current_prototype_html: str = "",
    current_export_name: str = "",
    current_export_title: str = "",
    current_export_dir: str = "",
) -> str:
    parts = []
    if current_export_name:
        parts.append(f"当前已加载导出版本：{current_export_name}")
    if current_export_title:
        parts.append(f"当前已加载导出标题：{current_export_title}")
    if current_export_dir:
        parts.append(f"当前已加载导出目录：{current_export_dir}")

    prototype_context = _extract_existing_prototype_context(current_prototype_html)
    if prototype_context:
        parts.append(prototype_context)

    return "\n\n".join(parts)


def _build_analysis_system_prompt(bundle: Dict[str, Any], loaded_export_context: str = "") -> str:
    document_excerpt = bundle["document_text"][:9000]
    skill_excerpt = bundle["skill_text"][:9000]
    forms_spec_excerpt = bundle["forms_spec_excerpt"][:3500]
    toolbar_excerpt = bundle["toolbar_excerpt"][:1800]
    example_excerpt = bundle["example_excerpt"][:5000]
    loaded_export_section = loaded_export_context or "当前没有已加载的导出版本。"

    return f"""你是“Oracle EBS Forms 原型与 PRD 助手”。

你的工作目标：
1. 基于需求文档和 skill 约束，逐步澄清 Oracle EBS Forms 原型需求。
2. 严格按 skill 的引导方式工作：优先确认需求理解，不完整时一次只追问一个关键问题。
3. 明确告诉用户当前处于哪个阶段：需求理解 / 需求确认 / 原型设计 / PRD 设计。
4. 只有当需求足够明确，才开始给出原型结构建议或 PRD 大纲。
5. 严格遵循 skill 的引导式对话：如果用户还在描述需求或业务场景，就继续做需求澄清，不要抢先进入原型生成。
6. 后续如果进入 HTML 原型生成，必须以现有“供应商对账功能_原型.html”示例作为母版风格，不允许退化成简化模板。
7. 如果系统已提供“当前已加载导出版本”或“现有原型内容片段”，说明这些内容就是当前可直接修改的工作版本，不要把它当成无法访问的外部文件，不要要求用户再次粘贴文件内容。

回答规则：
- 使用中文。
- 不要冗长，不要泛泛而谈。
- 如果信息不足，一次只问一个最关键的问题。
- 如果用户已经给出完整需求，先总结理解，再请求用户确认。
- 只有在用户明确说“生成原型”、“输出 HTML”、“开始做原型”、“确认生成”、“开始生成”、“直接生成”、“生成文件”或同类指令时，才允许进入原型生成阶段。
- 如果用户只是提供案例、背景、功能点或回复你的问题，不要因为信息看起来足够就自动进入 prototype 阶段。
- 但如果用户已经明确下达“确认生成/开始生成/直接生成/生成文件”等执行指令，就不要继续停留在澄清阶段，必须进入原型生成链路。
- 当你判断下一步应进入原型生成时，不要把“已经生成完成”“正在生成中”“18个按钮已实现”这类执行结果写进 `reply`，因为真正的生成由后续独立接口执行；`reply` 只能表达“已进入生成步骤，请以右侧真实进度为准”。
- 本轮不要输出 prototype_html，不要输出大段 HTML，只负责输出结构化分析结果。

你必须严格输出 JSON，不要输出 Markdown 代码块，不要输出额外说明。
JSON schema:
{{
  "phase": "clarify|confirm|prototype|prd",
  "reply": "给左侧聊天窗口展示的回复",
  "display_title": "右侧展示区标题",
  "display_markdown": "右侧展示区内容，使用纯文本或 Markdown 风格文本",
  "should_generate_prototype": true,
  "prototype_requirements": "如果需要生成原型，这里用简明中文总结页面结构、交互重点、必须遵守的 Oracle EBS Forms 规范；否则为空字符串"
}}

以下是需求文档摘要：
{document_excerpt}

以下是 skill 摘要：
{skill_excerpt}

以下是 Oracle EBS Forms 设计规范摘要：
{forms_spec_excerpt}

以下是全局工具栏规范摘要：
{toolbar_excerpt}

以下是现有示例原型摘要（后续生成时必须高度贴合它的结构与交互壳子）：
{example_excerpt}

以下是当前已加载的导出版本上下文（若存在，后续修改必须以此为准）：
{loaded_export_section}
"""


def _build_html_generation_prompt(
    bundle: Dict[str, Any],
    analysis: Dict[str, Any],
    messages: List[Dict[str, str]],
    existing_prototype_html: str = "",
) -> str:
    document_excerpt = bundle["document_text"][:7000]
    skill_excerpt = bundle["skill_text"][:7000]
    forms_spec_excerpt = bundle["forms_spec_excerpt"][:3200]
    toolbar_excerpt = bundle["toolbar_excerpt"][:1600]
    screenshot_excerpt = bundle["screenshot_excerpt"][:2600]
    template_excerpt = bundle["template_excerpt"][:2200]
    example_html = bundle["example_html"] or ""
    example_excerpt = bundle["example_excerpt"][:12000]
    conversation_excerpt = "\n".join(
        f"{item['role']}: {item['content']}" for item in messages[-8:]
    )
    existing_prototype_context = _extract_existing_prototype_context(existing_prototype_html)

    example_instruction = (
        "以下提供了完整的示例原型 HTML。你必须以它为唯一母版进行改造："
        "保留它的整体 DOM 结构、样式体系、按钮体系、函数名、工具栏、导航壳子、模态框和截图/文档/聚焦相关能力；"
        "只根据当前业务需求替换标题、导航节点、各 tab 面板内容、示例数据、文案说明、帮助内容、docTabList 与 batchTabList 的业务项。"
        if example_html else
        "若完整示例不可用，则退回参考模板片段，但仍须尽量贴近 Oracle EBS Forms 参考风格。"
    )

    return f"""你现在只负责生成一个完整、可直接运行的单文件 HTML 原型，用于 Oracle EBS Forms 风格的“{analysis.get('display_title') or 'Oracle EBS 原型'}”。

必须遵守：
- 只输出 HTML 文本本身，不要输出 JSON，不要输出 Markdown 代码块，不要输出解释说明。
- 输出必须从 <!DOCTYPE html> 或 <html 开始，并以 </html> 结束。
- 必须是单文件 HTML，可直接放入 iframe srcdoc 预览。
- 风格严格参考 Oracle EBS Forms，包含左树右屏、多面板、工具栏、表单、表格、按钮等典型界面元素。
- 必须优先复用示例原型的结构与类名体系，不要自创一套新的简化布局，不要退回 basic-prototype 的极简壳子。
- 必须保留并实现这些区域：`.window`、`.global-toolbar`、`.main-container`、`.nav-panel`、`.view-panel`、`.view-title-bar`、`.view-content`、`.view-status-bar`、通用 modal、toast/focus overlay。
- 必须保留并定义这些函数名：`showMsg`、`toggleToolbar`、`switchPane`、`toggleFolder`、`captureCurrentScreenshot`、`batchScreenshot`、`generateDesignDoc`、`toggleFullscreen`、`toggleFocus`、`showHelp`。
- 必须保留顶部全局工具栏按钮，按钮数量、位置和用途要与示例原型一致；如果没有真实后端，也要保留演示逻辑，不能缺按钮。
- 必须保留右侧标题栏的最小化/最大化/关闭按钮，以及对应演示逻辑。
- 必须使用树形导航结构，不允许改成扁平按钮列表式导航。
- 页面内容不足一屏时正常显示；内容较多的区域要有内部滚动。
- 不依赖外部构建工具，不依赖需要联网才能工作的前端框架。
- 禁止加载任何 http/https 外链脚本、外链 CSS、外链图标、外链字体。
- 可以使用少量原生 JavaScript 实现页签切换、导航切换、按钮演示。
- 所有 onclick 或事件处理必须调用本文件内已定义的函数；没有真实后端时统一调用 showMsg('xxx') 做演示提示，不允许引用未定义函数。
- 按钮点击后宁可弹出演示提示，也不能报 JavaScript 错误。
- 视觉必须严格使用以下 token，不要自行改色：
  - 字体：宋体, SimSun, SimSun-ExtB, serif
  - 页面背景：#E8E8E8
  - 窗口背景：#F0F0F0
  - 画布区背景：#EAEEF2
  - 主标题栏背景：#2D82C3
  - 主标题栏底边：#1A6AAB
  - 工具栏背景：#E0E4E8
  - 按钮 hover：#D2E4F3
  - 通用边框：#A0A0A0
  - 聚焦边框：#2D6EB0
  - 标题栏控制按钮背景：#CFE3F5
  - 标题栏控制按钮文字/边框：#2D82C3
- 导航、按钮、标题栏、工具栏的尺寸尽量向参考模板对齐。
- 若示例原型与 skill/reference 有冲突，优先顺序为：截图/聚焦/工具栏等交互规范 > 示例原型壳子 > basic-prototype。
- 生成结果必须接近现有“供应商对账功能_原型.html”的完成度，而不是只输出一个骨架页面。
- 如果已经提供“现有已加载原型上下文”，表示用户是在现有版本上继续修改；你必须在当前版本基础上增量调整，而不是完全重做一个不相关的新页面。

本轮结构化分析结果：
phase: {analysis.get('phase', '')}
reply: {analysis.get('reply', '')}
display_title: {analysis.get('display_title', '')}
display_markdown:
{analysis.get('display_markdown', '')}

原型生成要求摘要：
{analysis.get('prototype_requirements', '')}

最近对话摘要：
{conversation_excerpt}

需求文档摘要：
{document_excerpt}

skill 摘要：
{skill_excerpt}

Oracle EBS Forms 设计规范摘要：
{forms_spec_excerpt}

全局工具栏规范摘要：
{toolbar_excerpt}

截图/文档/聚焦实现摘要：
{screenshot_excerpt}

示例原型摘要：
{example_excerpt}

参考模板片段：
{template_excerpt}

{example_instruction}

完整示例原型 HTML（请直接基于它改造，而不是另起炉灶）：
{example_html}

现有已加载原型上下文（如果为空则表示从零生成）：
{existing_prototype_context}
"""


def _build_prototype_blueprint_prompt(bundle: Dict[str, Any], analysis: Dict[str, Any], messages: List[Dict[str, str]], existing_prototype_html: str = "") -> str:
    document_excerpt = bundle["document_text"][:7000]
    skill_excerpt = bundle["skill_text"][:7000]
    forms_spec_excerpt = bundle["forms_spec_excerpt"][:3200]
    toolbar_excerpt = bundle["toolbar_excerpt"][:1600]
    screenshot_excerpt = bundle["screenshot_excerpt"][:2600]
    example_excerpt = bundle["example_excerpt"][:10000]
    conversation_excerpt = "\n".join(
        f"{item['role']}: {item['content']}" for item in messages[-8:]
    )
    existing_prototype_context = _extract_existing_prototype_context(existing_prototype_html)

    return f"""你现在不是输出完整 HTML，而是输出一个“原型蓝图 JSON”，随后后端会把这个 JSON 套入固定的 Oracle EBS 示例母版中。

目标：
- 页面最终必须使用现有示例原型的固定壳子、样式、工具栏、树导航、标题栏、模态框、截图/导出/聚焦能力。
- 你只负责给出业务内容结构：导航树、每个 pane 的标题、每个 pane 的内容片段、帮助文案、文档说明。
- 如果已经提供“现有原型内容片段”，表示用户正在现有版本上继续修改；你必须以该版本为当前基线做增量调整，而不是重做一个完全不同的页面。

强约束：
- 只输出 JSON 对象，不要输出 Markdown，不要输出解释说明。
- `content_html` 只能是“功能面板内部片段”，禁止输出 `<html>` `<head>` `<body>` `<script>` `<style>`。
- `content_html` 中必须尽量使用这些类名：`overview-card`、`flow-steps`、`flow-step`、`flow-step-box`、`flow-arrow`、`form-grid`、`form-item`、`toolbar`、`btn`、`btn-sm`、`section-title`、`scroll-table`、`data-table`、`summary-row`、`summary-item`、`status-tag`。
- `content_html` 里的按钮不要写复杂 onclick 逻辑，按钮只需要正常渲染；最终交互由固定母版脚本兜底。
- 导航必须是“一个根级总览 + 若干分组 + 分组下功能叶子”。
- pane 数量要和导航叶子数量一致，且必须包含 `tab-overview`。
- 帮助内容要贴合当前业务，而不是示例“供应商对账”。

JSON schema:
{{
  "prototype_title": "页面主标题，例如 采购需求管理系统",
  "version_text": "状态栏左侧版本文本，例如 采购需求管理系统 v1.0",
  "root_item": {{
    "pane_id": "tab-overview",
    "label": "📋 总览",
    "title": "采购需求管理总览"
  }},
  "groups": [
    {{
      "group_id": "folder-apply",
      "label": "📝 申请管理",
      "children": [
        {{
          "pane_id": "tab-apply",
          "label": "需求申请单",
          "title": "需求申请单",
          "doc_desc": "用于文档导出的简短说明"
        }}
      ]
    }}
  ],
  "panes": [
    {{
      "pane_id": "tab-overview",
      "title": "采购需求管理总览",
      "doc_desc": "系统总览页面说明",
      "content_html": "<div class=\\"overview-card\\">...</div>"
    }}
  ],
  "help_html": "<div style=\\"font-size:10pt;line-height:1.8;\\">...</div>"
}}

当前结构化分析结果：
phase: {analysis.get('phase', '')}
reply: {analysis.get('reply', '')}
display_title: {analysis.get('display_title', '')}
display_markdown:
{analysis.get('display_markdown', '')}

原型生成要求摘要：
{analysis.get('prototype_requirements', '')}

最近对话摘要：
{conversation_excerpt}

需求文档摘要：
{document_excerpt}

skill 摘要：
{skill_excerpt}

Oracle EBS Forms 设计规范摘要：
{forms_spec_excerpt}

全局工具栏规范摘要：
{toolbar_excerpt}

截图/文档/聚焦实现摘要：
{screenshot_excerpt}

示例原型摘要：
{example_excerpt}

现有已加载原型上下文（如果为空则表示从零生成）：
{existing_prototype_context}
"""


def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in messages[-12:]:
        role = item.get("role", "user")
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _request_modelscope_completion(messages: List[Dict[str, str]], max_tokens: int = 4800, model: str = "") -> Dict[str, Any]:
    api_key = Config.resolve_llm_key(model)
    response = requests.post(
        _normalize_modelscope_chat_url(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _resolve_model(model),
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        },
        timeout=90,
    )

    if response.status_code != 200:
        raise RuntimeError(f"ModelScope 调用失败: {response.status_code} {response.text[:1000]}")

    data = response.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return {
        "content": message.get("content", "") or "",
        "finish_reason": choice.get("finish_reason", "") or "",
    }


def _request_modelscope_completion_with_error_handling(messages: List[Dict[str, str]], max_tokens: int = 4800, timeout_seconds: int = 90, model: str = "") -> Dict[str, Any]:
    try:
        api_key = Config.resolve_llm_key(model)
        response = requests.post(
            _normalize_modelscope_chat_url(model),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _resolve_model(model),
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": max_tokens,
            },
            timeout=timeout_seconds,
        )
    except requests.exceptions.ReadTimeout as exc:
        raise RuntimeError(f"ModelScope 响应超时（{timeout_seconds}秒），请缩小本次生成范围或重试。") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"ModelScope 网络请求失败: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(f"ModelScope 调用失败: {response.status_code} {response.text[:1000]}")

    data = response.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return {
        "content": message.get("content", "") or "",
        "finish_reason": choice.get("finish_reason", "") or "",
    }


def _iter_modelscope_stream_with_error_handling(
    messages: List[Dict[str, str]],
    max_tokens: int = 4800,
    timeout_seconds: int = 90,
    model: str = "",
) -> Iterator[Dict[str, Any]]:
    response = None
    try:
        api_key = Config.resolve_llm_key(model)
        response = requests.post(
            _normalize_modelscope_chat_url(model),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _resolve_model(model),
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "stream": True,
            },
            timeout=timeout_seconds,
            stream=True,
        )
    except requests.exceptions.ReadTimeout as exc:
        raise RuntimeError(f"ModelScope 响应超时（{timeout_seconds}秒），请缩小本次生成范围或重试。") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"ModelScope 网络请求失败: {exc}") from exc

    if response.status_code != 200:
        text = response.text[:1000]
        response.close()
        raise RuntimeError(f"ModelScope 调用失败: {response.status_code} {text}")

    try:
        response.encoding = "utf-8"
        for raw_line in response.iter_lines(decode_unicode=False):
            if not raw_line:
                continue

            line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, bytes) else str(raw_line)
            if not line.startswith("data:"):
                continue

            payload_text = line[5:].strip()
            if not payload_text or payload_text == "[DONE]":
                continue

            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                continue

            choice = (payload.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            message = choice.get("message") or {}
            finish_reason = choice.get("finish_reason", "") or ""

            content = delta.get("content")
            if content is None:
                content = message.get("content", "") or ""

            yield {
                "content": str(content or ""),
                "finish_reason": finish_reason,
                "raw": payload,
            }
    finally:
        response.close()


def _sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _extract_partial_json_string_field(raw_text: str, field_name: str) -> str:
    text = str(raw_text or "")
    marker = f'"{field_name}"'
    start = text.find(marker)
    if start < 0:
        return ""

    colon_index = text.find(":", start + len(marker))
    if colon_index < 0:
        return ""

    quote_index = colon_index + 1
    while quote_index < len(text) and text[quote_index].isspace():
        quote_index += 1
    if quote_index >= len(text) or text[quote_index] != '"':
        return ""

    chars: List[str] = []
    index = quote_index + 1
    while index < len(text):
        char = text[index]
        if char == '"':
            return "".join(chars)
        if char != "\\":
            chars.append(char)
            index += 1
            continue

        if index + 1 >= len(text):
            break

        next_char = text[index + 1]
        if next_char == "u":
            hex_text = text[index + 2:index + 6]
            if len(hex_text) < 4 or not re.fullmatch(r"[0-9a-fA-F]{4}", hex_text):
                break
            chars.append(chr(int(hex_text, 16)))
            index += 6
            continue

        chars.append({
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }.get(next_char, next_char))
        index += 2

    return "".join(chars)


def _finalize_analysis_payload(
    payload_messages: List[Dict[str, str]],
    normalized_messages: List[Dict[str, str]],
    content: str,
    finish_reason: str,
    model: str = "",
) -> Dict[str, Any]:
    parsed = _extract_json_object(content)

    continuation_attempts = 0
    while continuation_attempts < 2 and (finish_reason == "length" or not parsed):
        continuation_attempts += 1
        continuation_messages = list(payload_messages)
        continuation_messages.append({"role": "assistant", "content": content})
        continuation_messages.append({
            "role": "user",
            "content": (
                "你上一条输出被截断或 JSON 不完整。"
                "请从中断处继续输出剩余 JSON 内容，只输出剩余文本，不要重复已经输出的部分。"
            ),
        })
        continuation = _request_modelscope_completion_with_error_handling(continuation_messages, max_tokens=2200, timeout_seconds=45, model=model)
        content += continuation["content"]
        finish_reason = continuation["finish_reason"]
        parsed = _extract_json_object(content)

    reply = parsed.get("reply") or content or "已收到需求，请继续。"
    display_title = parsed.get("display_title") or "AI 输出"
    display_markdown = parsed.get("display_markdown") or reply
    phase = parsed.get("phase") or "clarify"
    should_generate_prototype = _needs_prototype_generation(parsed, normalized_messages)

    if should_generate_prototype:
        reply = "已进入原型生成步骤。请以右侧“原型生成状态”和预览区实际结果为准。"

    return {
        "success": True,
        "phase": phase,
        "reply": reply,
        "display_title": display_title,
        "display_markdown": display_markdown,
        "prototype_html": "",
        "prototype_requirements": parsed.get("prototype_requirements") or "",
        "should_generate_prototype": should_generate_prototype,
        "model": _resolve_model(model),
    }


def _extract_html_document(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return ""

    fenced_match = re.search(r"```(?:html)?\s*(<!DOCTYPE html.*?</html>|<html.*?</html>)\s*```", text, re.S | re.I)
    if fenced_match:
        return fenced_match.group(1).strip()

    html_match = re.search(r"(<!DOCTYPE html.*?</html>|<html.*?</html>)", text, re.S | re.I)
    if html_match:
        return html_match.group(1).strip()

    if text.lower().startswith("<!doctype html") or text.lower().startswith("<html"):
        return text

    return ""


def _extract_best_html_document(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return ""

    start_candidates = []
    for pattern in (r"<!DOCTYPE html", r"<html\b"):
        start_candidates.extend(match.start() for match in re.finditer(pattern, text, re.I))
    start_candidates = sorted(set(start_candidates))

    end_matches = list(re.finditer(r"</html>", text, re.I))
    if not start_candidates or not end_matches:
        return _extract_html_document(text)

    first_start = start_candidates[0]
    last_end = end_matches[-1].end()
    outer_candidate = text[first_start:last_end].strip()
    if re.search(r"<head\b", outer_candidate, re.I) and re.search(r"<body\b", outer_candidate, re.I):
        return outer_candidate

    return _extract_html_document(text)


def _request_prototype_blueprint(bundle: Dict[str, Any], analysis: Dict[str, Any], messages: List[Dict[str, str]], existing_prototype_html: str = "", model: str = "") -> Dict[str, Any]:
    payload_messages = [
        {"role": "system", "content": _build_prototype_blueprint_prompt(bundle, analysis, messages, existing_prototype_html)}
    ]
    completion = _request_modelscope_completion_with_error_handling(payload_messages, max_tokens=6000, timeout_seconds=180, model=model)
    content = completion["content"]
    finish_reason = completion["finish_reason"]
    parsed = _extract_json_object(content)

    continuation_attempts = 0
    while continuation_attempts < 2 and (finish_reason == "length" or not parsed):
        continuation_attempts += 1
        continuation_messages = list(payload_messages)
        continuation_messages.append({"role": "assistant", "content": content})
        continuation_messages.append({
            "role": "user",
            "content": (
                "你上一条 JSON 被截断或不完整。"
                "请从中断处继续输出剩余 JSON 内容，只输出剩余文本，不要重复已经输出的部分。"
            ),
        })
        continuation = _request_modelscope_completion_with_error_handling(continuation_messages, max_tokens=6000, timeout_seconds=180, model=model)
        content += continuation["content"]
        finish_reason = continuation["finish_reason"]
        parsed = _extract_json_object(content)

    return _normalize_prototype_blueprint(parsed, analysis)


def _request_full_prototype_html(
    bundle: Dict[str, Any],
    analysis: Dict[str, Any],
    messages: List[Dict[str, str]],
    existing_prototype_html: str = "",
    model: str = "",
) -> str:
    payload_messages = [
        {
            "role": "system",
            "content": _build_html_generation_prompt(bundle, analysis, messages, existing_prototype_html),
        }
    ]
    completion = _request_modelscope_completion_with_error_handling(payload_messages, max_tokens=7000, timeout_seconds=180, model=model)
    content = completion["content"]
    finish_reason = completion["finish_reason"]
    html = _extract_html_document(content)

    continuation_attempts = 0
    while continuation_attempts < 2 and (finish_reason == "length" or not html):
        continuation_attempts += 1
        continuation_messages = list(payload_messages)
        continuation_messages.append({"role": "assistant", "content": content})
        continuation_messages.append({
            "role": "user",
            "content": (
                "你上一条 HTML 被截断、不完整或前面混入了说明文字。"
                "请继续补齐剩余 HTML；如果已经输出完整，请重新仅输出完整 HTML 文本，不要附加说明。"
            ),
        })
        continuation = _request_modelscope_completion_with_error_handling(continuation_messages, max_tokens=7000, timeout_seconds=180, model=model)
        content += continuation["content"]
        finish_reason = continuation["finish_reason"]
        html = _extract_html_document(content)

    return _normalize_generated_prototype_html(html)


def _build_navigation_html(spec: Dict[str, Any]) -> str:
    root_item = spec.get("root_item") or {}
    groups = spec.get("groups") or []

    root_pane_id = root_item.get("pane_id", "tab-overview")
    root_label = root_item.get("label", "📋 总览")
    root_title = root_item.get("title", "系统总览")

    parts = [
        '<div class="tree-root-item active" '
        f'onclick="switchPane(this,\'{root_pane_id}\',\'{root_title}\')">{root_label}</div>'
    ]

    for group in groups:
        group_id = group.get("group_id", f"folder-{uuid4().hex[:6]}")
        group_label = group.get("label", "📁 功能分组")
        children = group.get("children") or []
        child_html = []
        for child in children:
            pane_id = child.get("pane_id", f"tab-{uuid4().hex[:6]}")
            nav_label = child.get("label", child.get("title", "功能页面"))
            title = child.get("title", nav_label)
            child_html.append(
                '<div class="tree-leaf" '
                f'onclick="switchPane(this,\'{pane_id}\',\'{title}\')">{nav_label}</div>'
            )

        parts.append(
            f'<div class="tree-folder open" id="{group_id}">'
            f'<div class="tree-folder-header" onclick="toggleFolder(\'{group_id}\')">'
            '<span class="tree-folder-toggle">−</span>'
            f'<span>{group_label}</span>'
            '</div>'
            f'<div class="tree-folder-children">{"".join(child_html)}</div>'
            '</div>'
        )

    return "".join(parts)


def _build_panes_html(spec: Dict[str, Any]) -> str:
    panes = list(spec.get("panes") or [])
    panes.sort(key=lambda pane: 0 if str(pane.get("pane_id", "")).strip() == "tab-overview" else 1)
    parts = []
    for index, pane in enumerate(panes):
        pane_id = pane.get("pane_id", f"tab-{index}")
        content_html = _sanitize_fragment_html(pane.get("content_html", ""))
        active_class = " active" if index == 0 else ""
        parts.append(f'<div class="tab-pane{active_class}" id="{pane_id}">{content_html}</div>')
    return "".join(parts)


def _build_prototype_shell_html(bundle: Dict[str, Any], spec: Dict[str, Any]) -> str:
    example_html = bundle.get("example_html") or ""
    style_block = _extract_style_block(example_html) or _extract_style_block(bundle.get("template_excerpt", ""))
    icon_data_uri = _extract_icon_data_uri(example_html)

    prototype_title = str(spec.get("prototype_title", "Oracle EBS 原型")).strip() or "Oracle EBS 原型"
    version_text = str(spec.get("version_text", f"{prototype_title} v1.0")).strip() or f"{prototype_title} v1.0"
    root_item = spec.get("root_item") or {}
    initial_title = root_item.get("title", prototype_title)
    navigation_html = _build_navigation_html(spec)
    panes_html = _build_panes_html(spec)
    help_html = _sanitize_fragment_html(spec.get("help_html", ""))

    pane_docs = []
    for pane in spec.get("panes") or []:
        pane_id = str(pane.get("pane_id", "")).strip()
        title = str(pane.get("title", "")).strip()
        doc_desc = str(pane.get("doc_desc", "")).strip()
        if pane_id and title:
            pane_docs.append({"tabId": pane_id, "title": title, "desc": doc_desc or f"{title}功能说明"})

    batch_tabs_json = json.dumps(
        [{"tabId": item["tabId"], "title": item["title"]} for item in pane_docs],
        ensure_ascii=False,
    )
    doc_tabs_json = json.dumps(pane_docs, ensure_ascii=False)
    help_html_json = json.dumps(help_html, ensure_ascii=False)
    prototype_title_json = json.dumps(prototype_title, ensure_ascii=False)
    version_text_json = json.dumps(version_text, ensure_ascii=False)

    favicon_link = (
        f'<link rel="icon" type="image/png" href="{icon_data_uri}">' if icon_data_uri else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{prototype_title} - 功能原型</title>
{favicon_link}
<script src="{ALLOWED_EXTERNAL_SCRIPT_URLS[0]}"></script>
<script src="{ALLOWED_EXTERNAL_SCRIPT_URLS[1]}"></script>
<style>
{style_block}
</style>
</head>
<body>
<div class="focus-overlay" id="focusOverlay"></div>

<div class="window">
<div class="global-toolbar">
  <span class="tb-label">🔧 工具</span>
  <button class="tb-btn" onclick="captureCurrentScreenshot()">📸 功能截图</button>
  <button class="tb-btn" onclick="batchScreenshot()">📚 批量截图</button>
  <button class="tb-btn" onclick="generateDesignDoc()">📝 生成功能文档</button>
  <span class="tb-divider"></span>
  <button class="tb-btn" onclick="zoomPage(1.1)">🔍 放大</button>
  <button class="tb-btn" onclick="zoomPage(0.9)">🔍 缩小</button>
  <button class="tb-btn" onclick="resetZoom()">↺ 重置</button>
  <span class="tb-divider"></span>
  <button class="tb-btn" onclick="toggleFullscreen()">⛶ 全屏</button>
  <button class="tb-btn" onclick="toggleFocus()">🎯 聚焦</button>
  <span class="tb-divider"></span>
  <button class="tb-btn" onclick="showHelp()">❓ 帮助</button>
  <span style="flex:1;"></span>
  <button class="tb-btn tb-toggle" onclick="toggleToolbar()" title="折叠/展开工具栏">▲</button>
</div>

<div class="main-container">
  <div class="nav-panel">
    <div class="nav-title">功能导航</div>
    <div class="nav-tree">{navigation_html}</div>
  </div>

  <div class="view-panel">
    <div class="view-title-bar">
      <div class="view-title-left">
        <span class="view-title-icon"></span>
        <span id="viewTitleText">{initial_title}</span>
      </div>
      <div class="view-controls">
        <button onclick="showMsg('最小化面板')">_</button>
        <button onclick="showMsg('最大化面板')">□</button>
        <button onclick="showMsg('关闭面板')">×</button>
      </div>
    </div>

    <div class="view-content" id="prototypeViewContent">
      {panes_html}
    </div>

    <div class="view-status-bar">
      <span class="view-status-left">{version_text}</span>
      <span class="view-status-right" id="statusRight">就绪</span>
    </div>
  </div>
</div>
</div>

<div class="modal-overlay" id="modalGeneric">
  <div class="modal-box">
    <div class="modal-title">
      <span id="modalGenTitle">详情</span>
      <button class="modal-close" onclick="closeModal('modalGeneric')">×</button>
    </div>
    <div class="modal-body" id="modalGenBody"></div>
    <div class="modal-footer">
      <button class="btn" onclick="closeModal('modalGeneric')">关闭</button>
    </div>
  </div>
</div>

<div class="msg-toast" id="msgToast"></div>

<script>
const PROTOTYPE_TITLE = {prototype_title_json};
const PROTOTYPE_VERSION_TEXT = {version_text_json};
const HELP_HTML = {help_html_json};
const batchTabList = {batch_tabs_json};
const docTabList = {doc_tabs_json};
let currentZoom = 1;
let toolbarCollapsed = false;
let focusMode = false;
let msgTimer = null;
let docCaptureRunning = false;

function closeModal(id) {{
  document.getElementById(id).classList.remove('open');
}}

function showModal(id) {{
  document.getElementById(id).classList.add('open');
}}

function showMsg(msg) {{
  const t = document.getElementById('msgToast');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(msgTimer);
  msgTimer = setTimeout(() => {{
    t.style.display = 'none';
  }}, 2500);
}}

function escapeHtml(text) {{
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}}

function getActivePane() {{
  return document.querySelector('.tab-pane.active') || document.querySelector('.view-content');
}}

function getPrimaryTable(scope) {{
  const root = scope || getActivePane() || document;
  return root.querySelector('.scroll-table, .data-table, table');
}}

function getSelectedRow(scope) {{
  const root = scope || getActivePane() || document;
  return root.querySelector('.scroll-table tbody tr.selected, .data-table tbody tr.selected, table tbody tr.selected');
}}

function summarizeRow(row) {{
  if (!row || !row.cells) {{
    return '未选择记录';
  }}
  const parts = [];
  Array.from(row.cells).forEach(function(cell) {{
    if (parts.length >= 4) {{
      return;
    }}
    const text = (cell.textContent || '').replace(/\\s+/g, ' ').trim();
    if (text) {{
      parts.push(text);
    }}
  }});
  return parts.join(' / ') || '未选择记录';
}}

function openGenericActionModal(title, html) {{
  document.getElementById('modalGenTitle').textContent = title;
  document.getElementById('modalGenBody').innerHTML = html;
  showModal('modalGeneric');
}}

function getCandidateFieldLabels(btn) {{
  const table = getPrimaryTable(btn.closest('.tab-pane') || document);
  if (table) {{
    const headers = Array.from(table.querySelectorAll('thead th')).map(function(th) {{
      return (th.textContent || '').replace(/\\s+/g, ' ').trim();
    }}).filter(function(text) {{
      return text && text !== '操作' && text !== '选择';
    }});
    if (headers.length) {{
      return headers.slice(0, 4);
    }}
  }}
  return ['编码', '名称', '说明', '状态'];
}}

function buildGeneratedFormHtml(btn, actionLabel) {{
  const labels = getCandidateFieldLabels(btn);
  const items = labels.map(function(label, index) {{
    const placeholder = label.indexOf('状态') >= 0 ? '待处理' : ('请输入' + label);
    return '<div class="form-item" style="grid-column:' + (index > 1 ? '1 / -1' : 'auto') + ';">' +
      '<label>' + escapeHtml(label) + '</label>' +
      '<input type="text" class="c2-form-input" data-label="' + escapeHtml(label) + '" placeholder="' + escapeHtml(placeholder) + '">' +
      '</div>';
  }}).join('');
  return '' +
    '<div style="font-size:10pt;line-height:1.8;">' +
      '<p>请填写' + escapeHtml(actionLabel) + '所需信息：</p>' +
      '<div class="form-grid">' + items + '</div>' +
      '<div class="toolbar" style="justify-content:flex-end;margin-top:12px;">' +
        '<button class="btn btn-primary" onclick="submitGeneratedForm(\\'' + escapeHtml(actionLabel) + '\\')">确定</button>' +
        '<button class="btn" onclick="closeModal(\\'modalGeneric\\')">取消</button>' +
      '</div>' +
    '</div>';
}}

function insertGeneratedRow(actionLabel) {{
  const table = getPrimaryTable();
  if (!table) {{
    return false;
  }}
  const tbody = table.querySelector('tbody');
  const headerCells = Array.from(table.querySelectorAll('thead th'));
  if (!tbody || !headerCells.length) {{
    return false;
  }}

  const values = Array.from(document.querySelectorAll('#modalGenBody .c2-form-input')).map(function(input) {{
    return (input.value || '').trim();
  }});
  const row = document.createElement('tr');

  headerCells.forEach(function(th, index) {{
    const td = document.createElement('td');
    const headerText = (th.textContent || '').replace(/\\s+/g, ' ').trim();
    const value = values[index] || '';
    if (headerText === '选择') {{
      td.innerHTML = '<input type="checkbox">';
    }} else if (headerText === '操作') {{
      td.innerHTML = '<button class="btn btn-sm">查看</button>';
    }} else if (headerText.indexOf('状态') >= 0) {{
      td.innerHTML = '<span class="status-tag status-pending">' + escapeHtml(value || '待处理') + '</span>';
    }} else {{
      td.textContent = value || ('新' + headerText);
    }}
    row.appendChild(td);
  }});

  tbody.prepend(row);
  row.addEventListener('click', function() {{
    selectTr(row);
  }});
  selectTr(row);
  return true;
}}

function submitGeneratedForm(actionLabel) {{
  const inputs = Array.from(document.querySelectorAll('#modalGenBody .c2-form-input'));
  const missing = inputs.find(function(input) {{
    return !(input.value || '').trim();
  }});
  if (missing) {{
    showMsg('请先填写：' + (missing.getAttribute('data-label') || '必填项'));
    return;
  }}
  closeModal('modalGeneric');
  if (insertGeneratedRow(actionLabel)) {{
    showMsg(actionLabel + '成功，已写入当前列表');
  }} else {{
    showMsg(actionLabel + '成功');
  }}
}}

function confirmDeleteSelected() {{
  const row = getSelectedRow();
  if (!row) {{
    showMsg('请先选择一条记录');
    return;
  }}
  row.remove();
  closeModal('modalGeneric');
  showMsg('删除成功');
}}

function updateSelectedRowStatus(text, className) {{
  const row = getSelectedRow();
  if (!row) {{
    return false;
  }}
  const tag = row.querySelector('.status-tag');
  if (tag) {{
    tag.className = 'status-tag ' + className;
    tag.textContent = text;
    return true;
  }}
  const statusCell = Array.from(row.cells).find(function(cell) {{
    return /状态|审批|处理/.test(cell.textContent || '');
  }});
  if (statusCell) {{
    statusCell.textContent = text;
    return true;
  }}
  return false;
}}

function submitApproval(decision) {{
  const opinionInput = document.getElementById('c2ApprovalOpinion');
  const opinion = opinionInput ? (opinionInput.value || '').trim() : '';
  if (decision === 'reject' && !opinion) {{
    showMsg('请填写审批意见');
    return;
  }}
  closeModal('modalGeneric');
  if (decision === 'approve') {{
    updateSelectedRowStatus('审批中', 'status-running');
    showMsg('已提交审批');
  }} else {{
    updateSelectedRowStatus('已驳回', 'status-exception');
    showMsg('已退回并记录审批意见');
  }}
}}

let pendingLovTarget = null;

function chooseLovValue(value) {{
  if (!pendingLovTarget) {{
    closeModal('modalGeneric');
    return;
  }}
  if (pendingLovTarget.tagName === 'SELECT') {{
    const option = Array.from(pendingLovTarget.options).find(function(item) {{
      return item.text === value || item.value === value;
    }});
    if (option) {{
      pendingLovTarget.value = option.value;
    }}
  }} else {{
    pendingLovTarget.value = value;
  }}
  closeModal('modalGeneric');
  showMsg('已选择：' + value);
}}

function openLovDialog(btn) {{
  pendingLovTarget = btn.parentElement ? btn.parentElement.querySelector('input, select, textarea') : null;
  const options = ['001-标准值', '002-业务值', '003-示例值', '004-测试值'];
  const html = '' +
    '<div style="font-size:10pt;line-height:1.8;">' +
      '<p>请选择一条 LOV 记录：</p>' +
      '<div class="scroll-table"><table class="data-table"><thead><tr><th>编码</th><th>名称</th><th>操作</th></tr></thead><tbody>' +
      options.map(function(item) {{
        const name = item.split('-')[1] || item;
        return '<tr><td>' + escapeHtml(item.split('-')[0]) + '</td><td>' + escapeHtml(name) + '</td><td><button class="btn btn-sm" onclick="chooseLovValue(\\'' + escapeHtml(item) + '\\')">选择</button></td></tr>';
      }}).join('') +
      '</tbody></table></div>' +
    '</div>';
  openGenericActionModal('LOV 选择', html);
}}

function handleGeneratedButtonAction(btn) {{
  const label = (btn.textContent || '').replace(/\\s+/g, ' ').trim();
  if (!label) {{
    showMsg('按钮已触发');
    return;
  }}

  if (label === '⋯' || label.indexOf('LOV') >= 0 || label.indexOf('选择') >= 0) {{
    openLovDialog(btn);
    return;
  }}
  if (label.indexOf('重置') >= 0) {{
    resetForm(btn);
    return;
  }}
  if (label.indexOf('查询') >= 0 || label.indexOf('刷新') >= 0 || label.indexOf('检索') >= 0) {{
    openGenericActionModal(label, '<div style="font-size:10pt;line-height:1.8;"><p>已按当前条件执行' + escapeHtml(label) + '。</p><p>当前原型会保留查询表单与列表联动入口，便于后续继续细化真实规则。</p></div>');
    return;
  }}
  if (label.indexOf('新增') >= 0 || label.indexOf('新建') >= 0 || label.indexOf('创建') >= 0) {{
    openGenericActionModal(label, buildGeneratedFormHtml(btn, label));
    return;
  }}
  if (label.indexOf('编辑') >= 0 || label.indexOf('维护') >= 0) {{
    if (!getSelectedRow()) {{
      showMsg('请先选择一条记录');
      return;
    }}
    openGenericActionModal(label, buildGeneratedFormHtml(btn, label));
    return;
  }}
  if (label.indexOf('删除') >= 0 || label.indexOf('作废') >= 0) {{
    if (!getSelectedRow()) {{
      showMsg('请先选择一条记录');
      return;
    }}
    openGenericActionModal(label, '<div style="font-size:10pt;line-height:1.8;"><p>确认删除以下记录？</p><div class="overview-card" style="margin:10px 0;">' + escapeHtml(summarizeRow(getSelectedRow())) + '</div><div class="toolbar" style="justify-content:flex-end;"><button class="btn btn-primary" onclick="confirmDeleteSelected()">确认删除</button><button class="btn" onclick="closeModal(\\'modalGeneric\\')">取消</button></div></div>');
    return;
  }}
  if ((label.indexOf('审批') >= 0 || label.indexOf('审核') >= 0) && label.indexOf('查看') < 0) {{
    if (!getSelectedRow()) {{
      showMsg('请先选择一条记录');
      return;
    }}
    openGenericActionModal(label, '<div style="font-size:10pt;line-height:1.8;"><p>请填写审批意见：</p><div class="form-grid"><div class="form-item" style="grid-column:1 / -1;"><label>审批意见</label><textarea id="c2ApprovalOpinion" rows="4" style="width:100%;resize:vertical;"></textarea></div></div><div class="toolbar" style="justify-content:flex-end;margin-top:12px;"><button class="btn btn-primary" onclick="submitApproval(\\'approve\\')">同意</button><button class="btn" onclick="submitApproval(\\'reject\\')">驳回</button></div></div>');
    return;
  }}
  if (label.indexOf('查看') >= 0 || label.indexOf('预览') >= 0 || label.indexOf('详情') >= 0 || label.indexOf('明细') >= 0) {{
    openGenericActionModal(label, '<div style="font-size:10pt;line-height:1.8;"><p><b>当前记录：</b></p><div class="overview-card" style="margin:10px 0;">' + escapeHtml(summarizeRow(getSelectedRow())) + '</div><p>' + escapeHtml(label) + '功能已打开，可继续按业务需求细化字段、页签和联动逻辑。</p></div>');
    return;
  }}
  if (label.indexOf('提交') >= 0 || label.indexOf('保存') >= 0 || label.indexOf('确认') >= 0) {{
    openGenericActionModal(label, '<div style="font-size:10pt;line-height:1.8;"><p>确认执行“' + escapeHtml(label) + '”吗？</p><div class="toolbar" style="justify-content:flex-end;"><button class="btn btn-primary" onclick="closeModal(\\'modalGeneric\\');showMsg(\\'' + escapeHtml(label) + '成功\\')">确认</button><button class="btn" onclick="closeModal(\\'modalGeneric\\')">取消</button></div></div>');
    return;
  }}
  if (label.indexOf('导出') >= 0 || label.indexOf('下载') >= 0 || label.indexOf('打印') >= 0) {{
    openGenericActionModal(label, '<div style="font-size:10pt;line-height:1.8;"><p>已准备' + escapeHtml(label) + '内容。</p><p>当前为原型环境，保留导出入口与格式确认弹框，便于后续接入真实文件流。</p></div>');
    return;
  }}
  showMsg(label + '已触发');
}}

function selectTr(el) {{
  const table = el.closest('table');
  if (!table) return;
  table.querySelectorAll('tr').forEach(function(row) {{
    row.classList.remove('selected');
  }});
  el.classList.add('selected');
}}

function switchPane(el, tabId, title) {{
  document.querySelectorAll('.tree-leaf, .tree-root-item').forEach(function(node) {{
    node.classList.remove('active');
  }});
  el.classList.add('active');
  document.querySelectorAll('.tab-pane').forEach(function(pane) {{
    pane.classList.remove('active');
  }});
  const targetPane = document.getElementById(tabId);
  if (targetPane) {{
    targetPane.classList.add('active');
  }}
  document.getElementById('viewTitleText').textContent = title;
  document.getElementById('statusRight').textContent = '当前功能：' + title;
}}

function toggleFolder(id) {{
  const folder = document.getElementById(id);
  if (!folder) return;
  folder.classList.toggle('open');
  const toggle = folder.querySelector('.tree-folder-toggle');
  if (toggle) {{
    toggle.textContent = folder.classList.contains('open') ? '−' : '+';
  }}
}}

function resetForm(btn) {{
  const grid = btn.closest('.form-grid');
  if (!grid) {{
    showMsg('未找到可重置的查询区域');
    return;
  }}
  grid.querySelectorAll('input').forEach(function(input) {{
    if (input.type === 'checkbox' || input.type === 'radio') {{
      input.checked = false;
    }} else {{
      input.value = '';
    }}
  }});
  grid.querySelectorAll('select').forEach(function(select) {{
    select.selectedIndex = 0;
  }});
  showMsg('查询条件已重置');
}}

function toggleToolbar() {{
  toolbarCollapsed = !toolbarCollapsed;
  document.querySelector('.global-toolbar').classList.toggle('collapsed', toolbarCollapsed);
  const btn = document.querySelector('.tb-toggle');
  btn.textContent = toolbarCollapsed ? '▼' : '▲';
}}

function zoomPage(factor) {{
  currentZoom = Math.min(Math.max(currentZoom * factor, 0.5), 2);
  document.querySelector('.window').style.transform = 'scale(' + currentZoom + ')';
  document.querySelector('.window').style.transformOrigin = 'top center';
  showMsg('缩放: ' + Math.round(currentZoom * 100) + '%');
}}

function resetZoom() {{
  currentZoom = 1;
  document.querySelector('.window').style.transform = 'scale(1)';
  document.querySelector('.window').style.transformOrigin = 'top center';
  showMsg('缩放已重置');
}}

function toggleFullscreen() {{
  if (!document.fullscreenElement) {{
    document.documentElement.requestFullscreen().then(function() {{
      showMsg('全屏模式');
    }}).catch(function() {{
      showMsg('全屏不可用，请通过浏览器菜单操作');
    }});
  }} else {{
    document.exitFullscreen();
    showMsg('已退出全屏');
  }}
}}

document.addEventListener('click', function(e) {{
  if (document.body.hasAttribute('data-focus-exit') && focusMode) {{
    const btn = e.target.closest ? e.target.closest('.tb-btn') : null;
    if (btn && btn.getAttribute('onclick') && btn.getAttribute('onclick').indexOf('toggleFocus') !== -1) return;
    if (focusMode && e.target.closest && e.target.closest('.view-panel')) return;
    toggleFocus();
  }}
}});

document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape' && document.body.hasAttribute('data-focus-exit') && focusMode) {{
    toggleFocus();
  }}
}});

function toggleFocus() {{
  focusMode = !focusMode;
  document.body.classList.toggle('focus-mode', focusMode);
  document.getElementById('focusOverlay').classList.toggle('active', focusMode);
  showMsg(focusMode ? '🎯 聚焦模式 — 按 ESC 或再次点击按钮退出' : '已退出聚焦模式');
  if (focusMode) {{
    document.body.setAttribute('data-focus-exit', '1');
  }} else {{
    document.body.removeAttribute('data-focus-exit');
  }}
}}

function showHelp() {{
  showModal('modalGeneric');
  document.getElementById('modalGenTitle').textContent = '❓ 帮助 — ' + PROTOTYPE_TITLE;
  document.getElementById('modalGenBody').innerHTML = HELP_HTML || '<div style="font-size:10pt;line-height:1.8;">暂无帮助说明</div>';
}}

function captureCurrentScreenshot() {{
  const target = document.querySelector('.view-panel');
  if (!target || typeof html2canvas !== 'function') {{
    showMsg('截图依赖未就绪');
    return;
  }}

  const funcName = document.getElementById('viewTitleText').textContent.trim() || '未知功能';
  const now = new Date();
  const dateStr = now.getFullYear() + ('0' + (now.getMonth() + 1)).slice(-2) + ('0' + now.getDate()).slice(-2);
  const timeStr = ('0' + now.getHours()).slice(-2) + ('0' + now.getMinutes()).slice(-2) + ('0' + now.getSeconds()).slice(-2);
  const fileName = PROTOTYPE_TITLE + '_' + funcName + '_' + dateStr + '_' + timeStr + '.png';

  showMsg('正在截图...');

  html2canvas(target, {{
    scale: 2,
    useCORS: true,
    backgroundColor: '#EAEEF2',
    logging: false,
    allowTaint: true,
    width: target.scrollWidth,
    height: target.scrollHeight
  }}).then(function(canvas) {{
    const link = document.createElement('a');
    link.download = fileName;
    link.href = canvas.toDataURL('image/png');
    link.click();
    showMsg('✅ 截图已保存: ' + fileName);
  }}).catch(function(err) {{
    showMsg('截图失败: ' + err.message);
  }});
}}

function batchScreenshot() {{
  if (batchScreenshot.running) {{
    showMsg('批量截图进行中，请等待...');
    return;
  }}
  if (typeof html2canvas !== 'function') {{
    showMsg('批量截图依赖未就绪');
    return;
  }}
  batchScreenshot.running = true;

  const total = batchTabList.length;
  const results = [];
  showMsg('开始批量截图，共 ' + total + ' 个界面...');

  function captureNext(index) {{
    if (index >= total) {{
      generateWordDoc(results);
      batchScreenshot.running = false;
      return;
    }}

    const item = batchTabList[index];
    const navItem = document.querySelector('.tree-leaf[onclick*=\"\\'' + item.tabId + '\\'\"], .tree-root-item[onclick*=\"\\'' + item.tabId + '\\'\"]');
    if (navItem) {{
      navItem.click();
    }}

    setTimeout(function() {{
      const panel = document.querySelector('.view-panel');
      if (!panel) {{
        captureNext(index + 1);
        return;
      }}
      showMsg('截图 (' + (index + 1) + '/' + total + '): ' + item.title);
      html2canvas(panel, {{
        scale: 2,
        useCORS: true,
        backgroundColor: '#F0F0F0',
        logging: false,
        allowTaint: true,
        width: panel.scrollWidth,
        height: panel.scrollHeight
      }}).then(function(canvas) {{
        results.push({{ title: item.title, dataUrl: canvas.toDataURL('image/png') }});
        captureNext(index + 1);
      }}).catch(function() {{
        results.push({{ title: item.title, dataUrl: null }});
        captureNext(index + 1);
      }});
    }}, 500);
  }}

  captureNext(0);
}}

function generateWordDoc(results) {{
  const now = new Date();
  const dateStr = now.getFullYear() + ('0' + (now.getMonth() + 1)).slice(-2) + ('0' + now.getDate()).slice(-2);
  const fileName = PROTOTYPE_TITLE + '_批量截图_' + dateStr + '.doc';
  showMsg('正在生成Word文档...');

  let htmlContent = '<html xmlns:o=\"urn:schemas-microsoft-com:office:office\" xmlns:w=\"urn:schemas-microsoft-com:office:word\" xmlns=\"http://www.w3.org/TR/REC-html40\">';
  htmlContent += '<head><meta charset=\"UTF-8\"><title>' + PROTOTYPE_TITLE + ' - 功能截图</title>';
  htmlContent += '<style>body {{ font-family: 宋体, SimSun, serif; font-size: 12pt; margin: 40px; }} h2 {{ text-align: center; font-size: 16pt; margin-top: 30px; margin-bottom: 20px; }} .screenshot {{ text-align: center; margin-bottom: 10px; }} .screenshot img {{ max-width: 100%; }} .page-break {{ page-break-after: always; }}</style>';
  htmlContent += '</head><body>';

  results.forEach(function(result, index) {{
    if (!result.dataUrl) {{
      htmlContent += '<h2>' + result.title + ' - 截图失败</h2>' + (index < results.length - 1 ? '<br class=\"page-break\">' : '');
      return;
    }}
    htmlContent += '<h2>' + result.title + '</h2>';
    htmlContent += '<div class=\"screenshot\"><img src=\"' + result.dataUrl + '\" style=\"width:100%;max-width:650px;\"></div>';
    if (index < results.length - 1) {{
      htmlContent += '<br class=\"page-break\">';
    }}
  }});

  htmlContent += '</body><\\/html>';
  const blob = new Blob([htmlContent], {{ type: 'application/msword;charset=utf-8' }});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(link.href);
  showMsg('✅ 批量截图完成: ' + fileName);
}}

function generateDesignDoc() {{
  showModal('modalGeneric');
  document.getElementById('modalGenTitle').textContent = '📝 选择导出格式';
  document.getElementById('modalGenBody').innerHTML = `
    <div style="font-size:10pt;line-height:1.8;padding:10px 0;">
      <p>请选择功能设计文档的导出格式：</p>
      <div style="display:flex;gap:12px;margin-top:16px;justify-content:center;">
        <button class="btn btn-primary" onclick="closeModal('modalGeneric');startDocCapture('doc')" style="padding:8px 24px;min-height:40px;font-size:11pt;">📄 Word 文档 (.docx)</button>
        <button class="btn" onclick="closeModal('modalGeneric');startDocCapture('md')" style="padding:8px 24px;min-height:40px;font-size:11pt;">📝 Markdown 文档 (.md)</button>
      </div>
      <p style="margin-top:12px;color:#666;text-align:center;">两种格式均包含全部功能界面的截图和功能说明</p>
    </div>`;
}}

function startDocCapture(format) {{
  if (docCaptureRunning) {{
    showMsg('文档生成进行中，请等待...');
    return;
  }}
  if (typeof html2canvas !== 'function') {{
    showMsg('文档生成依赖未就绪');
    return;
  }}
  docCaptureRunning = true;
  const total = docTabList.length;
  const results = [];
  showMsg('开始截取界面，共 ' + total + ' 个...');

  function captureNext(index) {{
    if (index >= total) {{
      if (format === 'md') {{
        buildMarkdownDoc(results);
      }} else {{
        buildWordDoc(results);
      }}
      docCaptureRunning = false;
      return;
    }}

    const item = docTabList[index];
    const navItem = document.querySelector('.tree-leaf[onclick*=\"\\'' + item.tabId + '\\'\"], .tree-root-item[onclick*=\"\\'' + item.tabId + '\\'\"]');
    if (navItem) {{
      navItem.click();
    }}

    setTimeout(function() {{
      const panel = document.querySelector('.view-panel');
      if (!panel) {{
        captureNext(index + 1);
        return;
      }}
      showMsg('截取 (' + (index + 1) + '/' + total + '): ' + item.title);
      html2canvas(panel, {{
        scale: 2,
        useCORS: true,
        backgroundColor: '#F0F0F0',
        logging: false,
        allowTaint: true,
        width: panel.scrollWidth,
        height: panel.scrollHeight
      }}).then(function(canvas) {{
        results.push({{ title: item.title, desc: item.desc, dataUrl: canvas.toDataURL('image/png') }});
        captureNext(index + 1);
      }}).catch(function() {{
        results.push({{ title: item.title, desc: item.desc, dataUrl: null }});
        captureNext(index + 1);
      }});
    }}, 500);
  }}

  captureNext(0);
}}

function buildMarkdownDoc(results) {{
  if (typeof JSZip !== 'function') {{
    showMsg('Markdown导出依赖未就绪');
    return;
  }}
  showMsg('正在生成Markdown文档...');
  const now = new Date();
  const dateStr = now.getFullYear() + ('0' + (now.getMonth() + 1)).slice(-2) + ('0' + now.getDate()).slice(-2);
  const folderName = PROTOTYPE_TITLE + '_功能设计文档_' + dateStr;
  const imgDir = 'images/';
  let md = '# ' + PROTOTYPE_TITLE + ' — 功能设计文档\\n\\n';
  md += '**版本：** v1.0  **日期：** ' + now.toLocaleDateString('zh-CN') + '\\n\\n---\\n\\n';
  results.forEach(function(result, index) {{
    const imgFile = imgDir + result.title + '.png';
    md += '## ' + (index + 1) + '. ' + result.title + '\\n\\n';
    md += (result.desc || '') + '\\n\\n';
    if (result.dataUrl) {{
      md += '![' + result.title + '](' + imgFile + ')\\n\\n';
    }}
  }});

  const zip = new JSZip();
  zip.file(folderName + '.md', md);
  const imgFolder = zip.folder(imgDir);
  results.forEach(function(result) {{
    if (result.dataUrl) {{
      imgFolder.file(result.title + '.png', result.dataUrl.split(',')[1], {{ base64: true }});
    }}
  }});

  zip.generateAsync({{ type: 'blob' }}).then(function(blob) {{
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = folderName + '.zip';
    link.click();
    URL.revokeObjectURL(link.href);
    showMsg('✅ Markdown文档已生成: ' + folderName + '.zip');
  }});
}}

function buildWordDoc(results) {{
  showMsg('正在生成Word文档...');
  const now = new Date();
  const dateStr = now.getFullYear() + ('0' + (now.getMonth() + 1)).slice(-2) + ('0' + now.getDate()).slice(-2);
  const fileName = PROTOTYPE_TITLE + '_功能设计文档_' + dateStr + '.docx';
  let html = '<html xmlns:o=\"urn:schemas-microsoft-com:office:office\" xmlns:w=\"urn:schemas-microsoft-com:office:word\" xmlns=\"http://www.w3.org/TR/REC-html40\">';
  html += '<head><meta charset=\"UTF-8\"><title>' + PROTOTYPE_TITLE + ' - 功能设计文档</title>';
  html += '<style>body {{ font-family: 宋体, SimSun, serif; font-size: 11pt; margin: 50px; line-height: 1.7; }} h1 {{ text-align: center; font-size: 20pt; color: #2D82C3; border-bottom: 2px solid #2D82C3; padding-bottom: 10px; }} h2 {{ font-size: 14pt; color: #2D6EB0; margin-top: 25px; border-left: 4px solid #2D6EB0; padding-left: 10px; }} .screenshot {{ text-align: center; margin: 12px 0; }} .screenshot img {{ max-width: 100%; width: 650px; }} .desc-box {{ background: #F8FAFC; border: 1px solid #B0C4DE; padding: 10px 14px; margin: 8px 0; }} .page-break {{ page-break-after: always; }}</style></head><body>';
  html += '<h1>' + PROTOTYPE_TITLE + '</h1>';
  html += '<h2 style=\"border:none;text-align:center;font-size:16pt;margin-top:5px;\">功能设计文档</h2>';
  results.forEach(function(result, index) {{
    html += '<h2>' + result.title + '</h2>';
    if (result.dataUrl) {{
      html += '<div class=\"screenshot\"><img src=\"' + result.dataUrl + '\"></div>';
    }}
    html += '<div class=\"desc-box\"><b>功能说明：</b><br>' + (result.desc || '') + '</div>';
    if (index < results.length - 1) {{
      html += '<br class=\"page-break\">';
    }}
  }});
  html += '</body><\\/html>';
  const blob = new Blob([html], {{ type: 'application/msword;charset=utf-8' }});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(link.href);
  showMsg('✅ Word文档已生成: ' + fileName);
}}

function activatePrototypeInteractions() {{
  document.querySelectorAll('.modal-overlay').forEach(function(modal) {{
    modal.addEventListener('click', function(e) {{
      if (e.target === modal) {{
        modal.classList.remove('open');
      }}
    }});
  }});

  document.querySelectorAll('.scroll-table tbody tr, .data-table tbody tr').forEach(function(row) {{
    row.addEventListener('click', function() {{
      selectTr(row);
    }});
  }});

  document.querySelectorAll('.view-content .btn, .view-content .btn-sm').forEach(function(btn) {{
    if (btn.getAttribute('onclick')) {{
      return;
    }}
    btn.addEventListener('click', function(e) {{
      e.preventDefault();
      e.stopPropagation();
      handleGeneratedButtonAction(btn);
    }});
  }});
}}

activatePrototypeInteractions();
</script>
</body>
</html>"""


def _rebuild_export_preview_html(export_dir: Path) -> str:
    index_path = export_dir / "index.html"
    style_path = export_dir / "style.css"
    script_path = export_dir / "script.js"

    if not index_path.exists():
        raise FileNotFoundError(f"未找到导出的 index.html: {index_path}")

    html = _extract_best_html_document(index_path.read_text(encoding="utf-8", errors="ignore"))
    style_content = style_path.read_text(encoding="utf-8", errors="ignore") if style_path.exists() else ""
    script_content = script_path.read_text(encoding="utf-8", errors="ignore") if script_path.exists() else ""

    if style_content:
        html = html.replace('<link rel="stylesheet" href="./style.css">', f"<style>\n{style_content}\n</style>")

    external_scripts = "\n".join(
        f'<script src="{src}"></script>' for src in ALLOWED_EXTERNAL_SCRIPT_URLS
    )
    inline_script_tag = f"{external_scripts}\n<script>\n{script_content}\n</script>" if script_content else external_scripts
    html = html.replace('<script src="./script.js"></script>', inline_script_tag)

    return _normalize_generated_prototype_html(html)


def _read_export_meta(export_dir: Path) -> Dict[str, Any]:
    meta_path = export_dir / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}


def _resolve_export_dir(export_name: str) -> Path:
    safe_name = Path(str(export_name or "")).name
    export_dir = EXPORTS_DIR / safe_name
    if not safe_name or not export_dir.exists() or not export_dir.is_dir():
        raise FileNotFoundError("导出目录不存在")
    return export_dir


def _slugify_filename(text: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (text or "").strip(), flags=re.U)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:48] or "oracle-prd-prototype"


def _normalize_generated_prototype_html(html: str) -> str:
    text = (html or "").strip()
    if not text:
        return ""

    def _keep_allowed_script(match: re.Match[str]) -> str:
        tag = match.group(0)
        src_match = re.search(r"\bsrc=['\"]([^'\"]+)['\"]", tag, flags=re.I)
        if src_match and src_match.group(1) in ALLOWED_EXTERNAL_SCRIPT_URLS:
            return tag
        return ""

    text = re.sub(r"<script\b[^>]*\bsrc=['\"]https?://[^>]+></script>", _keep_allowed_script, text, flags=re.I)
    text = re.sub(r"<link\b[^>]*\bhref=['\"]https?://[^>]+>", "", text, flags=re.I)

    helper_script_tag = f"<script>\n{RUNTIME_HELPER_JS}\n</script>"
    if helper_script_tag in text:
        return text

    body_end_matches = list(re.finditer(r"</body>", text, re.I))
    if body_end_matches:
        last_match = body_end_matches[-1]
        text = (
            text[: last_match.start()]
            + helper_script_tag
            + "\n"
            + text[last_match.start() :]
        )
    else:
        text += "\n" + helper_script_tag

    return text


def _build_export_bundle(prototype_html: str, title: str, model: str = "") -> Dict[str, str]:
    html = _extract_best_html_document(_normalize_generated_prototype_html(prototype_html))
    if not html:
        raise RuntimeError("缺少可导出的原型 HTML。")

    meta = {
        "title": title or "Oracle PRD Prototype",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": _resolve_model(model),
    }

    return {
        "index.html": html.strip() + "\n",
        "meta.json": json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
    }


def _write_export_bundle(prototype_html: str, title: str, model: str = "") -> Dict[str, str]:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    export_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:6]
    export_name = _slugify_filename(title)
    export_dir = EXPORTS_DIR / f"{export_id}_{export_name}"
    export_dir.mkdir(parents=True, exist_ok=False)

    bundle_files = _build_export_bundle(prototype_html, title, model)
    for filename, content in bundle_files.items():
        (export_dir / filename).write_text(content, encoding="utf-8")

    zip_path = export_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename in bundle_files:
            zf.write(export_dir / filename, arcname=f"{export_dir.name}/{filename}")

    return {
        "export_id": export_id,
        "export_name": export_dir.name,
        "export_dir": str(export_dir),
        "zip_path": str(zip_path),
    }


def _build_export_payload(export_info: Dict[str, str]) -> Dict[str, str]:
    return {
        "export_id": export_info["export_id"],
        "export_name": export_info["export_name"],
        "export_dir": export_info["export_dir"],
        "download_url": f"/api/oracle-prd/export/{export_info['export_name']}/download",
    }


def _needs_prototype_generation(parsed: Dict[str, Any], messages: List[Dict[str, str]]) -> bool:
    latest_user_text = ""
    for item in reversed(messages):
        if item.get("role") == "user":
            latest_user_text = item.get("content", "")
            break

    raw_text = str(latest_user_text or "").strip().lower()
    if not raw_text:
        return False
    compact_text = re.sub(r"[\s,，。.!！？?；;：:\-_/]+", "", raw_text)

    negative_keywords = (
        "不要生成",
        "先别生成",
        "暂不生成",
        "先不生成",
        "还不生成",
        "不用生成",
        "不需要生成",
    )
    if any(keyword in raw_text or keyword in compact_text for keyword in negative_keywords):
        return False

    question_keywords = (
        "能不能生成",
        "可以生成吗",
        "能生成吗",
        "是否生成",
        "要不要生成",
        "还要生成吗",
    )
    if any(keyword in raw_text or keyword in compact_text for keyword in question_keywords):
        return False

    trigger_keywords = (
        "生成原型",
        "输出原型",
        "开始生成",
        "开始做原型",
        "确认生成",
        "确认开始生成",
        "确认做原型",
        "确认出原型",
        "直接生成",
        "立即生成",
        "继续生成",
        "生成页面",
        "生成文件",
        "开始出原型",
        "出原型",
        "做出来",
        "生成吧",
        "生成html",
        "生成 html",
        "输出html",
        "输出 html",
        "html 原型",
        "做原型",
    )
    if any(keyword in raw_text or keyword in compact_text for keyword in trigger_keywords):
        return True

    confirm_words = (
        "确定",
        "确认",
        "开始",
        "直接",
        "立即",
        "现在",
        "继续",
        "那就",
        "可以",
        "好的",
        "好",
        "行",
    )
    generate_words = (
        "生成",
        "做",
        "出",
    )
    generate_targets = (
        "原型",
        "页面",
        "界面",
        "html",
        "文件",
    )

    if any(word in compact_text for word in confirm_words) and any(word in compact_text for word in generate_words):
        return True

    if len(compact_text) <= 8 and compact_text in ("生成", "生成吧", "开始生成", "直接生成", "确认生成", "确定生成"):
        return True

    if any(word in compact_text for word in generate_words) and any(word in compact_text for word in generate_targets):
        return True

    return False


def _generate_prototype_html(bundle: Dict[str, Any], analysis: Dict[str, Any], messages: List[Dict[str, str]], existing_prototype_html: str = "", model: str = "") -> str:
    blueprint = _request_prototype_blueprint(bundle, analysis, messages, existing_prototype_html, model=model)
    if _is_usable_blueprint(blueprint):
        html = _build_prototype_shell_html(bundle, blueprint)
        return _normalize_generated_prototype_html(html)

    fallback_html = _request_full_prototype_html(bundle, analysis, messages, existing_prototype_html, model=model)
    if fallback_html:
        return fallback_html

    raise RuntimeError("模型未返回可用的原型蓝图 JSON，且回退 HTML 生成也失败。")


@oracle_prd_bp.route("/api/oracle-prd/context", methods=["GET"])
def get_oracle_prd_context():
    try:
        bundle = load_oracle_prd_bundle()
        return jsonify({
            "success": True,
            "document_title": bundle["document_title"],
            "document_excerpt": bundle["document_excerpt"],
            "skill_excerpt": bundle["skill_excerpt"],
            "forms_spec_excerpt": bundle["forms_spec_excerpt"],
            "skill_root": bundle["skill_root"],
            "preview_html": bundle["preview_html"],
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@oracle_prd_bp.route("/api/oracle-prd/chat", methods=["POST"])
def oracle_prd_chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    current_prototype_html = str(data.get("current_prototype_html", "") or "").strip()
    current_export_name = str(data.get("current_export_name", "") or "").strip()
    current_export_title = str(data.get("current_export_title", "") or "").strip()
    current_export_dir = str(data.get("current_export_dir", "") or "").strip()
    model = str(data.get("model", "") or "").strip()
    if not isinstance(messages, list) or not messages:
        return jsonify({"success": False, "error": "缺少 messages"}), 400

    api_key = Config.resolve_llm_key(model)
    if not api_key:
        return jsonify({"success": False, "error": "模型 API Key 未配置"}), 500

    try:
        bundle = load_oracle_prd_bundle()
        normalized_messages = _normalize_messages(messages)
        loaded_export_context = _build_loaded_export_context(
            current_prototype_html,
            current_export_name,
            current_export_title,
            current_export_dir,
        )
        payload_messages = [{"role": "system", "content": _build_analysis_system_prompt(bundle, loaded_export_context)}]
        payload_messages.extend(normalized_messages)

        completion = _request_modelscope_completion_with_error_handling(payload_messages, max_tokens=2200, timeout_seconds=45, model=model)
        result = _finalize_analysis_payload(
            payload_messages,
            normalized_messages,
            completion["content"],
            completion["finish_reason"],
            model=model,
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@oracle_prd_bp.route("/api/oracle-prd/chat-stream", methods=["POST"])
def oracle_prd_chat_stream():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    model = str(data.get("model", "") or "").strip()
    current_prototype_html = str(data.get("current_prototype_html", "") or "").strip()
    current_export_name = str(data.get("current_export_name", "") or "").strip()
    current_export_title = str(data.get("current_export_title", "") or "").strip()
    current_export_dir = str(data.get("current_export_dir", "") or "").strip()
    if not isinstance(messages, list) or not messages:
        return jsonify({"success": False, "error": "缺少 messages"}), 400

    api_key = Config.resolve_llm_key(model)
    if not api_key:
        return jsonify({"success": False, "error": "模型 API Key 未配置"}), 500

    @stream_with_context
    def generate() -> Iterator[str]:
        try:
            bundle = load_oracle_prd_bundle()
            normalized_messages = _normalize_messages(messages)
            loaded_export_context = _build_loaded_export_context(
                current_prototype_html,
                current_export_name,
                current_export_title,
                current_export_dir,
            )
            payload_messages = [{"role": "system", "content": _build_analysis_system_prompt(bundle, loaded_export_context)}]
            payload_messages.extend(normalized_messages)

            yield _sse_event("status", {"message": "正在整理需求上下文"})

            raw_content = ""
            finish_reason = ""
            last_reply = ""
            chunk_count = 0

            for chunk in _iter_modelscope_stream_with_error_handling(payload_messages, max_tokens=2200, timeout_seconds=45, model=model):
                finish_reason = chunk.get("finish_reason", "") or finish_reason
                delta = chunk.get("content", "") or ""
                if not delta:
                    continue

                raw_content += delta
                chunk_count += 1

                partial_reply = _extract_partial_json_string_field(raw_content, "reply")
                if partial_reply and partial_reply != last_reply:
                    delta_text = partial_reply[len(last_reply):]
                    last_reply = partial_reply
                    if delta_text:
                        yield _sse_event("reply_delta", {
                            "delta": delta_text,
                            "reply": partial_reply,
                        })

                if chunk_count == 1:
                    yield _sse_event("status", {"message": "模型开始返回内容"})
                elif chunk_count % 12 == 0:
                    yield _sse_event("status", {"message": f"正在接收模型回复，第 {chunk_count} 段"})

            result = _finalize_analysis_payload(payload_messages, normalized_messages, raw_content, finish_reason, model=model)
            yield _sse_event("result", result)
        except Exception as exc:
            yield _sse_event("error", {"error": str(exc)})
        finally:
            yield _sse_event("done", {"success": True})

    response = Response(generate(), content_type="text/event-stream; charset=utf-8")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@oracle_prd_bp.route("/api/oracle-prd/prototype", methods=["POST"])
def oracle_prd_prototype():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    analysis = data.get("analysis")
    current_prototype_html = str(data.get("current_prototype_html", "") or "").strip()
    model = str(data.get("model", "") or "").strip()
    if not isinstance(messages, list) or not messages:
        return jsonify({"success": False, "error": "缺少 messages"}), 400
    if not isinstance(analysis, dict):
        return jsonify({"success": False, "error": "缺少 analysis"}), 400

    api_key = Config.resolve_llm_key(model)
    if not api_key:
        return jsonify({"success": False, "error": "模型 API Key 未配置"}), 500

    try:
        bundle = load_oracle_prd_bundle()
        normalized_messages = _normalize_messages(messages)
        prototype_html = _generate_prototype_html(bundle, analysis, normalized_messages, current_prototype_html, model)
        if not prototype_html:
            raise RuntimeError("模型未返回完整 HTML 原型，请缩小页面范围后重试。")
        export_info = _write_export_bundle(
            prototype_html,
            analysis.get("display_title") or "原型预览",
            model,
        )

        return jsonify({
            "success": True,
            "prototype_html": prototype_html,
            "display_title": analysis.get("display_title") or "原型预览",
            "model": _resolve_model(model),
            "auto_export": _build_export_payload(export_info),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@oracle_prd_bp.route("/api/oracle-prd/prototype-stream", methods=["POST"])
def oracle_prd_prototype_stream():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    analysis = data.get("analysis")
    current_prototype_html = str(data.get("current_prototype_html", "") or "").strip()
    model = str(data.get("model", "") or "").strip()
    if not isinstance(messages, list) or not messages:
        return jsonify({"success": False, "error": "缺少 messages"}), 400
    if not isinstance(analysis, dict):
        return jsonify({"success": False, "error": "缺少 analysis"}), 400

    api_key = Config.resolve_llm_key(model)
    if not api_key:
        return jsonify({"success": False, "error": "模型 API Key 未配置"}), 500

    @stream_with_context
    def generate() -> Iterator[str]:
        try:
            bundle = load_oracle_prd_bundle()
            normalized_messages = _normalize_messages(messages)

            yield _sse_event("status", {"message": "正在汇总当前需求与原型约束"})

            blueprint_payload = [
                {
                    "role": "system",
                    "content": _build_prototype_blueprint_prompt(bundle, analysis, normalized_messages, current_prototype_html),
                }
            ]
            blueprint_content = ""
            blueprint_finish_reason = ""
            blueprint_chunk_count = 0

            yield _sse_event("status", {"message": "正在请求原型蓝图"})
            for chunk in _iter_modelscope_stream_with_error_handling(blueprint_payload, max_tokens=6000, timeout_seconds=180, model=selected_model):
                blueprint_finish_reason = chunk.get("finish_reason", "") or blueprint_finish_reason
                delta = chunk.get("content", "") or ""
                if not delta:
                    continue
                blueprint_content += delta
                blueprint_chunk_count += 1
                if blueprint_chunk_count == 1:
                    yield _sse_event("status", {"message": "蓝图内容开始返回"})
                elif blueprint_chunk_count % 18 == 0:
                    yield _sse_event("status", {"message": f"正在接收原型蓝图，第 {blueprint_chunk_count} 段"})

            blueprint = _normalize_prototype_blueprint(_extract_json_object(blueprint_content), analysis)
            if blueprint_finish_reason == "length" or not _is_usable_blueprint(blueprint):
                yield _sse_event("status", {"message": "蓝图不完整，正在自动补全"})
                blueprint = _request_prototype_blueprint(bundle, analysis, normalized_messages, current_prototype_html, model=selected_model)

            if _is_usable_blueprint(blueprint):
                yield _sse_event("status", {"message": "蓝图完成，正在套用固定模板"})
                prototype_html = _normalize_generated_prototype_html(_build_prototype_shell_html(bundle, blueprint))
                yield _sse_event("status", {"message": "原型生成完成，正在写入导出目录"})
                export_info = _write_export_bundle(
                    prototype_html,
                    analysis.get("display_title") or "原型预览",
                    model=selected_model,
                )
                yield _sse_event("result", {
                    "success": True,
                    "prototype_html": prototype_html,
                    "display_title": analysis.get("display_title") or "原型预览",
                    "model": _resolve_model(selected_model),
                    "auto_export": _build_export_payload(export_info),
                })
                return

            yield _sse_event("status", {"message": "蓝图不可用，回退到完整 HTML 生成"})

            html_payload = [
                {
                    "role": "system",
                    "content": _build_html_generation_prompt(bundle, analysis, normalized_messages, current_prototype_html),
                }
            ]
            html_content = ""
            html_finish_reason = ""
            html_chunk_count = 0

            for chunk in _iter_modelscope_stream_with_error_handling(html_payload, max_tokens=7000, timeout_seconds=180, model=selected_model):
                html_finish_reason = chunk.get("finish_reason", "") or html_finish_reason
                delta = chunk.get("content", "") or ""
                if not delta:
                    continue
                html_content += delta
                html_chunk_count += 1
                if html_chunk_count == 1:
                    yield _sse_event("status", {"message": "完整 HTML 开始返回"})
                elif html_chunk_count % 24 == 0:
                    yield _sse_event("status", {"message": f"正在接收完整 HTML，第 {html_chunk_count} 段"})

            prototype_html = _normalize_generated_prototype_html(_extract_html_document(html_content))
            if html_finish_reason == "length" or not prototype_html:
                yield _sse_event("status", {"message": "HTML 不完整，正在自动补全"})
                prototype_html = _request_full_prototype_html(bundle, analysis, normalized_messages, current_prototype_html, model=selected_model)

            if not prototype_html:
                raise RuntimeError("模型未返回完整 HTML 原型，请缩小页面范围后重试。")

            yield _sse_event("status", {"message": "原型生成完成，正在写入导出目录"})
            export_info = _write_export_bundle(
                prototype_html,
                analysis.get("display_title") or "原型预览",
                model=selected_model,
            )
            yield _sse_event("result", {
                "success": True,
                "prototype_html": prototype_html,
                "display_title": analysis.get("display_title") or "原型预览",
                "model": _resolve_model(selected_model),
                "auto_export": _build_export_payload(export_info),
            })
        except Exception as exc:
            yield _sse_event("error", {"error": str(exc)})
        finally:
            yield _sse_event("done", {"success": True})

    response = Response(generate(), content_type="text/event-stream; charset=utf-8")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@oracle_prd_bp.route("/api/oracle-prd/export", methods=["POST"])
def oracle_prd_export():
    data = request.get_json(silent=True) or {}
    prototype_html = str(data.get("prototype_html", "")).strip()
    title = str(data.get("title", "")).strip() or "Oracle PRD Prototype"
    if not prototype_html:
        return jsonify({"success": False, "error": "缺少 prototype_html"}), 400

    try:
        export_info = _write_export_bundle(prototype_html, title)
        payload = _build_export_payload(export_info)
        payload["success"] = True
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@oracle_prd_bp.route("/api/oracle-prd/exports", methods=["GET"])
def oracle_prd_exports():
    try:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        items = []
        for export_dir in sorted(
            [path for path in EXPORTS_DIR.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            meta = _read_export_meta(export_dir)
            items.append({
                "export_name": export_dir.name,
                "export_dir": str(export_dir),
                "title": meta.get("title") or export_dir.name,
                "generated_at": meta.get("generated_at") or datetime.fromtimestamp(export_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "model": meta.get("model") or "",
                "has_zip": export_dir.with_suffix(".zip").exists(),
            })

        return jsonify({
            "success": True,
            "items": items,
            "total": len(items),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@oracle_prd_bp.route("/api/oracle-prd/exports/<path:export_name>/load", methods=["GET"])
def oracle_prd_export_load(export_name: str):
    try:
        export_dir = _resolve_export_dir(export_name)
    except FileNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    try:
        safe_name = export_dir.name
        meta = _read_export_meta(export_dir)
        prototype_html = _rebuild_export_preview_html(export_dir)
        return jsonify({
            "success": True,
            "export_name": safe_name,
            "export_dir": str(export_dir),
            "title": meta.get("title") or safe_name,
            "generated_at": meta.get("generated_at") or "",
            "model": meta.get("model") or "",
            "prototype_html": prototype_html,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@oracle_prd_bp.route("/api/oracle-prd/export-load", methods=["GET"])
def oracle_prd_export_load_by_query():
    export_name = str(request.args.get("export_name", "") or "").strip()
    if not export_name:
        return jsonify({"success": False, "error": "缺少 export_name"}), 400

    try:
        export_dir = _resolve_export_dir(export_name)
    except FileNotFoundError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    try:
        meta = _read_export_meta(export_dir)
        prototype_html = _rebuild_export_preview_html(export_dir)
        return jsonify({
            "success": True,
            "export_name": export_dir.name,
            "export_dir": str(export_dir),
            "title": meta.get("title") or export_dir.name,
            "generated_at": meta.get("generated_at") or "",
            "model": meta.get("model") or "",
            "prototype_html": prototype_html,
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@oracle_prd_bp.route("/api/oracle-prd/export/<path:export_name>/download", methods=["GET"])
def oracle_prd_export_download(export_name: str):
    safe_name = Path(export_name).name
    zip_path = EXPORTS_DIR / f"{safe_name}.zip"
    if not zip_path.exists():
        return jsonify({"success": False, "error": "导出文件不存在"}), 404
    return send_file(zip_path, as_attachment=True, download_name=zip_path.name)
