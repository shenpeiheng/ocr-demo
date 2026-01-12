#!/usr/bin/env python3
"""
OCR工业图片识别系统 - 启动脚本
支持Linux Docker环境
"""

import os
import sys
import argparse
import subprocess
import platform
from config import Config

def is_docker_environment():
    """检测是否在Docker容器中运行"""
    # 方法1: 检查 /.dockerenv 文件
    if os.path.exists('/.dockerenv'):
        return True
    
    # 方法2: 检查 cgroup 信息
    try:
        with open('/proc/self/cgroup', 'r') as f:
            if 'docker' in f.read():
                return True
    except:
        pass
    
    # 方法3: 检查环境变量
    if os.environ.get('DOCKER_CONTAINER') == 'true':
        return True
    
    return False

def setup_environment():
    """设置环境"""
    print("=" * 60)
    print("OCR工业图片识别系统 - 环境设置")
    print("=" * 60)
    
    # 显示环境信息
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"Python版本: {sys.version.split()[0]}")
    print(f"工作目录: {os.getcwd()}")
    
    docker_env = is_docker_environment()
    if docker_env:
        print("运行环境: Docker容器")
        # 在Docker环境中设置PaddleOCR模型目录
        paddleocr_model_dir = '/app/.paddleocr'
        os.environ['PADDLEOCR_MODEL_DIR'] = paddleocr_model_dir
        print(f"PaddleOCR模型目录: {paddleocr_model_dir}")
        
        # 检查模型目录是否存在
        if os.path.exists(paddleocr_model_dir):
            import glob
            model_files = glob.glob(os.path.join(paddleocr_model_dir, '**', '*'), recursive=True)
            print(f"预下载模型文件数: {len(model_files)}")
            if model_files:
                print("✅ OCR模型已预下载")
            else:
                print("⚠️  模型目录为空，将在首次使用时下载")
        else:
            print("⚠️  模型目录不存在，将在首次使用时下载")
    else:
        print("运行环境: 本地系统")
    
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
    
    # 检查依赖 - 在Docker环境中跳过某些检查
    print("\n检查依赖...")
    
    required_packages = [
        ('flask', 'Flask'),
        ('PIL', 'Pillow'),
        ('openpyxl', 'openpyxl'),
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
        except ImportError:
            print(f"  ✗ {package_name}未安装")
            missing_packages.append(package_name)
    
    # PaddleOCR依赖检查
    try:
        import paddleocr
        print("  ✓ paddleocr")
    except ImportError:
        print("  ✗ paddleocr未安装")
        missing_packages.append('paddleocr')
    
    # 在Docker环境中，依赖应该已经安装好
    if missing_packages and docker_env:
        print(f"\n警告: Docker环境中缺少以下包: {', '.join(missing_packages)}")
        print("建议: 重新构建Docker镜像以确保所有依赖正确安装")
    
    print("\n环境设置完成!")
    return True

def install_dependencies():
    """安装依赖"""
    if is_docker_environment():
        print("警告: 在Docker容器中运行，依赖应该已经在镜像构建时安装")
        print("跳过自动依赖安装，如需更新依赖请重新构建镜像")
        return True
    
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

def start_server(host='0.0.0.0', port=5000, debug=False):
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
    
    # Docker环境特定信息
    if is_docker_environment():
        print(f"Docker容器ID: {os.environ.get('HOSTNAME', '未知')}")
        print(f"容器内部端口: {port}")
        print("注意: 外部访问端口可能不同（由docker run -p参数指定）")
    
    print("\nAPI端点:")
    print("  GET  /                    - API信息")
    print("  POST /api/upload          - 上传图片")
    print("  POST /api/process         - 处理图片")
    print("  GET  /api/results/<file>  - 获取结果")
    print("  GET  /api/download/excel/<file> - 下载Excel")
    print("  GET  /api/download/json/<file>  - 下载JSON")
    print("  GET  /uploads/<file>      - 访问上传的文件")
    
    # Docker环境中的额外提示
    if is_docker_environment():
        print("\nDocker容器信息:")
        print("  - 查看日志: docker logs <容器名>")
        print("  - 进入容器: docker exec -it <容器名> /bin/bash")
        print("  - 停止容器: docker stop <容器名>")
        print("  - 重启容器: docker restart <容器名>")
    
    print("\n按 Ctrl+C 停止服务器")
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
        # 在Docker环境或非调试模式下禁用reloader
        use_reloader = debug and not is_docker_environment()
        app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
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
        epilog='在Docker环境中运行时，建议使用环境变量配置而非命令行参数'
    )
    parser.add_argument('--install', action='store_true', help='安装依赖（在Docker中不推荐）')
    parser.add_argument('--host', default='0.0.0.0', help='服务器主机地址（默认: 0.0.0.0）')
    parser.add_argument('--port', type=int, default=5000, help='服务器端口（默认: 5000）')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--docker-info', action='store_true', help='显示Docker环境信息')
    
    args = parser.parse_args()
    
    # 显示Docker信息（如果请求）
    if args.docker_info:
        print("Docker环境检测:")
        print(f"  在Docker中运行: {'是' if is_docker_environment() else '否'}")
        print(f"  容器主机名: {os.environ.get('HOSTNAME', '未设置')}")
        print(f"  环境变量PORT: {os.environ.get('PORT', '未设置')}")
        print(f"  环境变量DEBUG: {os.environ.get('DEBUG', '未设置')}")
        print(f"  工作目录: {os.getcwd()}")
        return
    
    # Docker环境中的警告
    if is_docker_environment() and args.install:
        print("警告: 在Docker容器中手动安装依赖可能不是最佳实践")
        print("建议: 重新构建Docker镜像以包含所有依赖")
        response = input("是否继续安装? (y/N): ")
        if response.lower() != 'y':
            print("取消安装依赖")
            args.install = False
    
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
        if is_docker_environment():
            print("提示: 使用 'docker stop <容器名>' 停止Docker容器")
    except Exception as e:
        print(f"\n错误: {e}")
        print(f"错误类型: {type(e).__name__}")
        
        # 提供Docker特定的故障排除建议
        if is_docker_environment():
            print("\nDocker故障排除建议:")
            print("1. 检查容器日志: docker logs <容器名>")
            print("2. 检查端口映射: docker ps")
            print("3. 进入容器调试: docker exec -it <容器名> /bin/bash")
            print("4. 检查卷挂载: docker inspect <容器名>")
        
        sys.exit(1)

if __name__ == '__main__':
    main()