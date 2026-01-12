#!/usr/bin/env python3
"""
测试Docker构建配置
"""

import os
import sys
import subprocess

def check_docker_installed():
    """检查Docker是否安装"""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker已安装: {result.stdout.strip()}")
            return True
        else:
            print("❌ Docker未安装或不可用")
            return False
    except FileNotFoundError:
        print("❌ Docker未安装")
        return False

def check_docker_compose_installed():
    """检查Docker Compose是否安装"""
    try:
        result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker Compose已安装: {result.stdout.strip()}")
            return True
        else:
            print("❌ Docker Compose未安装或不可用")
            return False
    except FileNotFoundError:
        print("❌ Docker Compose未安装")
        return False

def check_dockerfile():
    """检查Dockerfile是否存在且配置正确"""
    dockerfile_path = 'Dockerfile'
    if os.path.exists(dockerfile_path):
        print(f"✅ Dockerfile存在: {dockerfile_path}")
        
        # 检查关键配置
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('FROM python:3.9-slim', '使用Python 3.9基础镜像'),
            ('paddlepaddle==3.2.2', '安装PaddlePaddle 3.2.2'),
            ('paddleocr==3.3.2', '安装PaddleOCR 3.3.2'),
            ('backend/preload_ocr_models.py', '模型预下载脚本'),
            ('CMD ["/opt/venv/bin/python", "backend/run.py"', '启动命令')
        ]
        
        for check_str, description in checks:
            if check_str in content:
                print(f"  ✅ {description}")
            else:
                print(f"  ⚠️  {description} 未找到")
        
        return True
    else:
        print(f"❌ Dockerfile不存在: {dockerfile_path}")
        return False

def check_docker_compose():
    """检查docker-compose.yml是否存在且配置正确"""
    compose_path = 'docker-compose.yml'
    if os.path.exists(compose_path):
        print(f"✅ docker-compose.yml存在: {compose_path}")
        
        # 检查关键配置
        with open(compose_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('version:', '版本定义'),
            ('ocr-app:', '服务定义'),
            ('ports:', '端口映射'),
            ('volumes:', '卷挂载')
        ]
        
        for check_str, description in checks:
            if check_str in content:
                print(f"  ✅ {description}")
            else:
                print(f"  ⚠️  {description} 未找到")
        
        return True
    else:
        print(f"❌ docker-compose.yml不存在: {compose_path}")
        return False

def check_requirements():
    """检查关键文件是否存在"""
    required_files = [
        'backend/run.py',
        'backend/app.py',
        'backend/paddle_ocr_processor.py',
        'backend/ocr_processor.py',
        'backend/config.py',
        'backend/preload_ocr_models.py',
        'frontend/index.html'
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} 存在")
        else:
            print(f"❌ {file_path} 不存在")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 60)
    print("Docker构建配置测试")
    print("=" * 60)
    
    # 检查Docker环境
    docker_ok = check_docker_installed()
    compose_ok = check_docker_compose_installed()
    
    print("\n" + "-" * 60)
    print("文件配置检查")
    print("-" * 60)
    
    # 检查文件
    dockerfile_ok = check_dockerfile()
    compose_file_ok = check_docker_compose()
    requirements_ok = check_requirements()
    
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    all_passed = all([
        docker_ok,
        compose_ok,
        dockerfile_ok,
        compose_file_ok,
        requirements_ok
    ])
    
    if all_passed:
        print("✅ 所有检查通过！Docker构建配置正确。")
        print("\n构建命令:")
        print("  1. 构建镜像: docker build -t ocr-industrial-demo .")
        print("  2. 运行容器: docker run -d -p 5000:5000 --name ocr-demo ocr-industrial-demo")
        print("  3. 使用docker-compose: docker-compose up -d")
        print("\n访问应用: http://localhost:5000")
    else:
        print("⚠️  部分检查未通过，请修复上述问题。")
    
    print("=" * 60)
    
    return all_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)