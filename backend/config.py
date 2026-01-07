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
    ALLOWED_EXTENSIONS_STR = os.getenv('ALLOWED_EXTENSIONS', 'PNG,JPG,JPEG,BMP,TIFF,GIF')
    ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in ALLOWED_EXTENSIONS_STR.split(',')}
    
    # 百度OCR API配置
    BAIDU_APP_ID = os.getenv('BAIDU_APP_ID', 'your_app_id')
    BAIDU_API_KEY = os.getenv('BAIDU_API_KEY', 'your_api_key')
    BAIDU_SECRET_KEY = os.getenv('BAIDU_SECRET_KEY', 'your_secret_key')
    
    # OCR处理配置
    OCR_USE_MOCK = os.getenv('OCR_USE_MOCK', 'true').lower() == 'true'
    OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', '0.5'))
    
    # 图像预处理配置
    PREPROCESS_ENABLED = os.getenv('PREPROCESS_ENABLED', 'true').lower() == 'true'
    IMAGE_RESIZE_WIDTH = int(os.getenv('IMAGE_RESIZE_WIDTH', '1600'))
    IMAGE_RESIZE_HEIGHT = int(os.getenv('IMAGE_RESIZE_HEIGHT', '1200'))
    
    # 输出配置
    OUTPUT_EXCEL_ENABLED = os.getenv('OUTPUT_EXCEL_ENABLED', 'true').lower() == 'true'
    OUTPUT_JSON_ENABLED = os.getenv('OUTPUT_JSON_ENABLED', 'true').lower() == 'true'
    OUTPUT_VISUALIZATION_ENABLED = os.getenv('OUTPUT_VISUALIZATION_ENABLED', 'true').lower() == 'true'
    
    # 高级配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    ENABLE_CORS = os.getenv('ENABLE_CORS', 'true').lower() == 'true'
    
    @classmethod
    def get_baidu_config(cls):
        """获取百度OCR配置"""
        return {
            'APP_ID': cls.BAIDU_APP_ID,
            'API_KEY': cls.BAIDU_API_KEY,
            'SECRET_KEY': cls.BAIDU_SECRET_KEY,
            'OCR_URL': 'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic',
            'ACCURATE_OCR_URL': 'https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic',
            'FORM_OCR_URL': 'https://aip.baidubce.com/rest/2.0/ocr/v1/form',
            'TABLES_OCR_URL': 'https://aip.baidubce.com/rest/2.0/ocr/v1/table'
        }
    
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
        
        # 检查百度OCR配置（如果不是模拟模式）
        if not cls.OCR_USE_MOCK:
            if cls.BAIDU_APP_ID == 'your_app_id':
                issues.append("百度OCR APP_ID未配置，将使用模拟模式")
                cls.OCR_USE_MOCK = True
            elif cls.BAIDU_API_KEY == 'your_api_key':
                issues.append("百度OCR API_KEY未配置，将使用模拟模式")
                cls.OCR_USE_MOCK = True
            elif cls.BAIDU_SECRET_KEY == 'your_secret_key':
                issues.append("百度OCR SECRET_KEY未配置，将使用模拟模式")
                cls.OCR_USE_MOCK = True
        
        return issues