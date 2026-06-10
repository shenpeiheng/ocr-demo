"""
OCR 工业图片识别系统后端入口。
"""

from flask import send_from_directory
from app_core import app, ocr_processor
from config import Config
from routes.ocr_routes import ocr_bp
from routes.pdf_routes import pdf_bp
from routes.vision_routes import preload_keypoint, preload_license_ocr, preload_safety_helmet, vision_bp


app.register_blueprint(ocr_bp)
app.register_blueprint(pdf_bp)
app.register_blueprint(vision_bp)


@app.route('/mineru_results/<path:filename>')
def serve_mineru_results(filename):
    """提供 MinerU 解析结果静态文件"""
    import os
    results_dir = Config.UPLOAD_FOLDER
    return send_from_directory(results_dir, filename)


if __name__ == "__main__":
    print("启动OCR工业图片识别系统...")
    print(f"上传目录: {app.config['UPLOAD_FOLDER']}")
    print(f"调试模式: {'开启' if Config.DEBUG else '关闭'}")
    print(f"CORS支持: {'开启' if Config.ENABLE_CORS else '关闭'}")

    engine_info = ocr_processor.get_engine_info()
    print(f"OCR引擎: {engine_info['current_engine']} (类型: {engine_info['engine_type']})")
    print(f"PaddleOCR可用: {engine_info['paddleocr_available']}")
    print(f"OpenAI VL可用: {engine_info['openai_vl_available']}")
    print("\n" + "=" * 60)
    print("[启动预加载] 正在预加载各功能模型...")
    print("=" * 60)
    if Config.PADDLEOCR_MODE == 'local':
        preload_license_ocr()
    else:
        print("[LicensePlate] 在线模式，跳过本地模型预加载")
    preload_safety_helmet()
    preload_keypoint()
    print("=" * 60)
    print("[启动预加载] 所有模型预加载完成")
    print("=" * 60 + "\n")
    print(f"API服务运行在 http://127.0.0.1:{Config.PORT}")

    config_issues = Config.validate_config()
    if config_issues:
        print("配置警告:")
        for issue in config_issues:
            print(f"  - {issue}")

    app.run(debug=Config.DEBUG, host="0.0.0.0", port=Config.PORT)
