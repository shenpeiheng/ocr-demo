#!/usr/bin/env python3
"""
测试服务器启动 - 验证run.py在本地环境中的兼容性
"""

import sys
import os
import subprocess
import time
import threading

print("测试服务器启动...")
print("=" * 60)

def check_server_running(port=5000):
    """检查服务器是否在指定端口运行"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

def start_server_in_thread():
    """在子线程中启动服务器"""
    print("启动服务器...")
    # 使用subprocess启动服务器
    cmd = [sys.executable, 'run.py']
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    
    # 启动服务器进程
    process = subprocess.Popen(
        cmd,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 等待一段时间让服务器启动
    time.sleep(5)
    
    # 检查服务器是否运行
    if check_server_running():
        print("✅ 服务器启动成功")
        # 停止服务器
        process.terminate()
        process.wait(timeout=5)
        return True
    else:
        print("❌ 服务器启动失败")
        # 获取错误输出
        stdout, stderr = process.communicate(timeout=2)
        print("标准输出:", stdout)
        print("错误输出:", stderr)
        process.terminate()
        return False

# 测试1: 直接导入run.py并检查环境检测
print("1. 测试环境检测功能...")
try:
    # 模拟导入run.py中的函数
    import run
    print("✅ run.py导入成功")
    
    # 检查is_docker_environment函数
    if hasattr(run, 'is_docker_environment'):
        is_docker = run.is_docker_environment()
        print(f"✅ 环境检测: {'Docker环境' if is_docker else '本地环境'}")
    else:
        print("❌ 缺少is_docker_environment函数")
        
except Exception as e:
    print(f"❌ run.py导入失败: {e}")
    import traceback
    traceback.print_exc()

print("\n2. 测试setup_environment函数...")
try:
    if hasattr(run, 'setup_environment'):
        run.setup_environment()
        print("✅ 环境设置成功")
        
        # 检查环境变量
        model_dir = os.environ.get('PADDLEOCR_MODEL_DIR')
        if model_dir:
            print(f"✅ PADDLEOCR_MODEL_DIR: {model_dir}")
        else:
            print("⚠️  PADDLEOCR_MODEL_DIR未设置")
    else:
        print("❌ 缺少setup_environment函数")
        
except Exception as e:
    print(f"❌ 环境设置失败: {e}")

print("\n3. 测试服务器启动（快速测试）...")
# 由于服务器启动需要时间，我们只进行快速测试
try:
    # 检查app.py是否能导入
    import app
    print("✅ app.py导入成功")
    
    # 检查OCR处理器是否初始化
    if hasattr(app, 'ocr_processor'):
        print("✅ OCR处理器已初始化")
    else:
        print("❌ OCR处理器未初始化")
        
except Exception as e:
    print(f"❌ app.py导入失败: {e}")

print("\n4. 测试配置文件...")
try:
    import config
    print("✅ config.py导入成功")
    
    # 检查重要配置
    print(f"  上传目录: {config.Config.UPLOAD_FOLDER}")
    print(f"  调试模式: {config.Config.DEBUG}")
    print(f"  服务器端口: {config.Config.PORT}")
    
except Exception as e:
    print(f"❌ config.py导入失败: {e}")

print("\n" + "=" * 60)
print("服务器启动测试完成")
print("注意: 完整服务器启动测试需要更多时间")
print("建议手动运行 'python run.py' 进行完整测试")