#!/usr/bin/env python3
"""
OCR工业图片识别系统 - 启动脚本
"""

import os
import sys
import argparse
from config import Config

def setup_environment():
    """设置环境"""
    print("=" * 60)
    print("OCR工业图片识别系统 - 环境设置")
    print("=" * 60)
    
    # 检查Python版本
    if sys.version_info < (3, 7):
        print("错误: 需要Python 3.7或更高版本")
        sys.exit(1)
    
    # 验证配置
    issues = Config.validate_config()
    
    if issues:
        print("配置检查发现以下问题:")
        for issue in issues:
            print(f"  - {issue}")
    
    # 检查依赖
    print("\n检查依赖...")
    try:
        import flask
        print(f"  ✓ Flask {flask.__version__}")
    except ImportError:
        print("  ✗ Flask未安装，请运行: pip install -r requirements.txt")
    
    try:
        import PIL
        print(f"  ✓ Pillow {PIL.__version__}")
    except ImportError:
        print("  ✗ Pillow未安装，请运行: pip install -r requirements.txt")
    
    try:
        import openpyxl
        print(f"  ✓ openpyxl {openpyxl.__version__}")
    except ImportError:
        print("  ✗ openpyxl未安装，请运行: pip install -r requirements.txt")
    
    if not Config.OCR_USE_MOCK:
        try:
            from aip import AipOcr
            print("  ✓ baidu-aip")
        except ImportError:
            print("  ✗ baidu-aip未安装，请运行: pip install baidu-aip")
            Config.OCR_USE_MOCK = True
    
    print("\n环境设置完成!")
    return True

def install_dependencies():
    """安装依赖"""
    print("安装Python依赖...")
    
    requirements_file = "requirements.txt"
    if os.path.exists(requirements_file):
        os.system(f"pip install -r {requirements_file}")
        print("依赖安装完成!")
    else:
        print(f"错误: 找不到 {requirements_file}")
        return False
    
    return True

def start_server(host='0.0.0.0', port=5000, debug=False):
    """启动服务器"""
    print("\n" + "=" * 60)
    print("启动OCR工业图片识别系统")
    print("=" * 60)
    
    print(f"服务器地址: http://{host}:{port}")
    print(f"上传目录: {Config.UPLOAD_FOLDER}")
    print(f"OCR模式: {'模拟数据' if Config.OCR_USE_MOCK else '百度OCR API'}")
    
    if Config.OCR_USE_MOCK:
        print("注意: 当前使用模拟OCR数据，要使用真实百度OCR API:")
        print("  1. 访问 https://ai.baidu.com/ 注册并创建应用")
        print("  2. 获取APP_ID, API_KEY, SECRET_KEY")
        print("  3. 在 .env 文件中配置这些密钥")
        print("  4. 设置 OCR_USE_MOCK=false")
    
    print("\nAPI端点:")
    print("  GET  /                    - API信息")
    print("  POST /api/upload          - 上传图片")
    print("  POST /api/process         - 处理图片")
    print("  GET  /api/results/<file>  - 获取结果")
    print("  GET  /api/download/excel/<file> - 下载Excel")
    print("  GET  /api/download/json/<file>  - 下载JSON")
    print("  GET  /uploads/<file>      - 访问上传的文件")
    
    print("\n前端界面:")
    print(f"  http://{host}:{port}/../frontend/index.html")
    
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    # 导入并启动应用
    from app import app
    app.run(host=host, port=port, debug=debug)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='OCR工业图片识别系统')
    parser.add_argument('--install', action='store_true', help='安装依赖')
    parser.add_argument('--host', default='0.0.0.0', help='服务器主机地址')
    parser.add_argument('--port', type=int, default=5000, help='服务器端口')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 设置环境
    if not setup_environment():
        sys.exit(1)
    
    # 安装依赖（如果指定）
    if args.install:
        if not install_dependencies():
            sys.exit(1)
    
    # 启动服务器
    try:
        start_server(args.host, args.port, args.debug)
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()