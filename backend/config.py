"""
配置文件 - OCR工业图片识别系统
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """应用配置类"""
    
    # Flask配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'ocr-industrial-demo-secret-key')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '16777216'))  # 16MB默认值
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    PORT = int(os.getenv('PORT', '5000'))
    
    # 文件上传配置
    UPLOAD_FOLDER = os.path.join('..', 'frontend', 'uploads')
    ALLOWED_EXTENSIONS_STR = os.getenv('ALLOWED_EXTENSIONS', 'PNG,JPG,JPEG,BMP,TIFF,GIF,PDF')
    ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in ALLOWED_EXTENSIONS_STR.split(',')}
    
    # PDF处理配置
    PDF_MAX_PAGES = int(os.getenv('PDF_MAX_PAGES', '50'))  # 最大处理页数
    PDF_DPI = int(os.getenv('PDF_DPI', '200'))  # PDF转换DPI
    
    # CORS配置
    ENABLE_CORS = os.getenv('ENABLE_CORS', 'true').lower() == 'true'
    
    @classmethod
    def validate_config(cls):
        """验证配置"""
        issues = []
        
        # 检查上传目录
        if not os.path.exists(cls.UPLOAD_FOLDER):
            try:
                os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
            except Exception as e:
                issues.append(f"无法创建上传目录: {e}")
        
        return issues