#!/usr/bin/env python3
"""
OCR工业图片识别系统 - 启动脚本
"""

import os
import sys
import argparse
import subprocess
import platform
from config import Config

def setup_environment():
    """设置环境"""
    print("=" * 60)
    print("OCR工业图片识别系统 - 环境设置")
    print("=" * 60)
    
    # 显示环境信息
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version.split()[0]}")
    print(f"工作目录: {os.getcwd()}")
    
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
    
    required_packages = [
        ('flask', 'Flask'),
        ('PIL', 'Pillow'),
        ('openpyxl', 'openpyxl'),
        ('paddleocr', 'paddleocr'),
    ]
    
    missing_packages = []
    
    for import_name, package_name in required_packages:
        try:
            if import_name == 'flask':
                import flask
                print(f"  ✓ Flask {flask.__version__}")
            elif import_name == 'PIL':
                import PIL
                print(f"  ✓ Pillow {PIL.__version__}")
            elif import_name == 'openpyxl':
                import openpyxl
                print(f"  ✓ openpyxl {openpyxl.__version__}")
            elif import_name == 'paddleocr':
                import paddleocr
                print(f"  ✓ paddleocr {paddleocr.__version__}")
        except ImportError:
            print(f"  ✗ {package_name}未安装")
            missing_packages.append(package_name)
    
    print("\n环境设置完成!")
    return True

def install_dependencies():
    """安装依赖"""
    
    print("安装Python依赖...")
    
    requirements_file = "requirements.txt"
    if os.path.exists(requirements_file):
        print(f"使用 {requirements_file} 安装依赖...")
        
        # 使用 subprocess 而不是 os.system 以获得更好的控制
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", requirements_file],
                capture_output=True,
                text=True,
                check=True
            )
            print("依赖安装完成!")
            
            # 显示安装摘要
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:  # 显示最后5行
                    if line.strip():
                        print(f"  {line}")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"依赖安装失败: {e}")
            if e.stderr:
                print("错误输出:")
                for line in e.stderr.strip().split('\n')[-10:]:
                    if line.strip():
                        print(f"  {line}")
            return False
        except Exception as e:
            print(f"安装过程中发生错误: {e}")
            return False
    else:
        print(f"错误: 找不到 {requirements_file}")
        print(f"当前目录: {os.getcwd()}")
        print(f"尝试查找文件...")
        
        # 尝试在父目录中查找
        parent_requirements = os.path.join("..", "requirements.txt")
        if os.path.exists(parent_requirements):
            print(f"在父目录中找到 {parent_requirements}")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", parent_requirements],
                    check=True
                )
                print("依赖安装完成!")
                return True
            except subprocess.CalledProcessError as e:
                print(f"依赖安装失败: {e}")
                return False
        
        return False

def start_server(host='0.0.0.0', port=5000, debug=True):
    """启动服务器"""
    print("\n" + "=" * 60)
    print("启动OCR工业图片识别系统")
    print("=" * 60)
    
    # 获取实际端口（环境变量优先）
    env_port = os.environ.get('PORT')
    if env_port and env_port.isdigit():
        port = int(env_port)
        print(f"使用环境变量PORT: {port}")
    
    print(f"服务器地址: http://{host}:{port}")
    print(f"上传目录: {Config.UPLOAD_FOLDER}")
    print(f"OCR引擎: PaddleOCR PP-OCRv5")
    
    print("\nAPI端点:")
    print("  GET  /                    - API信息")
    print("  POST /api/upload          - 上传图片")
    print("  POST /api/process         - 处理图片")
    print("  GET  /api/results/<file>  - 获取结果")
    print("  GET  /api/download/excel/<file> - 下载Excel")
    print("  GET  /api/download/json/<file>  - 下载JSON")
    print("  GET  /uploads/<file>      - 访问上传的文件")
    
    print("=" * 60)
    
    # 检查上传目录权限（在Docker中特别重要）
    upload_dir = Config.UPLOAD_FOLDER
    if not os.path.exists(upload_dir):
        try:
            os.makedirs(upload_dir, exist_ok=True)
            print(f"创建上传目录: {upload_dir}")
        except Exception as e:
            print(f"警告: 无法创建上传目录 {upload_dir}: {e}")
    
    # 检查目录写入权限
    try:
        test_file = os.path.join(upload_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"上传目录可写: {upload_dir}")
    except Exception as e:
        print(f"警告: 上传目录不可写 {upload_dir}: {e}")
        print("可能导致文件上传失败")
    
    # 导入并启动应用
    try:
        from app import app
        
        # 设置Flask配置
        app.config['ENV'] = 'production' if not debug else 'development'
        
        print(f"\n启动Flask应用 (环境: {app.config['ENV']})...")
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except ImportError as e:
        print(f"错误: 无法导入应用模块: {e}")
        print("请确保 app.py 文件存在且正确")
        sys.exit(1)
    except Exception as e:
        print(f"启动服务器时发生错误: {e}")
        sys.exit(1)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='OCR工业图片识别系统',
        epilog='建议使用环境变量配置而非命令行参数'
    )
    parser.add_argument('--install', action='store_true', help='安装依赖（在Docker中不推荐）')
    parser.add_argument('--host', default='0.0.0.0', help='服务器主机地址（默认: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=5000, help='服务器端口（默认: 5000）')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--no-debug', action='store_true', help='禁用调试模式')
    parser.add_argument('--docker-info', action='store_true', help='显示Docker环境信息')
    
    args = parser.parse_args()
    
    # 设置环境
    if not setup_environment():
        sys.exit(1)
    
    # 安装依赖（如果指定）
    if args.install:
        if not install_dependencies():
            sys.exit(1)
    
    # 确定debug模式
    # 如果指定了--debug，则启用debug模式
    # 如果指定了--no-debug，则禁用debug模式
    # 如果两者都没指定，则使用Config.DEBUG的值
    if args.debug:
        debug_mode = True
        print("调试模式: 启用 (通过命令行参数 --debug)")
    elif args.no_debug:
        debug_mode = False
        print("调试模式: 禁用 (通过命令行参数 --no-debug)")
    else:
        # 使用配置中的DEBUG值
        debug_mode = Config.DEBUG
        print(f"调试模式: {'启用' if debug_mode else '禁用'} (通过环境变量/配置文件)")
    
    # 启动服务器
    try:
        start_server(args.host, args.port, debug_mode)
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
    except Exception as e:
        print(f"\n错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        sys.exit(1)

if __name__ == '__main__':
    main()