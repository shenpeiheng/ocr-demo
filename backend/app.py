"""
OCR工业图片识别系统 - 后端API服务
支持上传工业图纸图片，识别内容并输出坐标和内容
"""
import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import openpyxl
from openpyxl import Workbook
from PIL import Image
import numpy as np
import cv2

# 导入配置和OCR处理器
from config import Config
from ocr_processor import OCRProcessor

# 初始化Flask应用
app = Flask(__name__, static_folder='../frontend', static_url_path='')

# 根据配置决定是否启用CORS
if Config.ENABLE_CORS:
    CORS(app)  # 允许跨域请求

# 应用配置
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = Config.ALLOWED_EXTENSIONS
app.config['SECRET_KEY'] = Config.SECRET_KEY

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 初始化OCR处理器
ocr_processor = OCRProcessor()

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    """前端页面"""
    return send_from_directory('../frontend', 'index.html')

@app.route('/api')
def api_index():
    """API根路径"""
    return jsonify({
        'name': 'OCR工业图片识别系统',
        'version': '1.0.0',
        'description': '工业图纸OCR识别API服务',
        'endpoints': {
            '/api/upload': '上传图片文件',
            '/api/process': '处理已上传的图片',
            '/api/results': '获取识别结果',
            '/api/download/excel': '下载Excel格式结果',
            '/api/download/json': '下载JSON格式结果'
        }
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传图片文件"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件部分'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if file and allowed_file(file.filename):
        # 生成唯一文件名
        original_filename = secure_filename(file.filename)
        file_ext = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        # 保存文件
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # 返回文件信息
        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'filename': unique_filename,
            'original_filename': original_filename,
            'filepath': filepath,
            'upload_time': datetime.now().isoformat()
        })
    
    return jsonify({'error': '文件类型不支持'}), 400

@app.route('/api/process', methods=['POST'])
def process_image():
    """处理图片并进行OCR识别"""
    data = request.json
    if not data or 'filename' not in data:
        return jsonify({'error': '缺少文件名参数'}), 400
    
    filename = data['filename']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        # 使用OCR处理器识别图片
        results = ocr_processor.process_image(filepath)
        
        # 保存结果到JSON文件
        result_filename = f"result_{os.path.splitext(filename)[0]}.json"
        result_path = os.path.join(app.config['UPLOAD_FOLDER'], result_filename)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 生成Excel文件
        excel_filename = f"result_{os.path.splitext(filename)[0]}.xlsx"
        excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_filename)
        generate_excel(results, excel_path)
        
        return jsonify({
            'success': True,
            'message': '图片处理成功',
            'filename': filename,
            'results': results,
            'result_files': {
                'json': result_filename,
                'excel': excel_filename
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500

@app.route('/api/results/<filename>')
def get_results(filename):
    """获取识别结果"""
    result_path = os.path.join(app.config['UPLOAD_FOLDER'], f"result_{os.path.splitext(filename)[0]}.json")
    
    if not os.path.exists(result_path):
        return jsonify({'error': '结果文件不存在'}), 404
    
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'results': results
        })
    except Exception as e:
        return jsonify({'error': f'读取结果失败: {str(e)}'}), 500

@app.route('/api/download/excel/<filename>')
def download_excel(filename):
    """下载Excel格式结果"""
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], f"result_{os.path.splitext(filename)[0]}.xlsx")
    
    if not os.path.exists(excel_path):
        return jsonify({'error': 'Excel文件不存在'}), 404
    
    return send_file(excel_path, as_attachment=True, download_name=f"ocr_result_{filename}.xlsx")

@app.route('/api/download/json/<filename>')
def download_json(filename):
    """下载JSON格式结果"""
    json_path = os.path.join(app.config['UPLOAD_FOLDER'], f"result_{os.path.splitext(filename)[0]}.json")
    
    if not os.path.exists(json_path):
        return jsonify({'error': 'JSON文件不存在'}), 404
    
    return send_file(json_path, as_attachment=True, download_name=f"ocr_result_{filename}.json")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """访问上传的文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def generate_excel(results, excel_path):
    """生成Excel文件"""
    wb = Workbook()
    ws = wb.active
    ws.title = "OCR识别结果"
    
    # 添加表头
    ws.append(['序号', '坐标X', '坐标Y', '宽度', '高度', '内容', '置信度', '类型'])
    
    # 添加数据
    for i, item in enumerate(results.get('text_items', []), 1):
        location = item.get('location', {})
        ws.append([
            i,
            location.get('left', 0),
            location.get('top', 0),
            location.get('width', 0),
            location.get('height', 0),
            item.get('text', ''),
            item.get('confidence', 0),
            item.get('type', 'text')
        ])
    
    # 调整列宽
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    wb.save(excel_path)

if __name__ == '__main__':
    print("启动OCR工业图片识别系统...")
    print(f"上传目录: {app.config['UPLOAD_FOLDER']}")
    print(f"调试模式: {'开启' if Config.DEBUG else '关闭'}")
    print(f"CORS支持: {'开启' if Config.ENABLE_CORS else '关闭'}")
    print(f"API服务运行在 http://127.0.0.1:{Config.PORT}")
    
    # 验证配置
    config_issues = Config.validate_config()
    if config_issues:
        print("配置警告:")
        for issue in config_issues:
            print(f"  - {issue}")
    
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)