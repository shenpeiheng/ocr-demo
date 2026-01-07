"""
创建示例工业图纸图片 - 用于测试OCR识别系统
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_sample_industrial_drawing():
    """创建示例工业图纸图片"""
    # 创建空白图片
    width, height = 800, 600
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # 尝试加载字体（使用默认字体）
    try:
        font = ImageFont.truetype("arial.ttf", 20)
        font_small = ImageFont.truetype("arial.ttf", 16)
        font_large = ImageFont.truetype("arial.ttf", 24)
    except:
        # 如果找不到字体，使用默认字体
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_large = ImageFont.load_default()
    
    # 绘制标题
    draw.text((300, 30), "工业图纸示例", fill='black', font=font_large)
    draw.text((280, 70), "Sample Industrial Drawing", fill='gray', font=font)
    
    # 绘制边框
    draw.rectangle([50, 100, 750, 550], outline='black', width=2)
    
    # 绘制零件轮廓
    draw.rectangle([100, 150, 400, 400], outline='blue', width=2)
    draw.rectangle([450, 200, 700, 500], outline='green', width=2)
    
    # 绘制尺寸标注
    # 水平尺寸
    draw.line([100, 420, 400, 420], fill='red', width=2)
    draw.line([100, 415, 100, 425], fill='red', width=2)
    draw.line([400, 415, 400, 425], fill='red', width=2)
    draw.text((230, 430), "300±0.1", fill='red', font=font)
    
    # 垂直尺寸
    draw.line([420, 150, 420, 400], fill='red', width=2)
    draw.line([415, 150, 425, 150], fill='red', width=2)
    draw.line([415, 400, 425, 400], fill='red', width=2)
    draw.text((430, 260), "250", fill='red', font=font)
    
    # 添加技术说明
    technical_notes = [
        "图纸编号: GD-2023-001",
        "产品名称: 液压阀体",
        "材料: 45#钢",
        "数量: 10件",
        "比例: 1:2",
        "公差: ±0.05mm",
        "表面粗糙度: Ra1.6",
        "热处理: 调质HRC28-32",
        "技术要求: 去毛刺",
        "检验标准: GB/T 1804-m"
    ]
    
    y_pos = 150
    for note in technical_notes:
        draw.text((500, y_pos), note, fill='black', font=font_small)
        y_pos += 30
    
    # 添加特殊符号
    draw.text((200, 180), "Φ50H7", fill='blue', font=font)
    draw.text((350, 300), "R12.5", fill='green', font=font)
    draw.text((150, 350), "M16×1.5", fill='purple', font=font)
    draw.text((300, 250), "45°", fill='orange', font=font)
    draw.text((250, 300), "▽▽", fill='brown', font=font)
    
    # 添加设计信息
    draw.text((100, 500), "设计: 张三", fill='darkgray', font=font_small)
    draw.text((100, 520), "审核: 李四", fill='darkgray', font=font_small)
    draw.text((300, 500), "日期: 2023-10-15", fill='darkgray', font=font_small)
    draw.text((300, 520), "版本: V2.0", fill='darkgray', font=font_small)
    
    # 保存图片
    output_dir = "../frontend/uploads"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "sample_industrial_drawing.png")
    image.save(output_path, "PNG")
    
    print(f"示例图片已创建: {output_path}")
    print("图片尺寸: 800×600 像素")
    print("包含内容:")
    print("  - 工业图纸标题和边框")
    print("  - 零件轮廓")
    print("  - 尺寸标注 (300±0.1, 250)")
    print("  - 技术说明 (材料、公差、粗糙度等)")
    print("  - 特殊符号 (Φ50H7, R12.5, M16×1.5, 45°, ▽▽)")
    print("  - 设计信息")
    
    return output_path

def create_simple_test_image():
    """创建简单的测试图片"""
    width, height = 400, 300
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()
    
    # 添加测试文本
    texts = [
        "OCR测试图片",
        "工业图纸识别",
        "坐标: X=100, Y=150",
        "尺寸: Φ25±0.02",
        "材料: 不锈钢304",
        "数量: 5件"
    ]
    
    y_pos = 50
    for text in texts:
        draw.text((100, y_pos), text, fill='black', font=font)
        y_pos += 40
    
    # 保存图片
    output_dir = "../frontend/uploads"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "test_ocr_image.png")
    image.save(output_path, "PNG")
    
    print(f"测试图片已创建: {output_path}")
    return output_path

if __name__ == "__main__":
    print("创建示例工业图纸图片...")
    print("-" * 50)
    
    # 创建示例图片
    sample_path = create_sample_industrial_drawing()
    
    print("\n" + "-" * 50)
    print("创建简单测试图片...")
    
    # 创建简单测试图片
    test_path = create_simple_test_image()
    
    print("\n" + "-" * 50)
    print("图片创建完成!")
    print(f"示例图片: {sample_path}")
    print(f"测试图片: {test_path}")
    print("\n这些图片可用于测试OCR识别系统。")
    print("在前端界面中上传这些图片进行识别测试。")