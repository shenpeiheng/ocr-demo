"""
OCR工业图片识别系统 - 后端API服务
支持上传工业图纸图片和PDF文件，识别内容并输出坐标和内容
支持PaddleOCR和OpenAI VL（ModelScope API）两种OCR引擎
"""

import os
import json
import uuid
import tempfile
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, send_file, send_from_directory, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import openpyxl
from openpyxl import Workbook
from PIL import Image
import numpy as np
import cv2

# 导入配置和处理器
from config import Config
from ocr_processor import OCRProcessor, create_ocr_processor
from pdf_processor import create_pdf_processor
from prompt_manager import prompt_manager, get_prompt
from markdown_formatter import markdown_formatter, format_results, save_markdown
from image_utils import preprocess_image_for_ocr

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

# 初始化OCR处理器（根据环境变量自动选择引擎）
ocr_processor = OCRProcessor()

# 初始化PDF处理器
pdf_processor = create_pdf_processor()

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def is_pdf_file(filename):
    """检查文件是否为PDF格式"""
    ext = os.path.splitext(filename)[1].lower()
    return ext == '.pdf'

@app.route('/')
def index():
    """前端页面"""
    return send_from_directory('../frontend', 'index.html')

@app.route('/api')
def api_index():
    """API根路径"""
    engine_info = ocr_processor.get_engine_info()
    
    return jsonify({
        'name': 'OCR工业图片识别系统',
        'version': '3.0.0',
        'description': '工业图纸和PDF文件OCR识别API服务，支持PaddleOCR和OpenAI VL',
        'supported_formats': list(app.config['ALLOWED_EXTENSIONS']),
        'pdf_support': pdf_processor.initialized,
        'ocr_engine': {
            'current': engine_info['current_engine'],
            'type': engine_info['engine_type'],
            'paddleocr_available': engine_info['paddleocr_available'],
            'openai_vl_available': engine_info['openai_vl_available']
        },
        'endpoints': {
            '/api/upload': '上传文件（支持图片和PDF）',
            '/api/process': '处理已上传的文件（自动识别文件类型）',
            '/api/process/openai_vl': '使用OpenAI VL处理图片',
            '/api/process/paddleocr': '使用PaddleOCR处理图片',
            '/api/prompts': '获取可用提示词列表',
            '/api/results/<filename>': '获取识别结果',
            '/api/download/excel/<filename>': '下载Excel格式结果',
            '/api/download/json/<filename>': '下载JSON格式结果',
            '/api/download/markdown/<filename>': '下载Markdown格式结果',
            '/api/pdf/info/<filename>': '获取PDF文件信息',
            '/api/pdf/extract/<filename>': '直接提取PDF文本'
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
        # 从原始文件名获取扩展名（在secure_filename之前）
        original_filename = file.filename
        # 使用os.path.splitext获取扩展名，更安全
        file_ext = os.path.splitext(original_filename)[1].lower()
        if file_ext:
            file_ext = file_ext[1:]  # 去掉点号，例如 ".pdf" -> "pdf"
        else:
            file_ext = "pdf"  # 默认扩展名
        
        # 生成唯一文件名
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
def process_file():
    """处理文件（图片或PDF）并进行OCR识别"""
    data = request.json
    if not data or 'filename' not in data:
        return jsonify({'error': '缺少文件名参数'}), 400
    
    filename = data['filename']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        # 检查文件类型
        if is_pdf_file(filename):
            # PDF文件处理
            return process_pdf_file(filename, filepath, data)
        else:
            # 图片文件处理
            return process_image_file(filename, filepath, data)
        
    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500

@app.route('/api/process/openai_vl', methods=['POST'])
def process_with_openai_vl():
    """使用OpenAI VL处理图片"""
    data = request.json
    if not data or 'filename' not in data:
        return jsonify({'error': '缺少文件名参数'}), 400
    
    filename = data['filename']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    if is_pdf_file(filename):
        return jsonify({'error': 'OpenAI VL暂不支持PDF文件，请先转换为图片'}), 400
    
    try:
        # 获取提示词
        prompt_name = data.get('prompt', 'mechanical_drawing_standard')
        custom_prompt = data.get('custom_prompt')
        
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = get_prompt(prompt_name)
        
        # 图片预处理：检查尺寸并调整到990x990（如果需要）
        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990)
        use_preprocessed = preprocessed_path != filepath
        
        # 使用OpenAI VL处理图片
        results = ocr_processor.process_image_with_engine(preprocessed_path, 'openai_vl', prompt)
        
        # 在结果中添加预处理信息
        if use_preprocessed:
            results['preprocessed_image'] = os.path.basename(preprocessed_path)
            results['original_image'] = filename
            results['image_preprocessed'] = True
        else:
            results['image_preprocessed'] = False
        
        # 保存结果到JSON文件
        result_filename = f"result_openai_vl_{os.path.splitext(filename)[0]}.json"
        result_path = os.path.join(app.config['UPLOAD_FOLDER'], result_filename)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 生成Markdown文件
        markdown_filename = f"result_openai_vl_{os.path.splitext(filename)[0]}.md"
        markdown_path = os.path.join(app.config['UPLOAD_FOLDER'], markdown_filename)
        markdown_content = markdown_formatter.format_ocr_results(results, include_raw=data.get('include_raw', False))
        save_markdown(markdown_content, markdown_path)
        
        # 生成Excel文件
        excel_filename = f"result_openai_vl_{os.path.splitext(filename)[0]}.xlsx"
        excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_filename)
        generate_excel(results, excel_path)
        
        return jsonify({
            'success': True,
            'message': 'OpenAI VL处理成功',
            'filename': filename,
            'file_type': 'image',
            'engine': 'openai_vl',
            'prompt_used': prompt_name,
            'results': results,
            'result_files': {
                'json': result_filename,
                'excel': excel_filename,
                'markdown': markdown_filename
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'OpenAI VL处理失败: {str(e)}'}), 500

@app.route('/api/process/paddleocr', methods=['POST'])
def process_with_paddleocr():
    """使用PaddleOCR处理图片"""
    data = request.json
    if not data or 'filename' not in data:
        return jsonify({'error': '缺少文件名参数'}), 400
    
    filename = data['filename']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    try:
        # 图片预处理：检查尺寸并调整到990x990（如果需要）
        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990)
        use_preprocessed = preprocessed_path != filepath
        
        # 使用PaddleOCR处理图片
        results = ocr_processor.process_image_with_engine(preprocessed_path, 'paddleocr')
        
        # 在结果中添加预处理信息
        if use_preprocessed:
            results['preprocessed_image'] = os.path.basename(preprocessed_path)
            results['original_image'] = filename
            results['image_preprocessed'] = True
        else:
            results['image_preprocessed'] = False
        
        # 保存结果到JSON文件
        result_filename = f"result_paddleocr_{os.path.splitext(filename)[0]}.json"
        result_path = os.path.join(app.config['UPLOAD_FOLDER'], result_filename)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 生成Excel文件
        excel_filename = f"result_paddleocr_{os.path.splitext(filename)[0]}.xlsx"
        excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_filename)
        generate_excel(results, excel_path)
        
        return jsonify({
            'success': True,
            'message': 'PaddleOCR处理成功',
            'filename': filename,
            'file_type': 'image',
            'engine': 'paddleocr',
            'results': results,
            'result_files': {
                'json': result_filename,
                'excel': excel_filename
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'PaddleOCR处理失败: {str(e)}'}), 500

@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    """获取可用提示词列表"""
    try:
        prompts = prompt_manager.get_all_prompts()
        
        # 只返回名称和预览
        prompt_list = []
        for name, content in prompts.items():
            prompt_list.append({
                'name': name,
                'preview': content[:100] + "..." if len(content) > 100 else content,
                'length': len(content)
            })
        
        return jsonify({
            'success': True,
            'prompts': prompt_list,
            'total': len(prompt_list)
        })
    except Exception as e:
        return jsonify({'error': f'获取提示词失败: {str(e)}'}), 500

@app.route('/api/prompts/<prompt_name>', methods=['GET'])
def get_prompt_detail(prompt_name):
    """获取特定提示词的详细内容"""
    try:
        prompt = prompt_manager.get_prompt(prompt_name)
        
        return jsonify({
            'success': True,
            'name': prompt_name,
            'content': prompt,
            'length': len(prompt)
        })
    except Exception as e:
        return jsonify({'error': f'获取提示词失败: {str(e)}'}), 500

def process_image_file(filename, filepath, data):
    """处理图片文件"""
    try:
        # 获取处理参数
        engine = data.get('engine', 'auto')  # auto, paddleocr, openai_vl
        prompt_name = data.get('prompt', 'mechanical_drawing_standard')
        custom_prompt = data.get('custom_prompt')
        
        # 图片预处理：检查尺寸并调整到990x990（如果需要）
        preprocessed_path = preprocess_image_for_ocr(filepath, target_size=990)
        use_preprocessed = preprocessed_path != filepath
        
        # 选择处理方式
        if engine == 'openai_vl':
            # 使用OpenAI VL
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = get_prompt(prompt_name)
            
            results = ocr_processor.process_image_with_engine(preprocessed_path, 'openai_vl', prompt)
            result_prefix = 'result_openai_vl'
        elif engine == 'paddleocr':
            # 使用PaddleOCR
            results = ocr_processor.process_image_with_engine(preprocessed_path, 'paddleocr')
            result_prefix = 'result_paddleocr'
        else:
            # 自动选择（使用初始化时的引擎）
            if custom_prompt:
                results = ocr_processor.process_image(preprocessed_path, custom_prompt)
            else:
                results = ocr_processor.process_image(preprocessed_path)
            result_prefix = 'result'
        
        # 在结果中添加预处理信息
        if use_preprocessed:
            results['preprocessed_image'] = os.path.basename(preprocessed_path)
            results['original_image'] = filename
            results['image_preprocessed'] = True
        else:
            results['image_preprocessed'] = False
        
        # 保存结果到JSON文件
        result_filename = f"{result_prefix}_{os.path.splitext(filename)[0]}.json"
        result_path = os.path.join(app.config['UPLOAD_FOLDER'], result_filename)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 生成Excel文件
        excel_filename = f"{result_prefix}_{os.path.splitext(filename)[0]}.xlsx"
        excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_filename)
        generate_excel(results, excel_path)
        
        # 如果是OpenAI VL，额外生成Markdown文件
        markdown_filename = None
        if engine == 'openai_vl' or (engine == 'auto' and ocr_processor.current_engine == 'openai_vl'):
            markdown_filename = f"{result_prefix}_{os.path.splitext(filename)[0]}.md"
            markdown_path = os.path.join(app.config['UPLOAD_FOLDER'], markdown_filename)
            markdown_content = markdown_formatter.format_ocr_results(results, include_raw=data.get('include_raw', False))
            save_markdown(markdown_content, markdown_path)
        
        # 构建响应
        response = {
            'success': True,
            'message': '图片处理成功',
            'filename': filename,
            'file_type': 'image',
            'engine': results.get('ocr_engine', 'unknown'),
            'results': results,
            'result_files': {
                'json': result_filename,
                'excel': excel_filename
            }
        }
        
        if markdown_filename:
            response['result_files']['markdown'] = markdown_filename
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': f'图片处理失败: {str(e)}'}), 500

def process_pdf_file(filename, filepath, data):
    """处理PDF文件"""
    try:
        # 检查PDF处理器是否可用
        if not pdf_processor.initialized:
            return jsonify({
                'success': False,
                'error': 'PDF处理器未初始化，请安装PDF处理依赖',
                'suggestion': '请运行: pip install pdf2image PyMuPDF pdfplumber'
            }), 500
        
        # 获取处理参数
        max_pages = data.get('max_pages', Config.PDF_MAX_PAGES)
        dpi = data.get('dpi', Config.PDF_DPI)
        engine = data.get('engine', 'auto')
        
        # 创建PDF图像输出目录（在上传目录中）
        pdf_base_name = os.path.splitext(filename)[0]
        images_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"images_{pdf_base_name}")
        os.makedirs(images_dir, exist_ok=True)
        
        # 处理PDF文件，指定输出目录
        pdf_result = pdf_processor.process_pdf_with_ocr(
            filepath,
            ocr_processor,
            dpi=dpi,
            max_pages=max_pages,
            output_dir=images_dir
        )
        
        if not pdf_result['success']:
            return jsonify({
                'success': False,
                'error': pdf_result.get('error', 'PDF处理失败'),
                'file_type': 'pdf'
            }), 500
        
        # 保存结果到JSON文件
        result_filename = f"result_{pdf_base_name}.json"
        result_path = os.path.join(app.config['UPLOAD_FOLDER'], result_filename)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(pdf_result, f, ensure_ascii=False, indent=2)
        
        # 生成Excel文件（包含所有页面的结果）
        excel_filename = f"result_{pdf_base_name}.xlsx"
        excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_filename)
        generate_pdf_excel(pdf_result, excel_path)
        
        # 不再清理图像文件，因为现在保存在上传目录中
        # 但需要更新图像路径，使其可以通过API访问
        if 'conversion_info' in pdf_result and 'image_paths' in pdf_result['conversion_info']:
            # 将绝对路径转换为相对路径
            image_paths = pdf_result['conversion_info']['image_paths']
            relative_image_paths = []
            for img_path in image_paths:
                if os.path.exists(img_path):
                    # 计算相对于上传目录的路径
                    rel_path = os.path.relpath(img_path, app.config['UPLOAD_FOLDER'])
                    relative_image_paths.append(rel_path)
            
            # 保存相对路径到结果中
            pdf_result['conversion_info']['relative_image_paths'] = relative_image_paths
        
        return jsonify({
            'success': True,
            'message': 'PDF处理成功',
            'filename': filename,
            'file_type': 'pdf',
            'results': pdf_result,
            'result_files': {
                'json': result_filename,
                'excel': excel_filename
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'PDF处理失败: {str(e)}'}), 500

@app.route('/api/results/<filename>')
def get_results(filename):
    """获取识别结果"""
    # 尝试多种可能的结果文件名
    possible_filenames = [
        f"result_{os.path.splitext(filename)[0]}.json",
        f"result_openai_vl_{os.path.splitext(filename)[0]}.json",
        f"result_paddleocr_{os.path.splitext(filename)[0]}.json"
    ]
    
    result_path = None
    for possible_filename in possible_filenames:
        test_path = os.path.join(app.config['UPLOAD_FOLDER'], possible_filename)
        if os.path.exists(test_path):
            result_path = test_path
            break
    
    if not result_path:
        return jsonify({'error': '结果文件不存在'}), 404
    
    try:
        with open(result_path, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'result_file': os.path.basename(result_path),
            'results': results
        })
    except Exception as e:
        return jsonify({'error': f'读取结果失败: {str(e)}'}), 500

@app.route('/api/download/excel/<filename>')
def download_excel(filename):
    """下载Excel格式结果"""
    # 尝试多种可能的Excel文件名
    possible_filenames = [
        f"result_{os.path.splitext(filename)[0]}.xlsx",
        f"result_openai_vl_{os.path.splitext(filename)[0]}.xlsx",
        f"result_paddleocr_{os.path.splitext(filename)[0]}.xlsx"
    ]
    
    excel_path = None
    for possible_filename in possible_filenames:
        test_path = os.path.join(app.config['UPLOAD_FOLDER'], possible_filename)
        if os.path.exists(test_path):
            excel_path = test_path
            break
    
    if not excel_path:
        return jsonify({'error': 'Excel文件不存在'}), 404
    
    return send_file(excel_path, as_attachment=True, download_name=f"ocr_result_{filename}.xlsx")

@app.route('/api/download/json/<filename>')
def download_json(filename):
    """下载JSON格式结果"""
    # 尝试多种可能的JSON文件名
    possible_filenames = [
        f"result_{os.path.splitext(filename)[0]}.json",
        f"result_openai_vl_{os.path.splitext(filename)[0]}.json",
        f"result_paddleocr_{os.path.splitext(filename)[0]}.json"
    ]
    
    json_path = None
    for possible_filename in possible_filenames:
        test_path = os.path.join(app.config['UPLOAD_FOLDER'], possible_filename)
        if os.path.exists(test_path):
            json_path = test_path
            break
    
    if not json_path:
        return jsonify({'error': 'JSON文件不存在'}), 404
    
    return send_file(json_path, as_attachment=True, download_name=f"ocr_result_{filename}.json")

@app.route('/api/download/markdown/<filename>')
def download_markdown(filename):
    """下载Markdown格式结果"""
    # 尝试多种可能的Markdown文件名
    possible_filenames = [
        f"result_{os.path.splitext(filename)[0]}.md",
        f"result_openai_vl_{os.path.splitext(filename)[0]}.md"
    ]
    
    markdown_path = None
    for possible_filename in possible_filenames:
        test_path = os.path.join(app.config['UPLOAD_FOLDER'], possible_filename)
        if os.path.exists(test_path):
            markdown_path = test_path
            break
    
    if not markdown_path:
        return jsonify({'error': 'Markdown文件不存在'}), 404
    
    return send_file(markdown_path, as_attachment=True, download_name=f"ocr_result_{filename}.md")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """访问上传的文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/pdf/info/<filename>')
def get_pdf_info(filename):
    """获取PDF文件信息"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    if not is_pdf_file(filename):
        return jsonify({'error': '文件不是PDF格式'}), 400
    
    if not pdf_processor.initialized:
        return jsonify({
            'success': False,
            'error': 'PDF处理器未初始化',
            'suggestion': '请安装PDF处理依赖: pip install pdf2image PyMuPDF pdfplumber'
        }), 500
    
    try:
        pdf_info = pdf_processor._get_pdf_info(filepath)
        return jsonify({
            'success': True,
            'filename': filename,
            'pdf_info': pdf_info
        })
    except Exception as e:
        return jsonify({'error': f'获取PDF信息失败: {str(e)}'}), 500

@app.route('/api/pdf/extract/<filename>')
def extract_pdf_text(filename):
    """直接提取PDF文本（不进行OCR）"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    if not is_pdf_file(filename):
        return jsonify({'error': '文件不是PDF格式'}), 400
    
    if not pdf_processor.initialized:
        return jsonify({
            'success': False,
            'error': 'PDF处理器未初始化',
            'suggestion': '请安装PDF处理依赖: pip install pdf2image PyMuPDF pdfplumber'
        }), 500
    
    try:
        # 获取查询参数
        first_page = request.args.get('first_page', default=None, type=int)
        last_page = request.args.get('last_page', default=None, type=int)
        
        # 提取文本
        text_result = pdf_processor.extract_text_from_pdf(
            filepath,
            first_page=first_page,
            last_page=last_page
        )
        
        if text_result['success']:
            return jsonify({
                'success': True,
                'filename': filename,
                'result': text_result
            })
        else:
            return jsonify({
                'success': False,
                'error': text_result.get('error', '文本提取失败')
            }), 500
            
    except Exception as e:
        return jsonify({'error': f'提取PDF文本失败: {str(e)}'}), 500

@app.route('/api/pdf/images/<filename>/<int:page>')
def get_pdf_image(filename, page):
    """获取PDF页面图像"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    if not is_pdf_file(filename):
        return jsonify({'error': '文件不是PDF格式'}), 400
    
    # 查找图像文件
    pdf_base_name = os.path.splitext(filename)[0]
    images_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"images_{pdf_base_name}")
    
    # 可能的图像文件名格式
    image_patterns = [
        f"page_{page:03d}.png",
        f"page_{page}.png",
        f"{page}.png",
        f"page_{page:03d}.jpg",
        f"page_{page}.jpg",
        f"{page}.jpg"
    ]
    
    image_path = None
    for pattern in image_patterns:
        test_path = os.path.join(images_dir, pattern)
        if os.path.exists(test_path):
            image_path = test_path
            break
    
    if not image_path:
        # 如果找不到图像文件，尝试从PDF重新生成
        try:
            if not pdf_processor.initialized:
                return jsonify({'error': 'PDF处理器未初始化'}), 500
            
            # 生成单页图像
            conversion_result = pdf_processor.convert_pdf_to_images(
                filepath,
                dpi=200,
                first_page=page,
                last_page=page,
                output_dir=images_dir
            )
            
            if conversion_result['success'] and conversion_result['image_paths']:
                image_path = conversion_result['image_paths'][0]
            else:
                return jsonify({'error': '无法生成PDF页面图像'}), 500
        except Exception as e:
            return jsonify({'error': f'生成图像失败: {str(e)}'}), 500
    
    # 返回图像文件
    return send_file(image_path, mimetype='image/png')

@app.route('/api/pdf/images/list/<filename>')
def list_pdf_images(filename):
    """列出PDF所有页面图像"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    
    if not is_pdf_file(filename):
        return jsonify({'error': '文件不是PDF格式'}), 400
    
    # 查找图像目录
    pdf_base_name = os.path.splitext(filename)[0]
    images_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"images_{pdf_base_name}")
    
    if not os.path.exists(images_dir):
        return jsonify({
            'success': True,
            'filename': filename,
            'images': [],
            'message': '图像目录不存在，PDF可能尚未处理'
        })
    
    # 列出所有PNG和JPG文件
    image_files = []
    for ext in ['.png', '.jpg', '.jpeg']:
        for file in os.listdir(images_dir):
            if file.lower().endswith(ext):
                # 提取页码
                page_match = None
                import re
                # 匹配 page_001.png 或 page_1.png 或 1.png 等格式
                match = re.search(r'page_(\d+)', file)
                if match:
                    page_num = int(match.group(1))
                else:
                    match = re.search(r'(\d+)\.', file)
                    if match:
                        page_num = int(match.group(1))
                    else:
                        page_num = 0
                
                image_files.append({
                    'filename': file,
                    'page': page_num,
                    'url': f"/api/pdf/images/{filename}/{page_num}"
                })
    
    # 按页码排序
    image_files.sort(key=lambda x: x['page'])
    
    return jsonify({
        'success': True,
        'filename': filename,
        'images': image_files,
        'total': len(image_files)
    })

def generate_excel(results, excel_path):
    """生成Excel文件（用于图片处理结果）"""
    wb = Workbook()
    ws = wb.active
    ws.title = "OCR识别结果"
    
    # 添加表头
    headers = ['序号', '坐标X', '坐标Y', '宽度', '高度', '内容', '置信度', '类型']
    if 'region' in results.get('text_items', [{}])[0]:
        headers.append('区域')
    
    ws.append(headers)
    
    # 添加数据
    for i, item in enumerate(results.get('text_items', []), 1):
        location = item.get('location', {})
        row_data = [
            i,
            location.get('left', 0),
            location.get('top', 0),
            location.get('width', 0),
            location.get('height', 0),
            item.get('text', ''),
            item.get('confidence', 0),
            item.get('type', 'text')
        ]
        
        if 'region' in item:
            row_data.append(item.get('region', ''))
        
        ws.append(row_data)
    
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

def generate_pdf_excel(pdf_result, excel_path):
    """生成Excel文件（用于PDF处理结果）"""
    wb = Workbook()
    
    # 创建汇总工作表
    ws_summary = wb.active
    ws_summary.title = "PDF处理汇总"
    
    # 添加汇总信息
    ws_summary.append(['PDF文件信息', ''])
    pdf_info = pdf_result.get('pdf_info', {})
    ws_summary.append(['文件名', pdf_info.get('filename', '')])
    ws_summary.append(['总页数', pdf_info.get('total_pages', 0)])
    ws_summary.append(['文件大小', f"{pdf_info.get('file_size', 0)} 字节"])
    
    ws_summary.append([])
    ws_summary.append(['处理信息', ''])
    processing_info = pdf_result.get('processing_info', {})
    ws_summary.append(['DPI', processing_info.get('dpi', 200)])
    ws_summary.append(['最大处理页数', processing_info.get('max_pages', 10)])
    ws_summary.append(['实际处理页数', processing_info.get('actual_pages_processed', 0)])
    
    ws_summary.append([])
    ws_summary.append(['识别结果汇总', ''])
    combined_results = pdf_result.get('combined_results', {})
    ws_summary.append(['总识别项数', combined_results.get('total_items', 0)])
    ws_summary.append(['总处理时间', f"{combined_results.get('total_processing_time', 0)} 秒"])
    
    # 创建页面汇总工作表
    ws_pages = wb.create_sheet(title="页面汇总")
    ws_pages.append(['页码', '识别项数', '处理时间(秒)', '处理状态'])
    
    pages_summary = pdf_result.get('pages_summary', [])
    for page in pages_summary:
        ws_pages.append([
            page.get('page_number', 0),
            page.get('total_items', 0),
            page.get('processing_time', 0),
            '成功' if page.get('success', False) else '失败'
        ])
    
    # 创建详细结果工作表
    ws_details = wb.create_sheet(title="详细识别结果")
    detail_headers = ['页码', '序号', '坐标X', '坐标Y', '宽度', '高度', '内容', '置信度', '类型']
    if 'region' in pdf_result.get('combined_results', {}).get('text_items', [{}])[0]:
        detail_headers.append('区域')
    
    ws_details.append(detail_headers)
    
    text_items = combined_results.get('text_items', [])
    for i, item in enumerate(text_items, 1):
        location = item.get('location', {})
        row_data = [
            item.get('page', 1),
            i,
            location.get('left', 0),
            location.get('top', 0),
            location.get('width', 0),
            location.get('height', 0),
            item.get('text', ''),
            item.get('confidence', 0),
            item.get('type', 'text')
        ]
        
        if 'region' in item:
            row_data.append(item.get('region', ''))
        
        ws_details.append(row_data)
    
    # 调整列宽
    for ws in wb.worksheets:
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
    
    # 显示OCR引擎信息
    engine_info = ocr_processor.get_engine_info()
    print(f"OCR引擎: {engine_info['current_engine']} (类型: {engine_info['engine_type']})")
    print(f"PaddleOCR可用: {engine_info['paddleocr_available']}")
    print(f"OpenAI VL可用: {engine_info['openai_vl_available']}")
    
    print(f"API服务运行在 http://127.0.0.1:{Config.PORT}")
    
    # 验证配置
    config_issues = Config.validate_config()
    if config_issues:
        print("配置警告:")
        for issue in config_issues:
            print(f"  - {issue}")
    
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=Config.PORT)