"""
Word 流程图批量处理辅助函数。
"""

import os
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET


SUPPORTED_DOCX_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "gif", "tiff", "tif", "webp"}
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def is_docx_file(filename):
    return os.path.splitext(filename or "")[1].lower() == ".docx"


def extract_docx_images(docx_path, output_dir, batch_id, document_name):
    """从 docx 中按文档引用顺序提取图片，返回流程图识别可用的 image_entries。"""
    if not zipfile.is_zipfile(docx_path):
        raise ValueError("文件不是有效的DOCX文档")

    os.makedirs(output_dir, exist_ok=True)
    entries = []

    with zipfile.ZipFile(docx_path) as docx_file:
        image_members = _get_document_image_members(docx_file)
        if not image_members:
            image_members = _get_all_media_image_members(docx_file)

        for image_index, member_name in enumerate(image_members, 1):
            extension = os.path.splitext(member_name)[1].lower().lstrip(".")
            if extension not in SUPPORTED_DOCX_IMAGE_EXTENSIONS:
                continue

            unique_filename = f"word_flowchart_{batch_id}_{image_index:03d}.{extension}"
            image_path = os.path.join(output_dir, unique_filename)
            with open(image_path, "wb") as image_file:
                image_file.write(docx_file.read(member_name))

            entries.append(
                {
                    "filename": unique_filename,
                    "original_filename": f"Word图片{image_index:03d}.{extension}",
                    "path": image_path,
                    "image_index": image_index,
                    "source_document": document_name,
                }
            )

    return entries


def _get_document_image_members(docx_file):
    try:
        rels = _read_relationships(docx_file, "word/_rels/document.xml.rels", "word")
        document_xml = docx_file.read("word/document.xml")
    except KeyError:
        return []

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError:
        return []

    ordered_members = []
    for element in root.iter():
        for attr_name, rel_id in element.attrib.items():
            if not (attr_name.endswith("}embed") or attr_name.endswith("}link")):
                continue
            target = rels.get(rel_id)
            if target and _is_supported_media_member(docx_file, target):
                ordered_members.append(target)

    known_members = set(ordered_members)
    for member_name in _get_all_media_image_members(docx_file):
        if member_name not in known_members:
            ordered_members.append(member_name)

    return ordered_members


def _read_relationships(docx_file, rels_member, base_dir):
    root = ET.fromstring(docx_file.read(rels_member))
    rels = {}
    for relationship in root.findall(f"{REL_NS}Relationship"):
        rel_id = relationship.attrib.get("Id")
        target = relationship.attrib.get("Target", "")
        rel_type = relationship.attrib.get("Type", "")
        if not rel_id or not rel_type.endswith("/image") or target.startswith(("http://", "https://")):
            continue
        rels[rel_id] = _normalize_docx_target(base_dir, target)
    return rels


def _normalize_docx_target(base_dir, target):
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(base_dir, target))


def _get_all_media_image_members(docx_file):
    members = [
        member
        for member in docx_file.namelist()
        if _is_supported_media_member(docx_file, member)
    ]
    return sorted(members, key=_natural_sort_key)


def _is_supported_media_member(docx_file, member_name):
    if member_name not in docx_file.namelist() or not member_name.startswith("word/media/"):
        return False
    extension = os.path.splitext(member_name)[1].lower().lstrip(".")
    return extension in SUPPORTED_DOCX_IMAGE_EXTENSIONS


def _natural_sort_key(value):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]
