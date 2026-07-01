"""
应用核心对象与共享运行时依赖。
"""

import os
import socket

from flask import Flask
from flask_cors import CORS

from config import Config
from ocr_processor import OCRProcessor
from pdf_processor import create_pdf_processor


app = Flask(__name__, static_folder="../frontend", static_url_path="")

if Config.ENABLE_CORS:
    CORS(app)

app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER
app.config["ALLOWED_EXTENSIONS"] = Config.ALLOWED_EXTENSIONS
app.config["SECRET_KEY"] = Config.SECRET_KEY

# 配置 Werkzeug 底层 socket 超时，防止大文件上传时连接被重置
# 默认 socket 超时很短，大文件上传时间长会导致 ERR_CONNECTION_RESET
socket.setdefaulttimeout(600)  # 10 分钟

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ocr_processor = OCRProcessor()
pdf_processor = create_pdf_processor()
