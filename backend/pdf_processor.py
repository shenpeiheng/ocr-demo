"""
PDF处理器 - 将PDF文件转换为图像，支持多页处理和OCR识别
"""

import os
import tempfile
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFProcessor:
    """PDF处理器类，负责将PDF转换为图像"""
    
    def __init__(self):
        """初始化PDF处理器"""
        self.supported_formats = ['.pdf', '.PDF']
        self.initialized = False
        self._initialize_pdf_libs()
    
    def _initialize_pdf_libs(self):
        """初始化PDF处理库"""
        # 优先尝试使用PyMuPDF，因为它不需要外部依赖（如poppler）
        try:
            import fitz
            self.fitz = fitz
            self.initialized = True
            logger.info("PDF处理器初始化成功 (使用PyMuPDF)")
        except ImportError as e:
            logger.warning(f"PyMuPDF未安装: {e}")
            try:
                # 备选：尝试导入pdf2image
                import pdf2image
                self.pdf2image = pdf2image
                self.initialized = True
                logger.info("PDF处理器初始化成功 (使用pdf2image)")
                logger.info("注意：pdf2image需要poppler，请确保已安装poppler")
            except ImportError as e2:
                logger.warning(f"pdf2image未安装: {e2}")
                try:
                    # 备选：尝试使用pdfplumber
                    import pdfplumber
                    self.pdfplumber = pdfplumber
                    self.initialized = True
                    logger.info("PDF处理器初始化成功 (使用pdfplumber)")
                except ImportError as e3:
                    logger.error(f"所有PDF库都未安装: {e3}")
                    self.initialized = False
    
    def is_pdf_file(self, filepath: str) -> bool:
        """检查文件是否为PDF格式"""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in self.supported_formats
    
    def convert_pdf_to_images(self, pdf_path: str, output_dir: str = None, 
                              dpi: int = 200, first_page: int = None, 
                              last_page: int = None) -> Dict[str, Any]:
        """
        将PDF文件转换为图像
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录，如果为None则使用临时目录
            dpi: 图像DPI（分辨率）
            first_page: 起始页码（从1开始）
            last_page: 结束页码
            
        Returns:
            转换结果字典
        """
        if not self.initialized:
            return self._get_error_result("PDF处理器未初始化，请安装pdf2image或PyMuPDF")
        
        if not os.path.exists(pdf_path):
            return self._get_error_result(f"PDF文件不存在: {pdf_path}")
        
        try:
            # 创建输出目录
            if output_dir is None:
                output_dir = tempfile.mkdtemp(prefix='pdf_images_')
            else:
                os.makedirs(output_dir, exist_ok=True)
            
            # 获取PDF信息
            pdf_info = self._get_pdf_info(pdf_path)
            total_pages = pdf_info.get('total_pages', 0)
            
            if total_pages == 0:
                return self._get_error_result("PDF文件没有页面")
            
            # 确定要转换的页面范围
            if first_page is None:
                first_page = 1
            if last_page is None:
                last_page = total_pages
            
            first_page = max(1, min(first_page, total_pages))
            last_page = max(first_page, min(last_page, total_pages))
            
            logger.info(f"转换PDF: {pdf_path}, 页面 {first_page}-{last_page}/{total_pages}, DPI: {dpi}")
            
            # 转换PDF为图像
            image_paths = []
            
            # 优先尝试使用PyMuPDF
            if hasattr(self, 'fitz'):
                try:
                    doc = self.fitz.open(pdf_path)
                    for page_num in range(first_page - 1, last_page):
                        page = doc[page_num]
                        pix = page.get_pixmap(dpi=dpi)
                        image_filename = f"page_{page_num + 1:03d}.png"
                        image_path = os.path.join(output_dir, image_filename)
                        pix.save(image_path)
                        image_paths.append(image_path)
                        logger.info(f"保存页面 {page_num + 1} 到: {image_path}")
                    doc.close()
                except Exception as fitz_error:
                    logger.warning(f"PyMuPDF转换失败: {fitz_error}")
                    # 尝试使用pdf2image作为备选
            
            # 如果PyMuPDF失败或未安装，尝试使用pdf2image
            if len(image_paths) == 0 and hasattr(self, 'pdf2image'):
                try:
                    images = self.pdf2image.convert_from_path(
                        pdf_path,
                        dpi=dpi,
                        first_page=first_page,
                        last_page=last_page,
                        output_folder=output_dir,
                        fmt='png',
                        thread_count=2
                    )
                    
                    # 保存图像文件
                    for i, image in enumerate(images):
                        page_num = first_page + i
                        image_filename = f"page_{page_num:03d}.png"
                        image_path = os.path.join(output_dir, image_filename)
                        image.save(image_path, 'PNG')
                        image_paths.append(image_path)
                        logger.info(f"保存页面 {page_num} 到: {image_path}")
                        
                except Exception as pdf2image_error:
                    logger.warning(f"pdf2image转换失败（可能是poppler未安装）: {pdf2image_error}")
                    # 继续尝试其他方法
            
            # 如果仍然没有图像，尝试其他方法
            if len(image_paths) == 0:
                # 备选：使用pdfplumber（需要额外库）
                if hasattr(self, 'pdfplumber'):
                    with self.pdfplumber.open(pdf_path) as pdf:
                        for page_num in range(first_page - 1, last_page):
                            page = pdf.pages[page_num]
                            # pdfplumber本身不直接转换为图像，需要其他库支持
                            # 这里简单记录，实际使用时需要安装pillow等库
                            logger.warning("pdfplumber需要额外库支持图像转换")
                            break
                    return self._get_error_result("pdfplumber需要额外库支持图像转换")
                
                else:
                    return self._get_error_result("没有可用的PDF转换库。请安装pdf2image（需要poppler）或PyMuPDF。")
            
            # 构建结果
            result = {
                'success': True,
                'pdf_info': pdf_info,
                'conversion_info': {
                    'dpi': dpi,
                    'first_page': first_page,
                    'last_page': last_page,
                    'total_converted': len(image_paths),
                    'output_dir': output_dir
                },
                'image_paths': image_paths,
                'image_count': len(image_paths)
            }
            
            logger.info(f"PDF转换完成，生成 {len(image_paths)} 张图像")
            return result
            
        except Exception as e:
            logger.error(f"PDF转换失败: {e}")
            return self._get_error_result(f"PDF转换失败: {str(e)}")
    
    def _get_pdf_info(self, pdf_path: str) -> Dict[str, Any]:
        """获取PDF文件信息"""
        try:
            # 优先使用PyMuPDF获取信息
            if hasattr(self, 'fitz'):
                try:
                    doc = self.fitz.open(pdf_path)
                    total_pages = len(doc)
                    metadata = doc.metadata
                    doc.close()
                    
                    return {
                        'total_pages': total_pages,
                        'metadata': metadata,
                        'file_size': os.path.getsize(pdf_path),
                        'filename': os.path.basename(pdf_path)
                    }
                except Exception as fitz_error:
                    logger.warning(f"PyMuPDF获取PDF信息失败: {fitz_error}")
                    # 继续尝试其他方法
            
            # 备选：使用pdf2image获取信息
            if hasattr(self, 'pdf2image'):
                try:
                    from pdf2image.pdf2image import pdfinfo_from_path
                    info = pdfinfo_from_path(pdf_path)
                    
                    return {
                        'total_pages': info['Pages'],
                        'metadata': {
                            'title': info.get('Title', ''),
                            'author': info.get('Author', ''),
                            'creator': info.get('Creator', ''),
                            'producer': info.get('Producer', ''),
                            'creation_date': info.get('CreationDate', ''),
                            'mod_date': info.get('ModDate', '')
                        },
                        'file_size': os.path.getsize(pdf_path),
                        'filename': os.path.basename(pdf_path)
                    }
                except Exception as pdf2image_error:
                    # 如果pdf2image失败（可能是poppler未安装），尝试其他方法
                    logger.warning(f"pdf2image获取PDF信息失败: {pdf2image_error}")
                    # 继续尝试其他方法
            
            # 备选：使用pdfplumber获取信息
            if hasattr(self, 'pdfplumber'):
                try:
                    with self.pdfplumber.open(pdf_path) as pdf:
                        return {
                            'total_pages': len(pdf.pages),
                            'metadata': pdf.metadata,
                            'file_size': os.path.getsize(pdf_path),
                            'filename': os.path.basename(pdf_path)
                        }
                except Exception as pdfplumber_error:
                    logger.warning(f"pdfplumber获取PDF信息失败: {pdfplumber_error}")
            
            # 如果所有方法都失败，尝试使用简单的方法获取页数
            # 首先检查是否安装了PyPDF2
            try:
                import PyPDF2
                # 尝试使用PyPDF2作为最后的手段
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    total_pages = len(pdf_reader.pages)
                    return {
                        'total_pages': total_pages,
                        'metadata': {},
                        'file_size': os.path.getsize(pdf_path),
                        'filename': os.path.basename(pdf_path)
                    }
            except ImportError:
                # PyPDF2未安装，不记录警告，因为它是可选依赖
                pass
            except Exception as pypdf_error:
                logger.debug(f"PyPDF2获取PDF信息失败: {pypdf_error}")
            
            # 所有方法都失败，返回未知页数
            return {
                'total_pages': 0,  # 未知
                'metadata': {},
                'file_size': os.path.getsize(pdf_path),
                'filename': os.path.basename(pdf_path),
                'error': '无法获取PDF信息，请确保已安装PDF处理依赖'
            }
                
        except Exception as e:
            logger.warning(f"获取PDF信息失败: {e}")
            return {
                'total_pages': 0,
                'metadata': {},
                'file_size': os.path.getsize(pdf_path),
                'filename': os.path.basename(pdf_path),
                'error': str(e)
            }
    
    def extract_text_from_pdf(self, pdf_path: str, first_page: int = None, 
                              last_page: int = None) -> Dict[str, Any]:
        """
        直接从PDF提取文本（不转换为图像）
        
        Args:
            pdf_path: PDF文件路径
            first_page: 起始页码
            last_page: 结束页码
            
        Returns:
            提取的文本结果
        """
        try:
            if hasattr(self, 'pdfplumber'):
                return self._extract_text_with_pdfplumber(pdf_path, first_page, last_page)
            elif hasattr(self, 'fitz'):
                return self._extract_text_with_pymupdf(pdf_path, first_page, last_page)
            else:
                return self._get_error_result("没有可用的PDF文本提取库")
        except Exception as e:
            logger.error(f"PDF文本提取失败: {e}")
            return self._get_error_result(f"PDF文本提取失败: {str(e)}")
    
    def _extract_text_with_pdfplumber(self, pdf_path: str, first_page: int = None, 
                                      last_page: int = None) -> Dict[str, Any]:
        """使用pdfplumber提取文本"""
        with self.pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            
            if first_page is None:
                first_page = 1
            if last_page is None:
                last_page = total_pages
            
            first_page = max(1, min(first_page, total_pages))
            last_page = max(first_page, min(last_page, total_pages))
            
            pages_text = []
            for page_num in range(first_page - 1, last_page):
                page = pdf.pages[page_num]
                text = page.extract_text()
                pages_text.append({
                    'page_number': page_num + 1,
                    'text': text,
                    'char_count': len(text) if text else 0
                })
            
            return {
                'success': True,
                'total_pages': total_pages,
                'extracted_pages': len(pages_text),
                'pages': pages_text,
                'total_text': '\n'.join([p['text'] for p in pages_text if p['text']]),
                'total_char_count': sum(p['char_count'] for p in pages_text)
            }
    
    def _extract_text_with_pymupdf(self, pdf_path: str, first_page: int = None, 
                                   last_page: int = None) -> Dict[str, Any]:
        """使用PyMuPDF提取文本"""
        doc = self.fitz.open(pdf_path)
        total_pages = len(doc)
        
        if first_page is None:
            first_page = 1
        if last_page is None:
            last_page = total_pages
        
        first_page = max(1, min(first_page, total_pages))
        last_page = max(first_page, min(last_page, total_pages))
        
        pages_text = []
        for page_num in range(first_page - 1, last_page):
            page = doc[page_num]
            text = page.get_text()
            pages_text.append({
                'page_number': page_num + 1,
                'text': text,
                'char_count': len(text) if text else 0
            })
        
        doc.close()
        
        return {
            'success': True,
            'total_pages': total_pages,
            'extracted_pages': len(pages_text),
            'pages': pages_text,
            'total_text': '\n'.join([p['text'] for p in pages_text if p['text']]),
            'total_char_count': sum(p['char_count'] for p in pages_text)
        }
    
    def process_pdf_with_ocr(self, pdf_path: str, ocr_processor,
                             dpi: int = 200, max_pages: int = 10,
                             output_dir: str = None) -> Dict[str, Any]:
        """
        处理PDF文件并进行OCR识别
        
        Args:
            pdf_path: PDF文件路径
            ocr_processor: OCR处理器实例
            dpi: 图像DPI
            max_pages: 最大处理页数
            output_dir: 图像输出目录，如果为None则使用临时目录
            
        Returns:
            OCR识别结果
        """
        if not self.initialized:
            return self._get_error_result("PDF处理器未初始化")
        
        try:
            # 获取PDF信息
            pdf_info = self._get_pdf_info(pdf_path)
            total_pages = pdf_info.get('total_pages', 0)
            
            if total_pages == 0:
                return self._get_error_result("PDF文件没有页面")
            
            # 限制处理页数
            pages_to_process = min(total_pages, max_pages)
            
            # 转换PDF为图像
            conversion_result = self.convert_pdf_to_images(
                pdf_path,
                dpi=dpi,
                first_page=1,
                last_page=pages_to_process,
                output_dir=output_dir
            )
            
            if not conversion_result['success']:
                return conversion_result
            
            # 对每张图像进行OCR识别
            image_paths = conversion_result['image_paths']
            ocr_results = []
            
            for i, image_path in enumerate(image_paths):
                page_num = i + 1
                logger.info(f"对页面 {page_num}/{pages_to_process} 进行OCR识别: {image_path}")
                
                # 使用OCR处理器识别图像
                ocr_result = ocr_processor.process_image(image_path)
                ocr_result['page_number'] = page_num
                ocr_result['image_path'] = image_path
                ocr_results.append(ocr_result)
            
            # 合并所有页面的结果
            all_text_items = []
            for result in ocr_results:
                if result.get('success') and result.get('text_items'):
                    # 为每个文本项添加页面信息
                    for item in result['text_items']:
                        item['page'] = result['page_number']
                    all_text_items.extend(result['text_items'])
            
            # 计算总体统计
            total_processing_time = sum(r.get('processing_time', 0) for r in ocr_results)
            total_items = len(all_text_items)
            
            # 按页面分组
            pages_summary = []
            for result in ocr_results:
                pages_summary.append({
                    'page_number': result['page_number'],
                    'total_items': len(result.get('text_items', [])),
                    'processing_time': result.get('processing_time', 0),
                    'success': result.get('success', False)
                })
            
            return {
                'success': True,
                'pdf_info': pdf_info,
                'conversion_info': conversion_result['conversion_info'],
                'ocr_results': ocr_results,
                'combined_results': {
                    'text_items': all_text_items,
                    'total_items': total_items,
                    'total_pages': pages_to_process,
                    'total_processing_time': round(total_processing_time, 2)
                },
                'pages_summary': pages_summary,
                'processing_info': {
                    'dpi': dpi,
                    'max_pages': max_pages,
                    'actual_pages_processed': pages_to_process
                }
            }
            
        except Exception as e:
            logger.error(f"PDF OCR处理失败: {e}")
            return self._get_error_result(f"PDF OCR处理失败: {str(e)}")
    
    def _get_error_result(self, error_message: str) -> Dict[str, Any]:
        """获取错误结果"""
        return {
            'success': False,
            'error': error_message,
            'pdf_info': {},
            'conversion_info': {},
            'ocr_results': [],
            'combined_results': {
                'text_items': [],
                'total_items': 0,
                'total_pages': 0,
                'total_processing_time': 0
            }
        }


# 工厂函数
def create_pdf_processor():
    """创建PDF处理器实例"""
    return PDFProcessor()


if __name__ == '__main__':
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        print("用法: python pdf_processor.py <PDF文件路径>")
        sys.exit(1)
    
    print(f"测试PDF处理器: {pdf_path}")
    
    processor = PDFProcessor()
    
    if not processor.initialized:
        print("PDF处理器初始化失败，请安装依赖:")
        print("  pip install pdf2image")
        print("  或")
        print("  pip install PyMuPDF")
        print("  或")
        print("  pip install pdfplumber")
        sys.exit(1)
    
    # 测试PDF信息获取
    print("\n1. 获取PDF信息:")
    pdf_info = processor._get_pdf_info(pdf_path)
    print(f"   总页数: {pdf_info.get('total_pages', '未知')}")
    print(f"   文件大小: {pdf_info.get('file_size', 0)} 字节")
    
    # 测试PDF到图像转换
    print("\n2. 转换PDF为图像:")
    result = processor.convert_pdf_to_images(pdf_path, dpi=150, first_page=1, last_page=2)
    
    if result['success']:
        print(f"   转换成功!")
        print(f"   生成图像数: {result.get('image_count', 0)}")
        print(f"   输出目录: {result.get('conversion_info', {}).get('output_dir', '未知')}")
        
        # 测试文本提取
        print("\n3. 提取PDF文本:")
        text_result = processor.extract_text_from_pdf(pdf_path, first_page=1, last_page=2)
        
        if text_result['success']:
            print(f"   文本提取成功!")
            print(f"   提取页数: {text_result.get('extracted_pages', 0)}")
            print(f"   总字符数: {text_result.get('total_char_count', 0)}")
            
            # 显示第一页的部分文本
            pages = text_result.get('pages', [])
            if pages and len(pages) > 0:
                first_page_text = pages[0].get('text', '')
                preview = first_page_text[:200] + "..." if len(first_page_text) > 200 else first_page_text
                print(f"   第一页预览: {preview}")
        else:
            print(f"   文本提取失败: {text_result.get('error', '未知错误')}")
    else:
        print(f"   转换失败: {result.get('error', '未知错误')}")
    
    print("\nPDF处理器测试完成!")