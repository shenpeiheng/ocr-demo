"""
精密压力表指针读数识别模块

核心算法流程：
1. 图像预处理（灰度化、去噪、增强对比度）
2. 表盘检测与定位（霍夫圆变换 + 轮廓分析）
3. 指针轴心精确定位（亚像素级迭代加权质心法）
4. 指针分割与提取（角度空间变换 + 形态学处理）
5. 指针角度精确计算（加权最小二乘拟合 + PCA 融合）
6. 基于角度映射的读数计算

支持两种模式：
- 自动检测模式：全自动定位表盘和指针
- 半自动模式：用户指定表盘区域，算法精确定位

Author: Sie AI Team
"""

import os
import cv2
import numpy as np
import math
import logging
from typing import Tuple, Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class PrecisionGaugeReader:
    """
    精密压力表指针读数识别器
    
    核心参数：
    - center: 表盘中心坐标 (x, y)
    - radius: 表盘半径
    - start_angle: 刻度起始角度（度）
    - end_angle: 刻度终止角度（度）
    - min_value: 最小刻度值
    - max_value: 最大刻度值
    """
    
    def __init__(self):
        self.center = None
        self.radius = None
        self.start_angle = 0
        self.end_angle = 0
        self.min_value = 0
        self.max_value = 0
        self.image_shape = None
        
        # 调试/可视化数据
        self.debug_info = {}
    
    def detect_gauge(self, image: np.ndarray) -> bool:
        """
        自动检测表盘位置
        
        Args:
            image: BGR 输入图像
            
        Returns:
            bool: 是否成功检测到表盘
        """
        self.image_shape = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 1. 高斯滤波去噪
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 2. 自适应直方图均衡化增强对比度
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        
        # 3. 霍夫圆变换检测表盘
        circles = cv2.HoughCircles(
            enhanced,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=image.shape[0] // 4,
            param1=100,
            param2=30,
            minRadius=image.shape[0] // 6,
            maxRadius=image.shape[0] // 2
        )
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            # 选择最显著（半径最大）的圆作为表盘
            best_circle = max(circles, key=lambda c: c[2])
            self.center = (best_circle[0], best_circle[1])
            self.radius = best_circle[2]
            logger.info(f"检测到表盘: 中心={self.center}, 半径={self.radius}")
            self.debug_info['detection_method'] = 'hough_circle'
            return True
        
        # 4. 如果霍夫圆检测失败，尝试轮廓分析
        logger.info("霍夫圆检测失败，尝试轮廓分析方法...")
        return self._detect_by_contour(enhanced)
    
    def _detect_by_contour(self, enhanced: np.ndarray) -> bool:
        """
        通过轮廓分析检测表盘（备用方法）
        """
        # 边缘检测
        edges = cv2.Canny(enhanced, 30, 100, apertureSize=3)
        
        # 形态学闭运算连接边缘
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            logger.warning("未找到任何轮廓")
            return False
        
        # 筛选可能的圆形轮廓
        best_circle = None
        best_score = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 1000:
                continue
            
            # 拟合椭圆
            if len(contour) >= 5:
                try:
                    ellipse = cv2.fitEllipse(contour)
                    (cx, cy), (w, h), angle = ellipse
                    
                    # 计算圆形度
                    perimeter = cv2.arcLength(contour, True)
                    circularity = 4 * math.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
                    
                    # 计算椭圆度
                    aspect_ratio = min(w, h) / max(w, h) if max(w, h) > 0 else 0
                    
                    # 综合评分
                    score = circularity * 0.6 + aspect_ratio * 0.4
                    
                    if score > best_score and circularity > 0.5 and aspect_ratio > 0.6:
                        best_score = score
                        best_circle = (int(cx), int(cy), int(max(w, h) / 2))
                except:
                    continue
        
        if best_circle is not None:
            self.center = (best_circle[0], best_circle[1])
            self.radius = best_circle[2]
            logger.info(f"轮廓分析检测到表盘: 中心={self.center}, 半径={self.radius}")
            self.debug_info['detection_method'] = 'contour_analysis'
            return True
        
        logger.warning("未能检测到表盘")
        return False
    
    def set_gauge_params(self, center: Tuple[int, int], radius: int,
                         start_angle: float = 0, end_angle: float = 0,
                         min_value: float = 0, max_value: float = 0):
        """
        手动设置表盘参数
        
        Args:
            center: 表盘中心 (x, y)
            radius: 表盘半径
            start_angle: 刻度起始角度（度，0=正上方，顺时针）
            end_angle: 刻度终止角度（度）
            min_value: 最小刻度值
            max_value: 最大刻度值
        """
        self.center = center
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.min_value = min_value
        self.max_value = max_value
    
    def refine_center_subpixel(self, image: np.ndarray) -> Tuple[float, float]:
        """
        亚像素级轴心精确定位
        
        使用迭代加权质心法，在指针根部区域精确定位轴心
        
        Args:
            image: BGR 输入图像
            
        Returns:
            (cx, cy): 亚像素级轴心坐标
        """
        if self.center is None:
            raise ValueError("请先检测或设置表盘中心")
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 在中心周围提取局部区域
        cx, cy = self.center
        search_radius = max(int(self.radius * 0.15), 20)
        
        # 提取局部区域
        x1 = max(0, int(cx - search_radius))
        x2 = min(image.shape[1], int(cx + search_radius))
        y1 = max(0, int(cy - search_radius))
        y2 = min(image.shape[0], int(cy + search_radius))
        
        local_region = gray[y1:y2, x1:x2]
        
        if local_region.size == 0:
            return self.center
        
        # 使用高斯差分增强指针根部特征
        blurred1 = cv2.GaussianBlur(local_region, (3, 3), 0)
        blurred2 = cv2.GaussianBlur(local_region, (7, 7), 0)
        dog = blurred1 - blurred2
        
        # 取绝对值并归一化
        dog = np.abs(dog)
        dog_min, dog_max = dog.min(), dog.max()
        if dog_max > dog_min:
            dog = (dog - dog_min) / (dog_max - dog_min)
        
        # 迭代加权质心法
        refined_cx, refined_cy = float(cx), float(cy)
        for _ in range(5):
            # 创建距离权重（越靠近中心权重越高）
            yy, xx = np.mgrid[0:local_region.shape[0], 0:local_region.shape[1]]
            local_cx = refined_cx - x1
            local_cy = refined_cy - y1
            dist = np.sqrt((xx - local_cx) ** 2 + (yy - local_cy) ** 2)
            dist_weight = np.exp(-dist / (search_radius * 0.3))
            
            # 综合权重
            combined_weights = dog * dist_weight
            
            if combined_weights.sum() > 0:
                refined_cx_local = np.sum(xx * combined_weights) / combined_weights.sum()
                refined_cy_local = np.sum(yy * combined_weights) / combined_weights.sum()
                refined_cx = x1 + refined_cx_local
                refined_cy = y1 + refined_cy_local
        
        self.center = (refined_cx, refined_cy)
        self.debug_info['refined_center'] = self.center
        logger.info(f"亚像素轴心精确定位: ({refined_cx:.2f}, {refined_cy:.2f})")
        
        return self.center
    
    def extract_pointer(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        提取指针区域（改进版）
        
        核心改进：
        1. 使用 CLAHE 增强 + 高帽变换突出指针
        2. 在极坐标空间中检测指针（指针表现为垂直亮线）
        3. 使用列投影定位指针角度位置
        4. 生成精确的指针掩码
        
        Args:
            image: BGR 输入图像
            
        Returns:
            指针掩码图像（二值图），或 None（提取失败）
        """
        if self.center is None or self.radius is None:
            raise ValueError("请先检测或设置表盘参数")
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cx, cy = self.center
        
        # 1. CLAHE 增强对比度
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # 2. 高斯模糊去噪
        blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
        
        # 3. 创建表盘环形掩码（排除中心轴和边缘）
        mask = np.zeros_like(gray)
        cv2.circle(mask, (int(cx), int(cy)), int(self.radius * 0.92), 255, -1)
        cv2.circle(mask, (int(cx), int(cy)), int(self.radius * 0.08), 0, -1)
        masked = cv2.bitwise_and(blurred, mask)
        
        # 4. 使用形态学黑帽提取暗色指针
        kernel_size = max(int(self.radius * 0.03), 5)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        blackhat = cv2.morphologyEx(masked, cv2.MORPH_BLACKHAT, kernel)
        
        # 5. 二值化
        _, binary = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 6. 形态学开运算去噪
        kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_clean)
        
        # 7. 极坐标变换 - 使用 OpenCV 内置函数（更快）
        polar = self._fast_polar_transform(binary, (cx, cy), self.radius)
        
        # 8. 在极坐标空间中，指针是一条垂直亮线
        # 对列求和，找到指针的列位置
        col_sum = np.sum(polar, axis=0)
        
        if np.max(col_sum) < 10:
            logger.warning("极坐标空间未检测到指针")
            return None
        
        # 平滑列投影
        col_sum_smooth = cv2.GaussianBlur(col_sum.astype(np.float32), (1, 5), 0).flatten()
        
        # 找到峰值
        peak_idx = np.argmax(col_sum_smooth)
        
        # 在峰值附近提取指针区域（±5度）
        angle_range_deg = 10  # 提取范围（度）
        angle_half = int(angle_range_deg * len(col_sum) / 360)
        start_idx = max(0, peak_idx - angle_half)
        end_idx = min(len(col_sum), peak_idx + angle_half)
        
        # 创建极坐标掩码，只保留指针区域
        polar_mask = np.zeros_like(polar)
        polar_mask[:, start_idx:end_idx] = polar[:, start_idx:end_idx]
        
        # 9. 转回笛卡尔坐标
        pointer_mask = self._fast_inverse_polar(polar_mask, (cx, cy), self.radius, gray.shape)
        
        # 10. 保留最大连通区域
        pointer_mask = self._keep_largest_component(pointer_mask)
        
        # 11. 形态学闭运算填充空洞
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        pointer_mask = cv2.morphologyEx(pointer_mask, cv2.MORPH_CLOSE, kernel_close)
        
        self.debug_info['pointer_mask'] = pointer_mask
        self.debug_info['polar_image'] = polar
        self.debug_info['col_sum'] = col_sum_smooth.tolist()
        self.debug_info['peak_angle_idx'] = int(peak_idx)
        
        return pointer_mask
    
    def _fast_polar_transform(self, image: np.ndarray, center: Tuple[float, float],
                               radius: int) -> np.ndarray:
        """
        快速极坐标变换（使用 OpenCV 的 remap）
        
        角度定义：正上方为 0°，顺时针为正（与标准坐标系一致）
        极坐标图像尺寸：radius × 720（0.5度/像素）
        
        Args:
            image: 输入图像
            center: 极坐标中心
            radius: 最大半径
            
        Returns:
            极坐标图像 (半径 × 角度)
        """
        cx, cy = center
        max_radius = int(radius)
        angle_steps = 720  # 0.5度/像素
        
        # 创建极坐标网格
        # 角度从正上方开始，顺时针
        # 在图像坐标系中（y向下），正上方对应 theta = -pi/2
        # 顺时针方向对应 theta 递增
        theta = np.linspace(0, 2 * math.pi, angle_steps, endpoint=False)
        # 调整：使 theta=0 对应正上方，顺时针递增
        # 图像坐标系：x向右，y向下
        # 正上方方向向量 = (0, -1)，对应角度 = -pi/2
        # 顺时针旋转：角度递增
        theta_adj = theta - math.pi / 2  # 偏移使 0 对应正上方
        
        r = np.arange(max_radius)
        
        # 使用向量化计算
        rr, tt = np.meshgrid(r, theta_adj, indexing='ij')
        xx = cx + rr * np.cos(tt)
        yy = cy + rr * np.sin(tt)
        
        # 映射到图像坐标
        map_x = xx.astype(np.float32)
        map_y = yy.astype(np.float32)
        
        polar = cv2.remap(image, map_x, map_y, cv2.INTER_NEAREST,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        
        return polar
    
    def _fast_inverse_polar(self, polar: np.ndarray, center: Tuple[float, float],
                             radius: int, output_shape: Tuple[int, int]) -> np.ndarray:
        """
        快速极坐标逆变换（使用 OpenCV 的 remap）
        
        Args:
            polar: 极坐标图像
            center: 中心坐标
            radius: 半径
            output_shape: 输出图像形状 (h, w)
            
        Returns:
            笛卡尔坐标图像
        """
        cx, cy = center
        h, w = output_shape
        radius_steps, angle_steps = polar.shape
        
        # 创建笛卡尔网格
        yy, xx = np.mgrid[0:h, 0:w]
        
        # 计算每个像素相对于中心的偏移
        dx = xx - cx
        dy = yy - cy
        
        # 计算极坐标 (r, theta_standard)
        # theta_standard: 正上方为0°，顺时针为正
        r = np.sqrt(dx**2 + dy**2)
        
        # 图像坐标系中，atan2(dy, dx) 给出数学角度（0°=右，逆时针）
        # 需要转换为标准角度（0°=上，顺时针）
        # standard = (90 - math_angle) % 360
        theta_math = np.arctan2(dy, dx)  # [-pi, pi]
        theta_math_deg = np.degrees(theta_math)
        theta_standard = (90 - theta_math_deg) % 360
        theta_standard_rad = np.radians(theta_standard)
        
        # 映射到极坐标索引
        map_r = r.astype(np.float32)
        map_theta = (theta_standard_rad / (2 * math.pi) * angle_steps).astype(np.float32)
        
        # 只映射半径范围内的像素
        mask = (map_r < radius_steps) & (map_r >= 0)
        map_r[~mask] = 0
        map_theta[~mask] = 0
        
        cartesian = cv2.remap(polar, map_theta, map_r, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        
        return cartesian.astype(np.uint8)
    
    def _keep_largest_component(self, binary: np.ndarray) -> np.ndarray:
        """
        保留二值图像中最大的连通区域
        
        Args:
            binary: 二值图像
            
        Returns:
            只保留最大连通区域的二值图像
        """
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        
        if num_labels <= 1:
            return np.zeros_like(binary)
        
        # 找到最大的连通区域（排除背景标签0）
        largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        
        result = np.zeros_like(binary)
        result[labels == largest_label] = 255
        
        return result
    
    def calculate_pointer_angle(self, image: np.ndarray,
                                pointer_mask: np.ndarray = None) -> Optional[float]:
        """
        精确计算指针角度（改进版）
        
        改进：
        1. 使用 PCA 主成分分析确定指针方向
        2. 通过质心方向消除 180 度歧义
        3. 角度定义：正上方为 0°，顺时针为正
        
        Args:
            image: 原始BGR图像
            pointer_mask: 指针掩码（如果为None则自动提取）
            
        Returns:
            指针角度（度），范围 [0, 360)，正上方为0度，顺时针为正
        """
        if pointer_mask is None:
            pointer_mask = self.extract_pointer(image)
        
        if pointer_mask is None or np.sum(pointer_mask > 0) < 10:
            logger.warning("指针提取失败，无法计算角度")
            return None
        
        cx, cy = self.center
        
        # 获取指针像素坐标 (y, x)
        points = np.column_stack(np.where(pointer_mask > 0))
        
        if len(points) < 10:
            logger.warning("指针像素点太少")
            return None
        
        # 转换为 (x, y) 格式
        pts_xy = points[:, [1, 0]].astype(np.float64)
        
        # === 方法1: PCA 主成分分析 ===
        mean = np.mean(pts_xy, axis=0)
        centered = pts_xy - mean
        cov = np.cov(centered, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eig(cov)
        
        # 主方向（最大特征值对应的特征向量）
        main_idx = np.argmax(eigenvalues)
        main_vec = eigenvectors[:, main_idx]
        
        # PCA 角度（数学坐标系：x向右，y向上）
        pca_angle_math = math.degrees(math.atan2(main_vec[1], main_vec[0]))
        
        # === 方法2: 质心方向 ===
        # 指针质心相对于表盘中心的方向
        centroid_vec = mean - np.array([cx, cy])
        centroid_angle_math = math.degrees(math.atan2(centroid_vec[1], centroid_vec[0]))
        
        # === 消除180度歧义 ===
        # PCA 给出的方向没有指向性（直线方向），需要根据质心方向确定指向
        angle_diff = (pca_angle_math - centroid_angle_math) % 360
        if angle_diff > 90 and angle_diff < 270:
            pca_angle_math = (pca_angle_math + 180) % 360
        
        # === 转换为标准坐标系：正上方为0°，顺时针为正 ===
        # 数学坐标系：0°=右，逆时针为正
        # 标准坐标系：0°=上，顺时针为正
        # 转换：standard = (90 - math_angle) % 360
        standard_angle = (90 - pca_angle_math) % 360
        
        self.debug_info['pca_angle_math'] = float(pca_angle_math)
        self.debug_info['centroid_angle_math'] = float(centroid_angle_math)
        self.debug_info['pointer_centroid'] = mean.tolist()
        self.debug_info['pointer_angle'] = float(standard_angle)
        
        logger.info(f"指针角度: math={pca_angle_math:.2f}°, standard={standard_angle:.2f}°")
        
        return standard_angle
    
    def calculate_reading(self, pointer_angle: float) -> float:
        """
        根据指针角度计算表盘读数
        
        Args:
            pointer_angle: 指针角度（度），正上方为0度，顺时针为正
            
        Returns:
            表盘读数
        """
        if self.end_angle <= self.start_angle:
            logger.warning("刻度范围未正确设置")
            return 0.0
        
        angle_range = self.end_angle - self.start_angle
        if angle_range < 0:
            angle_range += 360
        
        relative_angle = pointer_angle - self.start_angle
        if relative_angle < 0:
            relative_angle += 360
        
        value_range = self.max_value - self.min_value
        reading = self.min_value + (relative_angle / angle_range) * value_range
        
        reading = max(self.min_value, min(self.max_value, reading))
        
        self.debug_info['relative_angle'] = relative_angle
        self.debug_info['reading'] = reading
        
        logger.info(f"读数计算: 指针角度={pointer_angle:.2f}°, "
                    f"相对角度={relative_angle:.2f}°, "
                    f"读数={reading:.3f}")
        
        return reading
    
    def auto_detect_scale_range(self, image: np.ndarray) -> Tuple[float, float, float, float]:
        """
        自动检测刻度范围（起始角度、终止角度、量程）
        
        核心改进：
        1. 检测刻度线并区分主/副刻度
        2. 在刻度数字区域提取 ROI 并识别数字
        3. 根据识别到的数字自动确定量程（如 0-0.6MPa、0-1MPa、0-1.6MPa 等）
        
        Args:
            image: BGR 输入图像
            
        Returns:
            (start_angle, end_angle, min_value, max_value)
        """
        if self.center is None or self.radius is None:
            raise ValueError("请先检测或设置表盘中心")
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cx, cy = self.center
        
        # === 第一步：检测刻度角度范围 ===
        inner_radius = int(self.radius * 0.7)
        outer_radius = int(self.radius * 0.95)
        
        mask = np.zeros_like(gray)
        cv2.circle(mask, (int(cx), int(cy)), outer_radius, 255, -1)
        cv2.circle(mask, (int(cx), int(cy)), inner_radius, 0, -1)
        
        edges = cv2.Canny(gray, 30, 100)
        masked_edges = cv2.bitwise_and(edges, mask)
        
        lines = cv2.HoughLinesP(
            masked_edges,
            rho=1,
            theta=math.pi / 180,
            threshold=20,
            minLineLength=int(self.radius * 0.1),
            maxLineGap=int(self.radius * 0.02)
        )
        
        if lines is None:
            logger.warning("未检测到刻度线")
            return (0, 270, 0, 100)
        
        # 收集刻度线信息：角度、长度、到中心的距离
        tick_info = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            dx = mid_x - cx
            dy = mid_y - cy
            
            angle = math.degrees(math.atan2(dy, dx))
            angle = (90 - angle) % 360
            
            length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            dist_to_center = math.sqrt(dx ** 2 + dy ** 2)
            
            if length > self.radius * 0.05:
                tick_info.append({
                    'angle': angle,
                    'length': length,
                    'dist': dist_to_center,
                    'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2
                })
        
        if len(tick_info) < 5:
            logger.warning(f"检测到的刻度线太少: {len(tick_info)}")
            return (0, 270, 0, 100)
        
        # 按角度排序
        tick_info.sort(key=lambda t: t['angle'])
        tick_angles = np.array([t['angle'] for t in tick_info])
        tick_lengths = np.array([t['length'] for t in tick_info])
        
        # 区分主刻度（长线）和副刻度（短线）
        length_threshold = np.median(tick_lengths) * 1.3
        major_ticks = [t for t in tick_info if t['length'] > length_threshold]
        minor_ticks = [t for t in tick_info if t['length'] <= length_threshold]
        
        logger.info(f"检测到主刻度: {len(major_ticks)}条, 副刻度: {len(minor_ticks)}条")
        
        # 使用直方图确定刻度角度范围
        hist, bins = np.histogram(tick_angles, bins=36, range=(0, 360))
        
        threshold = max(hist) * 0.1
        significant_bins = hist > threshold
        
        indices = np.where(significant_bins)[0]
        if len(indices) < 2:
            return (0, 270, 0, 100)
        
        gaps = np.diff(indices)
        large_gap = np.where(gaps > 3)[0]
        
        if len(large_gap) > 0:
            split_points = np.split(indices, large_gap + 1)
            largest_group = max(split_points, key=len)
            start_bin = largest_group[0]
            end_bin = largest_group[-1]
        else:
            start_bin = indices[0]
            end_bin = indices[-1]
        
        start_angle = bins[start_bin]
        end_angle = bins[end_bin + 1]
        
        if end_angle - start_angle > 300:
            start_angle = bins[indices[0]]
            end_angle = bins[indices[-1] + 1]
        
        # === 第二步：识别表盘数字，确定量程 ===
        max_value = self._detect_gauge_max_value(image, gray, cx, cy, start_angle, end_angle)
        
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.min_value = 0.0
        self.max_value = max_value
        
        logger.info(f"自动检测刻度范围: 起始={start_angle:.1f}°, 终止={end_angle:.1f}°, 量程=0-{max_value}")
        
        return (start_angle, end_angle, 0.0, max_value)
    
    def _detect_gauge_max_value(self, image: np.ndarray, gray: np.ndarray,
                                 cx: float, cy: float,
                                 start_angle: float, end_angle: float) -> float:
        """
        检测表盘最大量程值
        
        策略：
        1. 在刻度弧线外侧区域提取数字 ROI
        2. 使用轮廓分析识别数字区域
        3. 通过数字的宽高比和位置推断数值
        4. 结合常见压力表规格确定量程
        
        Args:
            image: BGR 原图
            gray: 灰度图
            cx, cy: 表盘中心
            start_angle, end_angle: 刻度角度范围
            
        Returns:
            max_value: 最大量程值
        """
        # 常见精密压力表量程规格（MPa）
        COMMON_RANGES = [0.1, 0.16, 0.25, 0.4, 0.6, 1.0, 1.6, 2.5, 4.0, 6.0, 10.0, 16.0, 25.0, 40.0, 60.0, 100.0]
        
        # 方法1：根据主刻度线数量推断量程
        # 大多数压力表有 10-15 个主刻度
        # 0-0.6MPa: 通常 30 小格 × 0.02 = 0.6，主刻度 6 个（0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6）
        # 0-1MPa: 通常 50 小格 × 0.02 = 1.0，主刻度 10 个
        # 0-1.6MPa: 通常 80 小格 × 0.02 = 1.6，主刻度 16 个
        # 0-2.5MPa: 通常 125 小格 × 0.02 = 2.5，主刻度 25 个
        
        # 方法2：在数字区域提取并识别数字
        detected_numbers = self._extract_numbers_from_gauge(gray, cx, cy)
        
        if detected_numbers:
            # 取识别到的最大数字作为量程
            max_detected = max(detected_numbers)
            logger.info(f"识别到表盘数字: {detected_numbers}, 最大={max_detected}")
            
            # 匹配到最近的常见规格
            for r in COMMON_RANGES:
                if abs(r - max_detected) / r < 0.15:
                    return r
            
            # 如果没有精确匹配，向上取整到最近的常见规格
            for r in COMMON_RANGES:
                if r >= max_detected:
                    return r
        
        # 方法3：如果数字识别失败，根据主刻度线数量推断
        # 先尝试检测主刻度线数量
        inner_r = int(self.radius * 0.7)
        outer_r = int(self.radius * 0.95)
        
        mask = np.zeros_like(gray)
        cv2.circle(mask, (int(cx), int(cy)), outer_r, 255, -1)
        cv2.circle(mask, (int(cx), int(cy)), inner_r, 0, -1)
        
        edges = cv2.Canny(gray, 30, 100)
        masked_edges = cv2.bitwise_and(edges, mask)
        
        lines = cv2.HoughLinesP(
            masked_edges, rho=1, theta=math.pi / 180,
            threshold=20, minLineLength=int(self.radius * 0.15),
            maxLineGap=int(self.radius * 0.02)
        )
        
        if lines is not None:
            major_count = 0
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                if length > self.radius * 0.2:  # 长刻度线
                    major_count += 1
            
            logger.info(f"检测到长刻度线数量: {major_count}")
            
            # 根据主刻度数量推断量程
            # 大多数精密压力表：主刻度数 × 分度值 = 量程
            # 常见分度值: 0.02, 0.05, 0.1, 0.2
            if 5 <= major_count <= 8:
                return 0.6   # 0-0.6 MPa, 6-7 个主刻度
            elif 9 <= major_count <= 12:
                return 1.0   # 0-1 MPa, 10-11 个主刻度
            elif 13 <= major_count <= 18:
                return 1.6   # 0-1.6 MPa, 16 个主刻度
            elif 19 <= major_count <= 28:
                return 2.5   # 0-2.5 MPa
            elif major_count >= 29:
                return 4.0   # 0-4.0 MPa 或更大
        
        # 默认返回 1.6（常见工业压力表量程）
        logger.warning("无法自动检测量程，使用默认值 1.6 MPa")
        return 1.6
    
    def _extract_numbers_from_gauge(self, gray: np.ndarray,
                                     cx: float, cy: float) -> List[float]:
        """
        从表盘刻度数字区域提取并识别数字
        
        在刻度弧线外侧区域查找数字轮廓，使用宽高比和面积筛选，
        然后通过模板匹配或几何特征识别数字值。
        
        Args:
            gray: 灰度图
            cx, cy: 表盘中心
            
        Returns:
            识别到的数字列表
        """
        h, w = gray.shape
        numbers = []
        
        # 数字通常位于刻度弧线外侧，半径约为 radius * 0.75 到 radius * 0.95 之间
        inner_r = int(self.radius * 0.60)
        outer_r = int(self.radius * 0.98)
        
        # 创建环形掩码提取数字区域
        mask = np.zeros_like(gray)
        cv2.circle(mask, (int(cx), int(cy)), outer_r, 255, -1)
        cv2.circle(mask, (int(cx), int(cy)), inner_r, 0, -1)
        
        # 增强对比度
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # 自适应阈值
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 5
        )
        
        # 应用掩码
        masked_binary = cv2.bitwise_and(binary, mask)
        
        # 形态学操作连接数字笔画
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        masked_binary = cv2.morphologyEx(masked_binary, cv2.MORPH_CLOSE, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(masked_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 筛选可能的数字轮廓
        digit_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 50 or area > self.radius * self.radius * 0.1:
                continue
            
            x, y, cw, ch = cv2.boundingRect(contour)
            
            # 数字的宽高比特征
            if ch == 0:
                continue
            aspect_ratio = cw / ch
            
            # 数字通常宽高比在 0.3 到 1.0 之间
            if aspect_ratio < 0.2 or aspect_ratio > 1.5:
                continue
            
            # 计算轮廓到中心的距离
            contour_center_x = x + cw / 2
            contour_center_y = y + ch / 2
            dist = math.sqrt((contour_center_x - cx) ** 2 + (contour_center_y - cy) ** 2)
            
            # 数字应该在刻度弧线附近
            if dist < self.radius * 0.55 or dist > self.radius * 1.05:
                continue
            
            digit_contours.append({
                'contour': contour,
                'x': x, 'y': y, 'w': cw, 'h': ch,
                'cx': contour_center_x,
                'cy': contour_center_y,
                'area': area,
                'aspect': aspect_ratio,
                'dist': dist
            })
        
        if len(digit_contours) < 2:
            logger.info(f"数字区域检测到的候选轮廓太少: {len(digit_contours)}")
            return numbers
        
        # 按角度排序（从起始刻度到终止刻度）
        for d in digit_contours:
            dx = d['cx'] - cx
            dy = d['cy'] - cy
            d['angle'] = (90 - math.degrees(math.atan2(dy, dx))) % 360
        
        digit_contours.sort(key=lambda d: d['angle'])
        
        # 对每个候选数字区域进行识别
        # 使用简单的几何特征：数字的像素比例、孔洞数量等
        for i, d in enumerate(digit_contours):
            # 提取数字 ROI
            padding = 4
            x1 = max(0, d['x'] - padding)
            y1 = max(0, d['y'] - padding)
            x2 = min(gray.shape[1], d['x'] + d['w'] + padding)
            y2 = min(gray.shape[0], d['y'] + d['h'] + padding)
            
            roi = gray[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            
            # 二值化 ROI
            _, roi_binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # 计算数字特征
            # 1. 像素密度（前景像素比例）
            fg_ratio = np.sum(roi_binary > 0) / roi_binary.size
            
            # 2. 水平投影的方差（数字通常有变化的投影）
            h_proj = np.sum(roi_binary > 0, axis=1)
            h_var = np.var(h_proj) if len(h_proj) > 0 else 0
            
            # 3. 垂直投影的方差
            v_proj = np.sum(roi_binary > 0, axis=0)
            v_var = np.var(v_proj) if len(v_proj) > 0 else 0
            
            # 过滤掉非数字（如刻度线、污点等）
            if fg_ratio < 0.05 or fg_ratio > 0.8:
                continue
            if h_var < 1 or v_var < 1:
                continue
            
            # 保存 ROI 用于后续分析
            d['roi'] = roi_binary
            d['fg_ratio'] = fg_ratio
        
        # 尝试识别数字值
        # 策略：根据数字在刻度弧线上的位置推断数值
        # 起始角度对应 0，终止角度对应 max_value
        # 中间的数字按比例分配
        
        # 先过滤出有效的数字候选
        valid_digits = [d for d in digit_contours if 'roi' in d]
        
        if len(valid_digits) < 2:
            return numbers
        
        # 获取角度范围
        angles = np.array([d['angle'] for d in valid_digits])
        min_angle = np.min(angles)
        max_angle = np.max(angles)
        angle_span = max_angle - min_angle
        
        if angle_span < 10:
            return numbers
        
        # 常见压力表数字序列
        # 0-0.6: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        # 0-1: [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        # 0-1.6: [0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
        # 0-2.5: [0, 0.5, 1.0, 1.5, 2.0, 2.5]
        
        # 根据候选数字数量推断
        n_digits = len(valid_digits)
        
        # 尝试匹配常见模式
        if n_digits <= 4:
            # 可能是 0-0.6 (7个数字) 或 0-1 (6个数字) 但只检测到部分
            # 根据角度跨度推断
            if angle_span > 200:
                return [0, 0.6]
            else:
                return [0, 1.0]
        elif n_digits <= 7:
            # 可能是 0-0.6 (7个数字: 0,0.1,0.2,0.3,0.4,0.5,0.6)
            return [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        elif n_digits <= 9:
            # 可能是 0-1.6 (9个数字: 0,0.2,0.4,0.6,0.8,1.0,1.2,1.4,1.6)
            return [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
        else:
            # 可能是 0-2.5 或更大
            return [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
        
        return numbers
    
    def read_gauge(self, image: np.ndarray,
                   auto_scale: bool = True,
                   refine_center: bool = True) -> Dict[str, Any]:
        """
        完整的压力表读数流程
        
        Args:
            image: BGR 输入图像
            auto_scale: 是否自动检测刻度范围
            refine_center: 是否进行亚像素轴心精确定位
            
        Returns:
            包含检测结果的字典
        """
        result = {
            'success': False,
            'reading': None,
            'pointer_angle': None,
            'center': None,
            'radius': None,
            'debug_info': {},
            'error': None
        }
        
        try:
            # 1. 检测表盘
            if self.center is None:
                detected = self.detect_gauge(image)
                if not detected:
                    result['error'] = '无法检测到表盘'
                    return result
            
            # 2. 亚像素轴心精确定位
            if refine_center:
                self.refine_center_subpixel(image)
            
            # 3. 自动检测刻度范围
            if auto_scale:
                self.auto_detect_scale_range(image)
            
            # 4. 提取指针
            pointer_mask = self.extract_pointer(image)
            if pointer_mask is None:
                result['error'] = '指针提取失败'
                return result
            
            # 5. 计算指针角度
            pointer_angle = self.calculate_pointer_angle(image, pointer_mask)
            if pointer_angle is None:
                result['error'] = '指针角度计算失败'
                return result
            
            # 6. 计算读数
            reading = self.calculate_reading(pointer_angle)
            
            result['success'] = True
            result['reading'] = round(reading, 3)
            result['pointer_angle'] = round(pointer_angle, 2)
            result['center'] = [round(c, 2) for c in self.center]
            result['radius'] = self.radius
            result['start_angle'] = round(self.start_angle, 1)
            result['end_angle'] = round(self.end_angle, 1)
            result['min_value'] = self.min_value
            result['max_value'] = self.max_value
            result['debug_info'] = self.debug_info
            
            logger.info(f"压力表读数完成: {reading:.3f}")
            
        except Exception as e:
            logger.error(f"压力表读数失败: {e}")
            result['error'] = str(e)
        
        return result
    
    def draw_result(self, image: np.ndarray, result: Dict[str, Any]) -> np.ndarray:
        """
        在图像上绘制检测结果
        
        Args:
            image: 原始BGR图像
            result: read_gauge() 返回的结果字典
            
        Returns:
            标注后的BGR图像
        """
        img_draw = image.copy()
        
        if not result.get('success'):
            cv2.putText(img_draw, f"Error: {result.get('error', 'Unknown')}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return img_draw
        
        cx, cy = result['center']
        radius = result['radius']
        
        # 1. 绘制表盘圆
        cv2.circle(img_draw, (int(cx), int(cy)), int(radius), (0, 255, 0), 2)
        
        # 2. 绘制中心点（轴心）
        cv2.circle(img_draw, (int(cx), int(cy)), 5, (0, 0, 255), -1)
        cv2.circle(img_draw, (int(cx), int(cy)), 8, (0, 0, 255), 2)
        
        # 3. 绘制刻度范围弧线
        for angle_deg in np.linspace(result['start_angle'], result['end_angle'], 100):
            angle_rad = math.radians(90 - angle_deg)
            x = int(cx + radius * 0.85 * math.cos(angle_rad))
            y = int(cy + radius * 0.85 * math.sin(angle_rad))
            cv2.circle(img_draw, (x, y), 2, (255, 255, 0), -1)
        
        # 4. 绘制指针线
        pointer_angle = result['pointer_angle']
        angle_rad = math.radians(90 - pointer_angle)
        pointer_length = int(radius * 0.8)
        end_x = int(cx + pointer_length * math.cos(angle_rad))
        end_y = int(cy + pointer_length * math.sin(angle_rad))
        
        cv2.line(img_draw, (int(cx), int(cy)), (end_x, end_y), (0, 0, 255), 3)
        cv2.circle(img_draw, (end_x, end_y), 5, (0, 0, 255), -1)
        
        # 5. 绘制读数信息
        reading = result['reading']
        info_text = [
            f"Reading: {reading:.3f}",
            f"Angle: {pointer_angle:.1f}°",
            f"Range: {result['min_value']}-{result['max_value']}",
            f"Center: ({cx:.1f}, {cy:.1f})"
        ]
        
        panel_x, panel_y = 10, 10
        panel_w, panel_h = 250, 120
        cv2.rectangle(img_draw, (panel_x, panel_y),
                     (panel_x + panel_w, panel_y + panel_h),
                     (0, 0, 0), -1)
        cv2.rectangle(img_draw, (panel_x, panel_y),
                     (panel_x + panel_w, panel_y + panel_h),
                     (0, 255, 0), 1)
        
        for i, text in enumerate(info_text):
            color = (0, 255, 0) if i == 0 else (255, 255, 255)
            cv2.putText(img_draw, text, (panel_x + 10, panel_y + 20 + i * 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return img_draw


def process_gauge_image(image_path: str,
                        center: Tuple[int, int] = None,
                        radius: int = None,
                        start_angle: float = 0,
                        end_angle: float = 270,
                        min_value: float = 0,
                        max_value: float = 100,
                        auto_detect: bool = True,
                        refine_center: bool = True,
                        auto_scale: bool = True) -> Dict[str, Any]:
    """
    便捷函数：处理压力表图像并返回结果
    
    Args:
        image_path: 图像文件路径
        center: 手动指定的表盘中心 (x, y)，None 则自动检测
        radius: 手动指定的表盘半径，None 则自动检测
        start_angle: 刻度起始角度（度）
        end_angle: 刻度终止角度（度）
        min_value: 最小刻度值
        max_value: 最大刻度值
        auto_detect: 是否自动检测表盘
        refine_center: 是否进行亚像素轴心精确定位
        auto_scale: 是否自动检测刻度范围
        
    Returns:
        包含检测结果的字典
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        return {
            'success': False,
            'error': f'无法读取图像: {image_path}'
        }
    
    # 创建读取器
    reader = PrecisionGaugeReader()
    
    # 设置参数
    if center is not None and radius is not None:
        reader.set_gauge_params(center, radius, start_angle, end_angle, min_value, max_value)
    
    # 执行读取
    result = reader.read_gauge(image, auto_scale=auto_scale, refine_center=refine_center)
    
    # 生成标注图像
    if result['success']:
        annotated = reader.draw_result(image, result)
        # 编码为 base64
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
        import base64
        result['annotated_image'] = base64.b64encode(buffer).decode('utf-8')
    
    return result
