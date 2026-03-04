"""
图片预处理工具函数
提供尺寸检查、等比缩放和填充白边功能
"""

import os
import logging
from PIL import Image
import numpy as np
import cv2

logger = logging.getLogger(__name__)

def check_image_size(image_path: str, min_size: int = 1000) -> tuple:
    """
    检查图片尺寸是否满足最小要求
    
    Args:
        image_path: 图片文件路径
        min_size: 最小尺寸（宽和高）
        
    Returns:
        tuple: (width, height, needs_resize)
        needs_resize: True表示需要调整尺寸（任意一边小于min_size）
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            needs_resize = width < min_size or height < min_size
            return width, height, needs_resize
    except Exception as e:
        logger.error(f"检查图片尺寸失败: {e}")
        raise

def resize_with_padding(image_path: str, target_size: int = 990, output_path: str = None) -> str:
    """
    填充白边到目标尺寸，图片不变形
    
    规则：
    1. 如果图片宽和高都大于等于目标尺寸，保持原尺寸
    2. 如果只有一边小于目标尺寸，保持较大边不变，在较小边填充白边
    3. 如果两边都小于目标尺寸，等比缩放到目标尺寸，然后填充白边到目标尺寸
    
    Args:
        image_path: 原始图片路径
        target_size: 目标最小尺寸
        output_path: 输出文件路径，如果为None则自动生成
        
    Returns:
        str: 处理后的图片路径
    """
    try:
        # 打开原始图片
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            logger.info(f"原始图片尺寸: {original_width}x{original_height}, 目标最小尺寸: {target_size}")
            
            # 检查是否需要调整尺寸
            if original_width >= target_size and original_height >= target_size:
                logger.info(f"图片尺寸已满足要求，无需调整")
                if output_path and output_path != image_path:
                    img.save(output_path)
                    return output_path
                return image_path
            
            # 计算最终画布尺寸
            canvas_width = original_width
            canvas_height = original_height
            
            if original_width >= target_size and original_height < target_size:
                # 情况1：宽度足够，高度不足 - 保持宽度不变，高度填充到目标尺寸
                canvas_height = target_size
                logger.info(f"高度不足，保持宽度{original_width}不变，高度从{original_height}填充到{target_size}")
            elif original_height >= target_size and original_width < target_size:
                # 情况2：高度足够，宽度不足 - 保持高度不变，宽度填充到目标尺寸
                canvas_width = target_size
                logger.info(f"宽度不足，保持高度{original_height}不变，宽度从{original_width}填充到{target_size}")
            else:
                # 情况3：两边都不足 - 先等比缩放到目标尺寸
                scale = target_size / max(original_width, original_height)
                canvas_width = int(original_width * scale)
                canvas_height = int(original_height * scale)
                logger.info(f"两边都不足，等比缩放比例: {scale:.3f}, 缩放后尺寸: {canvas_width}x{canvas_height}")
            
            # 创建白色背景画布
            background = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
            
            # 计算放置位置（居中）
            x_offset = (canvas_width - original_width) // 2
            y_offset = (canvas_height - original_height) // 2
            
            # 将原始图片粘贴到白色背景上
            background.paste(img, (x_offset, y_offset))
            
            # 生成输出路径
            if output_path is None:
                base_name = os.path.splitext(image_path)[0]
                ext = os.path.splitext(image_path)[1]
                output_path = f"{base_name}_preprocessed{ext}"
            
            # 保存处理后的图片
            background.save(output_path)
            logger.info(f"图片处理完成，保存到: {output_path}, 最终尺寸: {canvas_width}x{canvas_height}")
            
            return output_path
            
    except Exception as e:
        logger.error(f"图片填充白边失败: {e}")
        raise

def preprocess_image_for_ocr(image_path: str, target_size: int = 990) -> str:
    """
    为OCR预处理图片：检查尺寸并调整到目标尺寸
    
    Args:
        image_path: 原始图片路径
        target_size: 目标尺寸
        
    Returns:
        str: 处理后的图片路径（如果不需要处理则返回原路径）
    """
    try:
        # 检查图片尺寸
        width, height, needs_resize = check_image_size(image_path, target_size)
        
        if needs_resize:
            logger.info(f"图片尺寸{width}x{height}小于目标尺寸{target_size}，进行等比缩放和填充白边")
            # 生成预处理后的图片路径
            base_name = os.path.splitext(image_path)[0]
            ext = os.path.splitext(image_path)[1]
            preprocessed_path = f"{base_name}_preprocessed{ext}"
            
            return resize_with_padding(image_path, target_size, preprocessed_path)
        else:
            logger.info(f"图片尺寸{width}x{height}已满足要求，无需处理")
            return image_path
            
    except Exception as e:
        logger.error(f"图片预处理失败: {e}")
        # 如果预处理失败，返回原始图片路径
        return image_path

def get_image_dimensions(image_path: str) -> tuple:
    """
    获取图片尺寸
    
    Args:
        image_path: 图片路径
        
    Returns:
        tuple: (width, height)
    """
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        logger.error(f"获取图片尺寸失败: {e}")
        return (0, 0)

def convert_to_rgb(image_path: str) -> np.ndarray:
    """
    将图片转换为RGB格式的numpy数组（供OCR使用）
    
    Args:
        image_path: 图片路径
        
    Returns:
        np.ndarray: RGB格式的图片数组
    """
    try:
        # 使用OpenCV读取
        img = cv2.imread(image_path)
        if img is not None:
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 如果OpenCV失败，使用PIL
        with Image.open(image_path) as pil_img:
            return np.array(pil_img.convert('RGB'))
    except Exception as e:
        logger.error(f"图片转换失败: {e}")
        raise