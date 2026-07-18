import os
import urllib.request
import zipfile
from PySide6 import QtCore
from src.core.config import BIN_DIR, MODELS_DIR, FFMPEG_PATH, FFPROBE_PATH, FFMPEG_URL, MODEL_URLS
from src.core.utils import format_size, get_whisper_download_url, HAS_CUDA

class DownloadWorker(QtCore.QObject):
    progress_signal = QtCore.Signal(str, int)  # status text, percent
    finished_signal = QtCore.Signal(bool, str) # success, error_message
    
    def __init__(self, missing_items, selected_model_name, custom_url=None):
        super().__init__()
        self.missing_items = missing_items
        self.selected_model_name = selected_model_name
        self.custom_url = custom_url
        self.cancelled = False
        
    def cancel(self):
        self.cancelled = True
        
    def run(self):
        try:
            if "FFmpeg (Audio Converter)" in self.missing_items:
                if not self.download_and_extract_ffmpeg():
                    return
            if "Whisper.cpp (C++ Engine)" in self.missing_items:
                if not self.download_and_extract_whisper():
                    return
            if "Whisper Model" in self.missing_items:
                if not self.download_model():
                    return
            self.progress_signal.emit("Tải xuống hoàn tất!", 100)
            self.finished_signal.emit(True, "")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def download_file_with_progress(self, url, dest_path, desc):
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            block_size = 1024 * 128
            last_percent = -1
            
            with open(dest_path, 'wb') as f:
                while True:
                    if self.cancelled:
                        return False
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    f.write(buffer)
                    
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        if percent != last_percent:
                            self.progress_signal.emit(f"{desc}: {format_size(downloaded)} / {format_size(total_size)} ({percent}%)", percent)
                            last_percent = percent
                    else:
                        # If total_size is unknown, emit less frequently based on downloaded bytes
                        if downloaded // (1024 * 1024) != last_percent:
                            self.progress_signal.emit(f"{desc}: {format_size(downloaded)}", 50)
                            last_percent = downloaded // (1024 * 1024)
        return True

    def download_and_extract_ffmpeg(self):
        zip_path = os.path.join(BIN_DIR, "ffmpeg_temp.zip")
        self.progress_signal.emit("Đang chuẩn bị tải FFmpeg...", 0)
        
        if self.download_file_with_progress(FFMPEG_URL, zip_path, "Tải FFmpeg"):
            self.progress_signal.emit("Đang giải nén FFmpeg & FFprobe...", 95)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                extracted_count = 0
                for name in zip_ref.namelist():
                    if name.endswith("ffmpeg.exe"):
                        with zip_ref.open(name) as source, open(FFMPEG_PATH, 'wb') as target:
                            target.write(source.read())
                        extracted_count += 1
                    elif name.endswith("ffprobe.exe"):
                        with zip_ref.open(name) as source, open(FFPROBE_PATH, 'wb') as target:
                            target.write(source.read())
                        extracted_count += 1
                    if extracted_count >= 2:
                        break
            try:
                os.remove(zip_path)
            except:
                pass
            return True
        return False

    def download_and_extract_whisper(self):
        zip_path = os.path.join(BIN_DIR, "whisper_temp.zip")
        whisper_url = get_whisper_download_url()
        variant = "CUDA" if HAS_CUDA else "CPU (BLAS)"
        self.progress_signal.emit(f"Đang chuẩn bị tải Whisper.cpp ({variant})...", 0)
        
        if self.download_file_with_progress(whisper_url, zip_path, f"Tải Whisper Engine ({variant})"):
            self.progress_signal.emit("Đang giải nén Whisper Engine...", 95)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(BIN_DIR)
            try:
                os.remove(zip_path)
            except:
                pass
            return True
        return False

    def download_model(self):
        if self.custom_url:
            url = self.custom_url.strip()
            # Extract filename from URL
            filename = url.split("/")[-1]
            # Strip query params
            filename = filename.split("?")[0]
            if not filename.endswith(".bin"):
                filename += ".bin"
            if not filename.startswith("ggml-"):
                filename = "ggml-" + filename
        else:
            model_info = MODEL_URLS[self.selected_model_name]
            if isinstance(model_info, dict):
                url = model_info["url"]
                filename = model_info["filename"]
            else:
                url = model_info
                filename = url.split("/")[-1]
        dest_path = os.path.join(MODELS_DIR, filename)
        
        self.progress_signal.emit(f"Đang chuẩn bị tải mô hình {filename}...", 0)
        return self.download_file_with_progress(url, dest_path, f"Tải {filename}")


