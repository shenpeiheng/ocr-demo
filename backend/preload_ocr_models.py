#!/usr/bin/env python3
"""
PaddleOCR模型预下载脚本
在Docker构建时运行，避免首次运行时下载模型
"""

import os
import sys

def main():
    """主函数"""
    print("=" * 60)
    print("PaddleOCR模型预下载")
    print("=" * 60)
    
    # 设置模型目录
    model_dir = "/app/.paddleocr"
    os.environ["PADDLEOCR_MODEL_DIR"] = model_dir
    print(f"模型目录: {model_dir}")
    
    # 创建目录
    os.makedirs(model_dir, exist_ok=True)
    
    try:
        from paddleocr import PaddleOCR
        
        print("\n正在预下载中文OCR模型 (PP-OCRv5)...")
        # 预下载中文模型 - 使用PP-OCRv5
        ocr_ch = PaddleOCR(
            lang='ch',
            ocr_version='PP-OCRv5',  # 使用PP-OCRv5版本
            text_detection_model_dir=os.path.join(model_dir, 'det'),
            text_recognition_model_dir=os.path.join(model_dir, 'rec'),
            textline_orientation_model_dir=os.path.join(model_dir, 'cls'),
        )
        print("✅ 中文OCR模型 (PP-OCRv5) 预下载完成")
        
        print("\n正在预下载英文OCR模型 (PP-OCRv5)...")
        # 预下载英文模型 - 使用PP-OCRv5
        ocr_en = PaddleOCR(
            lang='en',
            ocr_version='PP-OCRv5',  # 使用PP-OCRv5版本
            text_detection_model_dir=os.path.join(model_dir, 'det'),
            text_recognition_model_dir=os.path.join(model_dir, 'rec'),
            textline_orientation_model_dir=os.path.join(model_dir, 'cls'),
        )
        print("✅ 英文OCR模型 (PP-OCRv5) 预下载完成")
        
        # 验证模型目录中有文件
        import glob
        model_files = glob.glob(os.path.join(model_dir, '**', '*'), recursive=True)
        print(f"\n模型文件统计:")
        print(f"  总文件数: {len(model_files)}")
        
        if model_files:
            # 按类型统计
            file_types = {}
            for f in model_files:
                ext = os.path.splitext(f)[1]
                file_types[ext] = file_types.get(ext, 0) + 1
            
            print("  文件类型分布:")
            for ext, count in file_types.items():
                if ext:  # 忽略空扩展名
                    print(f"    {ext}: {count}个")
            
            # 显示前几个文件
            print("\n  示例文件:")
            for f in model_files[:3]:
                rel_path = os.path.relpath(f, model_dir)
                print(f"    - {rel_path}")
            if len(model_files) > 3:
                print(f"    ... 还有 {len(model_files) - 3} 个文件")
        
        print("\n" + "=" * 60)
        print("✅ 所有OCR模型预下载成功")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"\n❌ 导入PaddleOCR失败: {e}")
        print("请检查paddleocr是否安装正确")
        return False
    except Exception as e:
        print(f"\n⚠️ 模型预下载过程中出现错误: {e}")
        print("注意: 模型将在首次运行时自动下载")
        print("这不会影响容器构建，可以继续")
        return True  # 返回True，允许构建继续

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)