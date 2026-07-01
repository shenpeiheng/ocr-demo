"""
Whisper 语音转字幕处理器
使用 OpenAI Whisper 模型将音频/视频转换为字幕文件
"""

import os
import json
import subprocess
import re
import sys
from datetime import timedelta
from typing import Optional, Dict, Any, List
from io import StringIO


def check_whisper_installed() -> bool:
    """检查 Whisper 是否已安装"""
    try:
        import whisper
        return True
    except ImportError:
        return False


def check_ffmpeg_installed() -> bool:
    """检查 FFmpeg 是否已安装（用于提取音频）"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


class WhisperProcessor:
    """Whisper 语音转字幕处理器"""

    def __init__(self):
        self.whisper_available = check_whisper_installed()
        self.ffmpeg_available = check_ffmpeg_installed()
        self.model_cache = {}

    def get_status(self) -> Dict[str, Any]:
        """获取 Whisper 状态信息"""
        return {
            "whisper_available": self.whisper_available,
            "ffmpeg_available": self.ffmpeg_available,
            "ready": self.whisper_available and self.ffmpeg_available,
            "models": ["tiny", "base", "small", "medium", "large-v3"],
            "languages": {
                "auto": "自动检测",
                "zh": "中文",
                "yue": "粤语",
                "en": "英语",
            }
        }

    def extract_audio(self, video_path: str, audio_path: str) -> bool:
        """从视频文件中提取音频"""
        if not self.ffmpeg_available:
            raise RuntimeError("FFmpeg 未安装")

        try:
            cmd = [
                "ffmpeg", "-i", video_path, "-vn",
                "-acodec", "pcm_s16le", "-ar", "16000",
                "-ac", "1", "-y", audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            return result.returncode == 0 and os.path.exists(audio_path)
        except Exception as e:
            raise RuntimeError(f"音频提取失败: {str(e)}")

    def load_model(self, model_name: str = "base"):
        """加载 Whisper 模型"""
        if not self.whisper_available:
            raise RuntimeError("Whisper 未安装")

        if model_name in self.model_cache:
            return self.model_cache[model_name]

        try:
            import whisper
            model = whisper.load_model(model_name)
            self.model_cache[model_name] = model
            return model
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {str(e)}")

    def transcribe(self, audio_path: str, model_name: str = "base",
                   language: Optional[str] = None, progress_callback=None) -> Dict[str, Any]:
        """转录音频文件"""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        model = self.load_model(model_name)

        # 如果有回调函数，启用 verbose 来获取进度
        options = {
            "task": "transcribe",
            "verbose": False,  # 不输出字幕片段
            "fp16": False  # 兼容性更好
        }

        # Whisper 不支持 yue（粤语），使用 zh 代替
        if language and language != "auto":
            if language == "yue":
                language = "zh"
            options["language"] = language

        try:
            # 捕获 Whisper 内部 tqdm 进度输出
            if progress_callback:
                from tqdm import tqdm as original_tqdm

                callback_ref = progress_callback

                class ProgressTqdm(original_tqdm):
                    """自定义 tqdm 拦截进度更新"""
                    def update(self, n=1):
                        super().update(n)
                        try:
                            if self.total and self.total > 0:
                                percent = int(self.n / self.total * 100)
                                # 映射到 40%-90% 区间
                                actual_progress = 40 + int(percent * 0.5)

                                # 计算速度和剩余时间
                                rate = self.format_dict.get('rate') or 0
                                elapsed = self.format_dict.get('elapsed', 0)

                                if rate and rate > 0:
                                    remaining_sec = (self.total - self.n) / rate
                                    remaining = f"{int(remaining_sec // 60):02d}:{int(remaining_sec % 60):02d}"
                                    speed_str = f"{rate:.1f}"
                                else:
                                    remaining = "--:--"
                                    speed_str = "0.0"

                                message = f"转录中 {percent}% | {self.n}/{self.total} | 剩余 {remaining} | {speed_str} fps"
                                callback_ref(actual_progress, message)
                        except Exception:
                            pass

                # 替换全局 tqdm
                import tqdm as tqdm_module
                tqdm_module.tqdm = ProgressTqdm

                try:
                    result = model.transcribe(audio_path, **options)
                finally:
                    # 恢复原始 tqdm
                    tqdm_module.tqdm = original_tqdm
            else:
                result = model.transcribe(audio_path, **options)

            return {
                "success": True,
                "text": result["text"],
                "language": result.get("language", language or "auto"),
                "segments": result.get("segments", []),
                "model": model_name,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name}

    def format_timestamp(self, seconds: float) -> str:
        """格式化 SRT 时间戳"""
        td = timedelta(seconds=seconds)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        secs = td.seconds % 60
        millis = td.microseconds // 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_srt(self, segments: List[Dict], output_path: str) -> bool:
        """生成 SRT 字幕文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    start = self.format_timestamp(segment['start'])
                    end = self.format_timestamp(segment['end'])
                    text = segment['text'].strip()
                    f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            return True
        except Exception:
            return False

    def generate_txt(self, segments: List[Dict], output_path: str) -> bool:
        """生成纯文本文件，按片段分行"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for segment in segments:
                    text = segment['text'].strip()
                    f.write(f"{text}\n")
            return True
        except Exception:
            return False

    def generate_vtt(self, segments: List[Dict], output_path: str) -> bool:
        """生成 WebVTT 字幕文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                for i, segment in enumerate(segments, 1):
                    # WebVTT 使用点号分隔毫秒
                    start = self.format_timestamp(segment['start']).replace(',', '.')
                    end = self.format_timestamp(segment['end']).replace(',', '.')
                    text = segment['text'].strip()
                    f.write(f"{start} --> {end}\n{text}\n\n")
            return True
        except Exception:
            return False

    def generate_json(self, result: Dict, output_path: str, original_filename: str = None) -> bool:
        """生成 JSON 结果文件"""
        try:
            # 添加原始文件名到结果中
            if original_filename:
                result["original_filename"] = original_filename

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def process_video(self, video_path: str, output_dir: str,
                     model_name: str = "base", language: Optional[str] = None,
                     base_filename: Optional[str] = None,
                     original_filename: Optional[str] = None,
                     progress_callback=None) -> Dict[str, Any]:
        """处理视频文件，生成字幕"""
        if not self.whisper_available:
            return {"success": False, "error": "Whisper 未安装"}
        if not self.ffmpeg_available:
            return {"success": False, "error": "FFmpeg 未安装"}

        if not base_filename:
            base_filename = os.path.splitext(os.path.basename(video_path))[0]

        audio_path = os.path.join(output_dir, f"{base_filename}_audio.wav")

        try:
            # 提取音频
            if progress_callback:
                progress_callback(20, "正在提取音频...")

            if not self.extract_audio(video_path, audio_path):
                return {"success": False, "error": "音频提取失败"}

            # 转录音频
            if progress_callback:
                progress_callback(40, "正在转录音频...")

            result = self.transcribe(audio_path, model_name, language, progress_callback)
            if not result["success"]:
                return result

            # 生成字幕文件
            if progress_callback:
                progress_callback(90, "正在生成字幕文件...")

            srt_path = os.path.join(output_dir, f"{base_filename}.srt")
            txt_path = os.path.join(output_dir, f"{base_filename}.txt")
            json_path = os.path.join(output_dir, f"{base_filename}.json")
            vtt_path = os.path.join(output_dir, f"{base_filename}.vtt")

            self.generate_srt(result["segments"], srt_path)
            self.generate_txt(result["segments"], txt_path)
            self.generate_json(result, json_path, original_filename)
            self.generate_vtt(result["segments"], vtt_path)

            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass

            return {
                "success": True,
                "text": result["text"],
                "language": result["language"],
                "model": model_name,
                "files": {
                    "srt": os.path.basename(srt_path),
                    "txt": os.path.basename(txt_path),
                    "json": os.path.basename(json_path),
                    "vtt": os.path.basename(vtt_path),
                },
                "segment_count": len(result["segments"]),
            }
        except Exception as e:
            return {"success": False, "error": f"处理失败: {str(e)}"}


whisper_processor = WhisperProcessor()
