"""
配置文件 - OCR工业图片识别系统
"""

import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """应用配置类"""
    
    # Flask配置
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '2147483648'))  # 2GB 默认值，支持大视频文件
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    PORT = int(os.getenv('PORT', '5000'))
    
    # 文件上传配置
    upload_folder_from_env = os.getenv('UPLOAD_FOLDER')
    if upload_folder_from_env:
        UPLOAD_FOLDER = upload_folder_from_env
    else:
        UPLOAD_FOLDER = os.path.abspath(os.path.join('..', 'frontend', 'uploads'))
    ALLOWED_EXTENSIONS_STR = os.getenv('ALLOWED_EXTENSIONS', 'PNG,JPG,JPEG,BMP,TIFF,GIF,PDF')
    ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in ALLOWED_EXTENSIONS_STR.split(',')}
    
    # PDF处理配置
    PDF_MAX_PAGES = int(os.getenv('PDF_MAX_PAGES', '50'))  # 最大处理页数
    PDF_DPI = int(os.getenv('PDF_DPI', '200'))  # PDF转换DPI
    PDF_ENGINE = os.getenv('PDF_ENGINE', 'ocr').strip().lower()  # ocr 或 mineru
    MINERU_REQUEST_MODE = os.getenv('MINERU_REQUEST_MODE', 'modelscope_vl').strip().lower()

    # MinerU 官方 API 配置
    MINERU_OFFICIAL_API_URL = os.getenv('MINERU_OFFICIAL_API_URL', 'https://mineru.net/api/v4/extract').strip()
    MINERU_OFFICIAL_TOKEN = os.getenv('MINERU_OFFICIAL_TOKEN', '').strip()

    # ==================== 通用 LLM 配置 ====================
    # 通过 LLM_MODELS 环境变量（JSON 数组格式）配置所有可用模型，例如：
    # LLM_MODELS=[{"key":"deepseek","model":"glm-5.1","label":"DeepSeek-V4-Flash (推荐)","default":true,"url":"https://api-inference.modelscope.cn/v1","api_key":"sk-xxx"},{"key":"qwen","model":"Qwen/Qwen2.5-72B-Instruct","label":"通义千问","url":"https://api-inference.modelscope.cn/v1","api_key":"sk-xxx"}]
    # - key: 前端传递的模型别名
    # - model: 实际调用 API 时使用的模型 ID
    # - label: 前端下拉框显示的文本
    # - default: 是否默认选中（只有一个生效）
    # - url: 该模型专属的 API 地址（必填，每个模型独立配置）
    # - api_key: 该模型专属的 API Key（必填，每个模型独立配置）

    @classmethod
    def _parse_llm_models(cls):
        """解析 LLM 模型配置。优先从 llm_models.json 读取，否则回退到 LLM_MODELS 环境变量。"""
        # 优先读取 JSON 配置文件（方便多行编辑）
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'llm_models.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    models = json.loads(f.read())
                if isinstance(models, list) and models:
                    return models
            except (json.JSONDecodeError, OSError):
                pass

        # 回退：LLM_MODELS 环境变量
        raw = os.getenv('LLM_MODELS', '').strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        if raw:
            try:
                models = json.loads(raw)
                if isinstance(models, list) and models:
                    return models
            except json.JSONDecodeError:
                pass
        return []

    # 延迟解析，避免类体执行时 json 未导入
    _llm_models_cache = None

    @classmethod
    def get_llm_models(cls):
        """返回已配置的 LLM 模型列表。"""
        if cls._llm_models_cache is None:
            cls._llm_models_cache = cls._parse_llm_models()
        return cls._llm_models_cache

    @classmethod
    def get_llm_model_map(cls):
        """返回 {key: model_id} 映射。"""
        return {m['key']: m['model'] for m in cls.get_llm_models()}

    @classmethod
    def get_llm_default_model(cls):
        """返回默认模型 key。"""
        models = cls.get_llm_models()
        for m in models:
            if m.get('default'):
                return m['key']
        return models[0]['key'] if models else ''

    @classmethod
    def resolve_llm_model(cls, model_key: str = '') -> str:
        """将前端传入的模型 key 解析为真实模型 ID，未知时回退到默认模型。"""
        models = cls.get_llm_models()
        model_map = cls.get_llm_model_map()
        key = str(model_key or '').strip()
        if key and key in model_map:
            return model_map[key]
        # 回退到默认模型
        default_key = cls.get_llm_default_model()
        return model_map.get(default_key, models[0]['model'] if models else '')

    @classmethod
    def resolve_llm_url(cls, model_key: str = '') -> str:
        """根据模型 key 获取对应的 API URL。"""
        models = cls.get_llm_models()
        key = str(model_key or '').strip()
        if key:
            for m in models:
                if m['key'] == key and m.get('url'):
                    return m['url'].rstrip('/')
        # 回退到默认模型
        default_key = cls.get_llm_default_model()
        for m in models:
            if m['key'] == default_key:
                return m.get('url', '').rstrip('/')
        return (models[0].get('url', '') if models else '').rstrip('/')

    @classmethod
    def resolve_llm_key(cls, model_key: str = '') -> str:
        """根据模型 key 获取对应的 API Key。"""
        models = cls.get_llm_models()
        key = str(model_key or '').strip()
        if key:
            for m in models:
                if m['key'] == key and m.get('api_key'):
                    return m['api_key']
        # 回退到默认模型
        default_key = cls.get_llm_default_model()
        for m in models:
            if m['key'] == default_key:
                return m.get('api_key', '')
        return models[0].get('api_key', '') if models else ''

    # 通用 LLM 请求兜底配置
    LLM_REQUEST_MAX_TOKENS = int(os.getenv('LLM_REQUEST_MAX_TOKENS', '16000'))
    LLM_REQUEST_TIMEOUT = int(os.getenv('LLM_REQUEST_TIMEOUT', '900'))

    # Oracle PRD 生成配置
    ORACLE_PRD_ANALYSIS_MAX_TOKENS = int(os.getenv('ORACLE_PRD_ANALYSIS_MAX_TOKENS', '12000'))
    ORACLE_PRD_ANALYSIS_TIMEOUT = int(os.getenv('ORACLE_PRD_ANALYSIS_TIMEOUT', '900'))
    ORACLE_PRD_BLUEPRINT_MAX_TOKENS = int(os.getenv('ORACLE_PRD_BLUEPRINT_MAX_TOKENS', '20000'))
    ORACLE_PRD_BLUEPRINT_TIMEOUT = int(os.getenv('ORACLE_PRD_BLUEPRINT_TIMEOUT', '1200'))
    ORACLE_PRD_HTML_MAX_TOKENS = int(os.getenv('ORACLE_PRD_HTML_MAX_TOKENS', '32000'))
    ORACLE_PRD_HTML_TIMEOUT = int(os.getenv('ORACLE_PRD_HTML_TIMEOUT', '1800'))

    # MinerU 其他配置
    _MINERU_DEFAULT_API_URL = (
        os.getenv('MODELSCOPE_BASE_URL', 'https://api-inference.modelscope.cn/v1')
        if MINERU_REQUEST_MODE in {'modelscope', 'modelscope_vl', 'openai_vl'}
        else ''
    )
    MINERU_API_URL = os.getenv(
        'MINERU_API_URL',
        _MINERU_DEFAULT_API_URL
    ).strip()
    MINERU_API_KEY = os.getenv('MINERU_API_KEY', os.getenv('MODELSCOPE_API_KEY', '')).strip()
    MINERU_MODEL = os.getenv('MINERU_MODEL', 'OpenDataLab/MinerU2.5-2509-1.2B').strip()
    MINERU_TIMEOUT = int(os.getenv('MINERU_TIMEOUT', '300'))

    # 文件上传服务配置（用于 MinerU 官方 API）
    MINERU_FILE_UPLOAD_SERVICE = os.getenv('MINERU_FILE_UPLOAD_SERVICE', 'transfer.sh').strip()

    # PaddleOCR 在线 API 配置
    PADDLEOCR_ONLINE_API_URL = os.getenv('PADDLEOCR_ONLINE_API_URL', 'https://paddleocr.aistudio-app.com/api/v2/ocr/jobs').strip()
    PADDLEOCR_ONLINE_TOKEN = os.getenv('PADDLEOCR_ONLINE_TOKEN', '').strip()
    PADDLEOCR_MODE = os.getenv('PADDLEOCR_MODE', 'online').strip().lower()

    # ==================== ModelScope / OCR-VL 配置（旧版兼容） ====================
    # OCR 引擎和 VL 处理器仍使用这些环境变量，不走 LLM_MODELS
    MODELSCOPE_API_KEY = os.getenv('MODELSCOPE_API_KEY', '').strip()
    MODELSCOPE_BASE_URL = os.getenv('MODELSCOPE_BASE_URL', 'https://api-inference.modelscope.cn/v1').strip()
    MODELSCOPE_MODEL = os.getenv('MODELSCOPE_MODEL', 'Qwen/Qwen3-VL-235B-A22B-Instruct').strip()

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

    @classmethod
    def get_model_options(cls):
        """获取前端可用的模型配置（兼容旧 /api/ui/model-options 接口）"""
        return {
            m['key']: {
                'model': m['model'],
                'label': m.get('label', m['key']),
            }
            for m in cls.get_llm_models()
        }
