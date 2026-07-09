#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper Offline Subtitler - PySide6 GUI
Rewritten from Tkinter to match the modern AutoCaption look & feel, 
while preserving the local Whisper.cpp and FFmpeg subprocess execution logic.

Copyright (c) 2026 Zenny126. Licensed under the MIT License.
"""

import os
import sys
import shutil
import threading
import subprocess
import urllib.request
import zipfile
from PySide6 import QtWidgets, QtCore, QtGui

# Constants & Paths
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")
MODELS_DIR = os.path.join(BIN_DIR, "models")
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg.exe")
WHISPER_CLI_PATH = os.path.join(BIN_DIR, "whisper-cli.exe")
WHISPER_MAIN_PATH = os.path.join(BIN_DIR, "main.exe")

# Download URLs
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
WHISPER_URL = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-blas-bin-x64.zip"

MODEL_URLS = {
    "Tiny (~75MB)": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "Base (~140MB - Khuyên dùng)": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "Small (~466MB)": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "Medium (~1.5GB)": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    "Large V3 Turbo (~1.5GB)": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
    "Belle Chinese Large V3 Turbo (~1.5GB)": {
        "url": "https://huggingface.co/BELLE-2/Belle-whisper-large-v3-turbo-zh-ggml/resolve/main/ggml-model.bin",
        "filename": "ggml-belle-whisper-large-v3-turbo-zh.bin"
    }
}

# Ensure directories exist
os.makedirs(BIN_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

SUPPORTED_EXTS = {".mp4", ".mkv", ".avi", ".mp3", ".wav", ".m4a", ".flac", ".mov", ".ogg", ".webm"}

# Helper function to format bytes
def format_size(bytes_num):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024
    return f"{bytes_num:.1f} TB"

def get_whisper_exe():
    candidates = [
        WHISPER_CLI_PATH,
        WHISPER_MAIN_PATH,
        os.path.join(BIN_DIR, "Release", "whisper-cli.exe"),
        os.path.join(BIN_DIR, "Release", "main.exe"),
    ]
    return next((p for p in candidates if os.path.exists(p)), None)

def open_directory(path):
    if path and os.path.isdir(path):
        try:
            os.startfile(path)
        except Exception:
            pass

def load_stylesheet():
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoCaption.css")
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""

def check_system_assets():
    missing = []
    if not os.path.exists(FFMPEG_PATH):
        missing.append("FFmpeg (Audio Converter)")
        
    whisper_exe = get_whisper_exe()
    if not whisper_exe:
        missing.append("Whisper.cpp (C++ Engine)")
        
    models = []
    if os.path.exists(MODELS_DIR):
        models = [f for f in os.listdir(MODELS_DIR) if f.endswith(".bin") and f.startswith("ggml-")]
    if not models:
        missing.append("Whisper Model")
        
    return missing

def check_gpu_available():
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        res = subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags,
            timeout=2
        )
        return res.returncode == 0
    except:
        return False

HAS_CUDA = check_gpu_available()


class CardFrame(QtWidgets.QFrame):
    double_clicked = QtCore.Signal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(90, 100)
        self.setProperty("class", "CardFrame")
        
        card_layout = QtWidgets.QVBoxLayout(self)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(4)
        card_layout.setAlignment(QtCore.Qt.AlignCenter)
        
        icon_lbl = QtWidgets.QLabel()
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        icon_provider = QtWidgets.QFileIconProvider()
        file_info = QtCore.QFileInfo(path)
        icon = icon_provider.icon(file_info)
        icon_lbl.setPixmap(icon.pixmap(40, 40))
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        
        text_lbl = QtWidgets.QLabel()
        text_lbl.setStyleSheet("font-size: 10px; color: #cbd5e1; border: none; background: transparent;")
        text_lbl.setAlignment(QtCore.Qt.AlignCenter)
        
        filename = os.path.basename(path)
        metrics = QtGui.QFontMetrics(text_lbl.font())
        elided = metrics.elidedText(filename, QtCore.Qt.ElideRight, 78)
        text_lbl.setText(elided)
        
        card_layout.addWidget(icon_lbl)
        card_layout.addWidget(text_lbl)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.path)


class DropZoneFrame(QtWidgets.QFrame):
    files_dropped = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if os.path.splitext(url.toLocalFile())[1].lower() in SUPPORTED_EXTS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        dropped_files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and os.path.splitext(file_path)[1].lower() in SUPPORTED_EXTS:
                dropped_files.append(file_path)
        if dropped_files:
            self.files_dropped.emit(dropped_files)


class SuccessPopup(QtWidgets.QDialog):
    def __init__(self, saved_paths, failed_files, parent=None):
        super().__init__(parent)
        self.saved_paths = saved_paths
        
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(480, 280)
        
        frame = QtWidgets.QFrame(self)
        frame.setObjectName("SuccessPopupFrame")
        
        effect = QtWidgets.QGraphicsDropShadowEffect()
        effect.setBlurRadius(30)
        effect.setColor(QtGui.QColor("#404040"))
        effect.setOffset(0, 0)
        frame.setGraphicsEffect(effect)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        
        if len(saved_paths) > 0 and len(failed_files) == 0:
            title_text = "Thành công"
            body_text = "Tạo phụ đề hoàn tất thành công!"
        elif len(saved_paths) > 0 and len(failed_files) > 0:
            title_text = "Cảnh báo"
            body_text = "Đã tạo một số phụ đề, nhưng có tệp bị lỗi.\nVui lòng kiểm tra lại định dạng âm thanh tệp lỗi."
        else:
            title_text = "Thất bại"
            body_text = "Không thể tạo phụ đề cho tệp nào.\nVui lòng kiểm tra lại định dạng tệp."

        header_layout = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel(title_text)
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF; border: none; background: transparent;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setObjectName("SuccessCloseBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)
        
        body_lbl = QtWidgets.QLabel(body_text)
        body_lbl.setStyleSheet("font-size: 14px; color: #D4D4D4; border: none; background: transparent;")
        layout.addWidget(body_lbl)
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setObjectName("SuccessList")
        self.list_widget.setFixedHeight(90)
        
        for p in saved_paths:
            item = QtWidgets.QListWidgetItem(f"✓ {os.path.basename(p)}")
            item.setForeground(QtGui.QColor("#22c55e"))
            item.setToolTip(p)
            self.list_widget.addItem(item)
            
        for p, reason in failed_files:
            item = QtWidgets.QListWidgetItem(f"✗ {os.path.basename(p)} ({reason})")
            item.setForeground(QtGui.QColor("#ef4444"))
            item.setToolTip(f"Thất bại: {p}\nLý do: {reason}")
            self.list_widget.addItem(item)
            
        layout.addWidget(self.list_widget)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(12)
        
        open_folder_btn = QtWidgets.QPushButton("Mở thư mục")
        open_folder_btn.setObjectName("SuccessOpenFolderBtn")
        open_folder_btn.clicked.connect(self.on_open_folder)
        open_folder_btn.setEnabled(len(saved_paths) > 0)
        
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setObjectName("SuccessOkBtn")
        ok_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(open_folder_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(frame)
        
    def on_open_folder(self):
        if self.saved_paths:
            open_directory(os.path.dirname(self.saved_paths[0]))
        self.accept()


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
            block_size = 1024 * 64
            
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
                        self.progress_signal.emit(f"{desc}: {format_size(downloaded)} / {format_size(total_size)} ({percent}%)", percent)
                    else:
                        self.progress_signal.emit(f"{desc}: {format_size(downloaded)}", 50)
        return True

    def download_and_extract_ffmpeg(self):
        zip_path = os.path.join(BIN_DIR, "ffmpeg_temp.zip")
        self.progress_signal.emit("Đang chuẩn bị tải FFmpeg...", 0)
        
        if self.download_file_with_progress(FFMPEG_URL, zip_path, "Tải FFmpeg"):
            self.progress_signal.emit("Đang giải nén FFmpeg.exe...", 95)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for name in zip_ref.namelist():
                    if name.endswith("ffmpeg.exe"):
                        with zip_ref.open(name) as source, open(FFMPEG_PATH, 'wb') as target:
                            target.write(source.read())
                        break
            try:
                os.remove(zip_path)
            except:
                pass
            return True
        return False

    def download_and_extract_whisper(self):
        zip_path = os.path.join(BIN_DIR, "whisper_temp.zip")
        self.progress_signal.emit("Đang chuẩn bị tải Whisper.cpp...", 0)
        
        if self.download_file_with_progress(WHISPER_URL, zip_path, "Tải Whisper Engine"):
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


class DownloaderDialog(QtWidgets.QDialog):
    def __init__(self, missing_items, parent=None):
        super().__init__(parent)
        self.missing_items = missing_items
        self.setWindowTitle("Tải tài nguyên hệ thống")
        self.resize(520, 520)
        self.setStyleSheet("QDialog { background-color: #121214; }")
        
        self.thread = None
        self.worker = None
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        
        lbl_title = QtWidgets.QLabel("TẢI TÀI NGUYÊN HỆ THỐNG")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #7c4dff;")
        lbl_title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(lbl_title)
        
        lbl_desc = QtWidgets.QLabel("Ứng dụng cần tải một số tệp thực thi nhẹ để chạy offline (chỉ tải một lần duy nhất).")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #9fa8da; font-size: 11px;")
        layout.addWidget(lbl_desc)
        
        frame_items = QtWidgets.QFrame()
        frame_items.setStyleSheet("background-color: #1e1e24; border: 1px solid #2e2e38; border-radius: 12px;")
        items_layout = QtWidgets.QVBoxLayout(frame_items)
        items_layout.setContentsMargins(16, 16, 16, 16)
        
        lbl_items_title = QtWidgets.QLabel("Các tệp cần tải:")
        lbl_items_title.setStyleSheet("font-weight: bold; color: #ffffff; border: none; background: transparent;")
        items_layout.addWidget(lbl_items_title)
        
        for item in self.missing_items:
            lbl_item = QtWidgets.QLabel(f"• {item}")
            lbl_item.setStyleSheet("color: #9fa8da; border: none; background: transparent;")
            items_layout.addWidget(lbl_item)
            
        layout.addWidget(frame_items)
        
        self.model_combo_row = QtWidgets.QHBoxLayout()
        self.lbl_select_model = QtWidgets.QLabel("Chọn kích thước mô hình:")
        self.lbl_select_model.setStyleSheet("color: #ffffff;")
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.addItems(list(MODEL_URLS.keys()))
        self.model_combo.setCurrentIndex(1) # Default Base
        
        self.model_combo_row.addWidget(self.lbl_select_model)
        self.model_combo_row.addWidget(self.model_combo, 1)
        
        if "Whisper Model" in self.missing_items:
            layout.addLayout(self.model_combo_row)
            
            # Custom model check & input
            self.custom_model_layout = QtWidgets.QVBoxLayout()
            self.custom_model_layout.setSpacing(6)
            
            self.chk_custom_model = QtWidgets.QCheckBox("Nhập link tải mô hình tùy chọn (GGML)")
            self.chk_custom_model.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent; border: none;")
            self.custom_model_layout.addWidget(self.chk_custom_model)
            
            self.edit_custom_url = QtWidgets.QLineEdit()
            self.edit_custom_url.setPlaceholderText("Ví dụ: https://huggingface.co/.../ggml-base.bin")
            self.edit_custom_url.setEnabled(False)
            self.custom_model_layout.addWidget(self.edit_custom_url)
            
            self.lbl_custom_info = QtWidgets.QLabel(
                "Yêu cầu: Link trực tiếp tải tệp định dạng GGML (*.bin).\n"
                "Tên mô hình tải về bắt buộc phải có tiền tố 'ggml-' và đuôi '.bin' (ví dụ: ggml-model.bin) để phần mềm nhận dạng được. Nếu tên tệp tải về chưa đúng chuẩn này, hệ thống sẽ tự động thêm tiền tố 'ggml-'."
            )
            self.lbl_custom_info.setWordWrap(True)
            self.lbl_custom_info.setStyleSheet("color: #8a8d9a; font-size: 10px; font-style: italic; border: none; background: transparent;")
            self.custom_model_layout.addWidget(self.lbl_custom_info)
            
            layout.addLayout(self.custom_model_layout)
            self.chk_custom_model.toggled.connect(self.toggle_custom_model_input)
            
        self.lbl_status = QtWidgets.QLabel("Sẵn sàng tải xuống...")
        self.lbl_status.setStyleSheet("color: #ffffff;")
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.lbl_status)
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_download = QtWidgets.QPushButton("Bắt đầu Tải")
        self.btn_download.setObjectName("StartBtn")
        self.btn_download.setStyleSheet("min-width: 120px; min-height: 36px; background-color: #7c4dff; color: white; border-radius: 18px; font-weight: bold;")
        
        self.btn_cancel = QtWidgets.QPushButton("Hủy bỏ")
        self.btn_cancel.setObjectName("SuccessCloseBtn")
        self.btn_cancel.setStyleSheet("min-width: 100px; min-height: 36px; background-color: #2c2c35; color: white; border-radius: 18px;")
        
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.btn_download.clicked.connect(self.start_download)
        self.btn_cancel.clicked.connect(self.cancel_download)
        
    def toggle_custom_model_input(self, checked):
        self.model_combo.setEnabled(not checked)
        self.edit_custom_url.setEnabled(checked)

    def start_download(self):
        custom_url = None
        if "Whisper Model" in self.missing_items and self.chk_custom_model.isChecked():
            url_text = self.edit_custom_url.text().strip()
            if not url_text or not (url_text.startswith("http://") or url_text.startswith("https://")):
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng nhập link tải http:// hoặc https:// hợp lệ!")
                return
            custom_url = url_text

        self.btn_download.setEnabled(False)
        self.model_combo.setEnabled(False)
        if hasattr(self, "chk_custom_model"):
            self.chk_custom_model.setEnabled(False)
            self.edit_custom_url.setEnabled(False)
        
        self.thread = QtCore.QThread()
        self.worker = DownloadWorker(self.missing_items, self.model_combo.currentText(), custom_url)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.download_finished)
        
        self.thread.start()
        
    def cancel_download(self):
        if self.worker:
            self.worker.cancel()
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.reject()
        
    def update_progress(self, status_text, percent):
        self.lbl_status.setText(status_text)
        self.progress_bar.setValue(percent)
        
    def download_finished(self, success, error_msg):
        self.thread.quit()
        self.thread.wait()
        
        if success:
            QtWidgets.QMessageBox.information(self, "Hoàn tất", "Tất cả tài nguyên đã được tải thành công!")
            self.accept()
        else:
            if self.worker and self.worker.cancelled:
                self.reject()
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi", f"Tải xuống thất bại:\n{error_msg}")
                self.btn_download.setEnabled(True)
                if hasattr(self, "chk_custom_model"):
                    self.chk_custom_model.setEnabled(True)
                    if self.chk_custom_model.isChecked():
                        self.edit_custom_url.setEnabled(True)
                        self.model_combo.setEnabled(False)
                    else:
                        self.model_combo.setEnabled(True)
                        self.edit_custom_url.setEnabled(False)
                else:
                    self.model_combo.setEnabled(True)


class TranscribeWorker(QtCore.QObject):
    log_signal = QtCore.Signal(str)
    progress_signal = QtCore.Signal(int)
    status_signal = QtCore.Signal(str)
    finished_signal = QtCore.Signal(bool, list, list) # success, saved_paths, failed_files
    
    def __init__(self, input_files, output_folder, save_same_folder, model_filename, lang_text, thread_count, device):
        super().__init__()
        self.input_files = input_files
        self.output_folder = output_folder
        self.save_same_folder = save_same_folder
        self.model_filename = model_filename
        self.lang_text = lang_text
        self.thread_count = thread_count
        self.device = device
        self.current_process = None
        self.cancelled = False
        
    def cancel(self):
        self.cancelled = True
        if self.current_process:
            try:
                self.current_process.terminate()
            except:
                pass
                
    def run(self):
        saved_paths = []
        failed_files = []
        total_files = len(self.input_files)
        
        # 1. Convert all input files to WAV sequentially
        temp_wav_files = []
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
        for idx, input_file in enumerate(self.input_files):
            if self.cancelled:
                break
                
            filename = os.path.basename(input_file)
            self.status_signal.emit(f"Đang chuyển đổi tệp {idx+1}/{total_files}: {filename}...")
            self.log_signal.emit(f"FFmpeg: Chuyển đổi {filename} sang WAV 16kHz...")
            
            temp_wav = os.path.join(BIN_DIR, f"temp_transcribe_{idx}.wav")
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except: pass
                
            ffmpeg_cmd = [
                FFMPEG_PATH, "-y", "-i", input_file,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", temp_wav
            ]
            
            self.current_process = subprocess.Popen(
                ffmpeg_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                creationflags=creation_flags
            )
            
            _, stderr = self.current_process.communicate()
            
            if self.cancelled:
                break
                
            if self.current_process.returncode != 0 or not os.path.exists(temp_wav):
                err_msg = stderr.decode('utf-8', errors='ignore')
                self.log_signal.emit(f"LỖI: FFmpeg chuyển đổi thất bại cho {filename}:\n{err_msg}")
                failed_files.append((input_file, "FFmpeg failed"))
                continue
                
            temp_wav_files.append((input_file, temp_wav))
            # Conversion progress contributes to first 30%
            self.progress_signal.emit(int(((idx + 1) * 30) / total_files))
            
        if self.cancelled or not temp_wav_files:
            self._cleanup_temp_files([w for _, w in temp_wav_files])
            self.finished_signal.emit(False, [], failed_files)
            return
            
        # 2. Run whisper-cli.exe once for all successfully converted files
        whisper_exe = get_whisper_exe()
        if not whisper_exe:
            self.log_signal.emit("LỖI: Không tìm thấy tệp thực thi whisper-cli.exe hoặc main.exe!")
            self.finished_signal.emit(False, [], [(f, "Whisper engine missing") for f, _ in temp_wav_files])
            self._cleanup_temp_files([w for _, w in temp_wav_files])
            return
            
        model_path = os.path.join(MODELS_DIR, self.model_filename)
        
        lang_mapping = {
            "Tự động phát hiện (Auto)": "auto",
            "Tiếng Việt (vi)": "vi",
            "Tiếng Anh (en)": "en",
            "Tiếng Trung (zh)": "zh",
            "Tiếng Nhật (ja)": "ja",
            "Tiếng Pháp (fr)": "fr"
        }
        lang_code = lang_mapping.get(self.lang_text, "auto")
        
        whisper_cmd = [
            whisper_exe,
            "-m", model_path,
            "-osrt",
            "-l", lang_code,
            "-t", str(self.thread_count)
        ]
        
        if self.device == "CPU":
            whisper_cmd.append("-ng")
            
        # Append all temp WAV files
        for _, temp_wav in temp_wav_files:
            whisper_cmd.append(temp_wav)
            
        self.status_signal.emit("Đang dịch tự động (chỉ load model 1 lần)...")
        self.log_signal.emit(f"\n========================================\n"
                             f"Chạy Whisper một lần duy nhất cho {len(temp_wav_files)} tệp...\n"
                             f"Lệnh: {' '.join([os.path.basename(c) for c in whisper_cmd])}\n"
                             f"========================================")
                             
        self.current_process = subprocess.Popen(
            whisper_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creation_flags
        )
        
        current_file_idx = 0
        while True:
            line = self.current_process.stdout.readline()
            if not line and self.current_process.poll() is not None:
                break
            if line:
                clean_line = line.strip()
                if clean_line:
                    self.log_signal.emit(clean_line)
                    # Track progress across multiple files
                    if "%" in clean_line:
                        try:
                            parts = clean_line.split()
                            for p in parts:
                                if p.endswith("%"):
                                    pct = int(p[:-1])
                                    file_progress = int((current_file_idx * 70) / total_files) + int((pct * 70) / (total_files * 100))
                                    self.progress_signal.emit(30 + file_progress)
                        except:
                            pass
                    if "processing" in clean_line.lower() and ".wav" in clean_line.lower():
                        for idx, (_, temp_wav) in enumerate(temp_wav_files):
                            if os.path.basename(temp_wav) in clean_line:
                                current_file_idx = idx
                                break
                                
        return_code = self.current_process.wait()
        
        if self.cancelled:
            self._cleanup_temp_files([w for _, w in temp_wav_files])
            self.finished_signal.emit(False, [], [])
            return
            
        if return_code != 0:
            self.log_signal.emit(f"LỖI: Whisper.cpp kết thúc với mã lỗi {return_code}")
            failed_files.extend([(f, f"Whisper failed (code {return_code})") for f, _ in temp_wav_files])
        else:
            # 3. Post-process and move SRT files
            for idx, (input_file, temp_wav) in enumerate(temp_wav_files):
                filename = os.path.basename(input_file)
                base_name = os.path.splitext(filename)[0]
                out_dir = os.path.dirname(input_file) if self.save_same_folder else self.output_folder
                output_file = os.path.join(out_dir, f"{base_name}.srt")
                
                # Check for possible output names in BIN_DIR
                possible_outputs = [
                    os.path.join(BIN_DIR, f"temp_transcribe_{idx}.wav.srt"),
                    os.path.join(BIN_DIR, f"temp_transcribe_{idx}.srt"),
                ]
                
                found_srt = None
                for po in possible_outputs:
                    if os.path.exists(po):
                        found_srt = po
                        break
                        
                if found_srt:
                    try:
                        if os.path.exists(output_file):
                            try: os.remove(output_file)
                            except: pass
                        shutil.move(found_srt, output_file)
                        self.log_signal.emit(f"Hoàn tất: {output_file}")
                        saved_paths.append(output_file)
                    except Exception as move_err:
                        self.log_signal.emit(f"LỖI di chuyển file phụ đề cho {filename}: {move_err}")
                        failed_files.append((input_file, "Failed to move SRT"))
                else:
                    self.log_signal.emit(f"LỖI: Không tìm thấy file phụ đề được tạo cho {filename}!")
                    failed_files.append((input_file, "Subtitle output missing"))
                    
        # Cleanup
        self._cleanup_temp_files([w for _, w in temp_wav_files])
        self.progress_signal.emit(100)
        
        if self.cancelled:
            self.finished_signal.emit(False, [], [])
        else:
            self.finished_signal.emit(True, saved_paths, failed_files)
            
    def _cleanup_temp_files(self, file_paths):
        for path in file_paths:
            if os.path.exists(path):
                try: os.remove(path)
                except: pass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self._running = False
        self._worker_thread = None
        self._worker = None
        self._input_files_list = []

        self._setup_theme()
        self._build_ui()
        self._load_settings()
        self._refresh_models()

    def _setup_theme(self):
        QtWidgets.QApplication.setStyle("Fusion")
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#000000"))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#0A0A0A"))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#000000"))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor("#0A0A0A"))
        palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#171717"))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#404040"))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#FFFFFF"))
        QtWidgets.QApplication.setPalette(palette)
        
        style = load_stylesheet()
        if style:
            QtWidgets.QApplication.instance().setStyleSheet(style)

    def _build_ui(self):
        self.setWindowTitle("AutoCaption - Whisper Offline Subtitler")
        self.resize(600, 850)
        self.setMinimumSize(550, 800)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Top bar
        top = QtWidgets.QFrame(self)
        top.setObjectName("TopBar")
        top_layout = QtWidgets.QHBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 12)
        
        title = QtWidgets.QLabel("AutoCaption")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self._btn_toggle_log = QtWidgets.QPushButton("Show Log")
        self._btn_toggle_log.setObjectName("ToggleLogBtn")
        self._btn_toggle_log.clicked.connect(self._toggle_log_panel)
        top_layout.addWidget(self._btn_toggle_log)
        main_layout.addWidget(top)

        # Content layout
        content = QtWidgets.QHBoxLayout()
        content.setSpacing(16)

        # Left panel (Form)
        left_card = QtWidgets.QFrame(self)
        left_card.setObjectName("LeftCard")
        left_layout = QtWidgets.QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        self._build_form(left_layout)
        content.addWidget(left_card, 1)

        # Right panel (Log)
        self._log_panel = QtWidgets.QFrame(self)
        self._log_panel.setObjectName("LogPanel")
        right_layout = QtWidgets.QVBoxLayout(self._log_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)

        self._build_log(right_layout)
        content.addWidget(self._log_panel, 1)

        main_layout.addLayout(content, 1)

        # Status bar
        status = QtWidgets.QFrame(self)
        status.setObjectName("StatusFrame")
        status_layout = QtWidgets.QHBoxLayout(status)
        status_layout.setContentsMargins(12, 8, 12, 8)
        self._status_label = QtWidgets.QLabel("Sẵn sàng")
        self._status_label.setStyleSheet("color: #cbd5e1;")
        status_layout.addWidget(self._status_label)
        main_layout.addWidget(status)

    def _build_form(self, parent_layout):
        title_style = """
            color: #A3A3A3;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
        """
        
        def add_glow(widget, color="#FFFFFF", radius=15):
            effect = QtWidgets.QGraphicsDropShadowEffect()
            effect.setBlurRadius(radius)
            effect.setColor(QtGui.QColor(color))
            effect.setOffset(0, 0)
            widget.setGraphicsEffect(effect)

        # 1. Input Media Group
        input_group = QtWidgets.QFrame()
        input_group.setProperty("class", "GroupFrame")
        input_layout = QtWidgets.QVBoxLayout(input_group)
        input_layout.setContentsMargins(20, 20, 20, 20)
        input_layout.setSpacing(12)

        input_header_layout = QtWidgets.QHBoxLayout()
        lbl_input_title = QtWidgets.QLabel("1. Đầu vào (Media Files)")
        lbl_input_title.setStyleSheet(title_style)
        input_header_layout.addWidget(lbl_input_title)
        input_header_layout.addStretch()
        
        self._btn_browse_input = QtWidgets.QPushButton("Chọn tệp")
        self._btn_browse_input.setProperty("class", "NormalBtn")
        self._btn_clear_input = QtWidgets.QPushButton("Xóa hết")
        self._btn_clear_input.setProperty("class", "NormalBtn")
        input_header_layout.addWidget(self._btn_browse_input)
        input_header_layout.addWidget(self._btn_clear_input)
        input_layout.addLayout(input_header_layout)

        # Drop Zone Frame
        self._drop_zone = DropZoneFrame()
        self._drop_zone.setObjectName("DropZone")
        self._drop_zone.setMinimumHeight(150)
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        
        drop_layout = QtWidgets.QVBoxLayout(self._drop_zone)
        drop_layout.setContentsMargins(10, 10, 10, 10)
        self._lbl_drop = QtWidgets.QLabel("Kéo & Thả tệp âm thanh/video vào đây\n(hoặc nhấn Chọn tệp ở trên)")
        self._lbl_drop.setAlignment(QtCore.Qt.AlignCenter)
        self._lbl_drop.setStyleSheet("font-size: 13px; font-weight: 500; color: #737373; border: none; background: transparent;")
        drop_layout.addWidget(self._lbl_drop)

        # Scroll Area for files
        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFixedHeight(130)
        self._scroll_area.hide()
        
        scroll_content = QtWidgets.QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._files_layout = QtWidgets.QHBoxLayout(scroll_content)
        self._files_layout.setContentsMargins(4, 4, 4, 4)
        self._files_layout.setSpacing(8)
        self._files_layout.setAlignment(QtCore.Qt.AlignLeft)
        
        self._scroll_area.setWidget(scroll_content)
        drop_layout.addWidget(self._scroll_area)
        input_layout.addWidget(self._drop_zone)
        parent_layout.addWidget(input_group)

        # 2. Settings Group
        settings_group = QtWidgets.QFrame()
        settings_group.setProperty("class", "GroupFrame")
        settings_group.setMinimumHeight(330)
        settings_layout = QtWidgets.QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(14)

        lbl_settings_title = QtWidgets.QLabel("2. Cấu hình")
        lbl_settings_title.setStyleSheet(title_style)
        settings_layout.addWidget(lbl_settings_title)

        self._chk_same_folder = QtWidgets.QCheckBox("Lưu SRT cùng thư mục với tệp gốc")
        self._chk_same_folder.setStyleSheet("color: #E5E5E5; font-weight: 500; background: transparent; border: none;")
        self._chk_same_folder.setChecked(True)
        self._chk_same_folder.toggled.connect(self._toggle_output_folder)
        settings_layout.addWidget(self._chk_same_folder)
        
        # Spacer between checkbox and form
        settings_layout.addSpacing(6)

        # Form Layout for perfect alignment and spacing
        settings_form = QtWidgets.QFormLayout()
        settings_form.setVerticalSpacing(18)  # Spaced out vertical rows (18px)
        settings_form.setHorizontalSpacing(15)
        settings_form.setContentsMargins(0, 5, 0, 5)

        # Output row
        output_row = QtWidgets.QHBoxLayout()
        self._lbl_output = QtWidgets.QLabel("Thư mục lưu:")
        self._lbl_output.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._output_edit = QtWidgets.QLineEdit()
        self._btn_browse_output = QtWidgets.QPushButton("Chọn...")
        self._btn_browse_output.setProperty("class", "NormalBtn")
        output_row.addWidget(self._output_edit, 1)
        output_row.addWidget(self._btn_browse_output, 0)
        settings_form.addRow(self._lbl_output, output_row)

        # Model row with refresh and download options
        model_row = QtWidgets.QHBoxLayout()
        self._lbl_model = QtWidgets.QLabel("Mô hình:")
        self._lbl_model.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_model = QtWidgets.QComboBox()
        self._btn_refresh_models = QtWidgets.QPushButton("Tải lại")
        self._btn_refresh_models.setProperty("class", "NormalBtn")
        self._btn_dl_more = QtWidgets.QPushButton("Tải thêm...")
        self._btn_dl_more.setProperty("class", "NormalBtn")
        self._btn_dl_more.setStyleSheet("color: #7c4dff;")
        
        model_row.addWidget(self._cmb_model, 1)
        model_row.addWidget(self._btn_refresh_models, 0)
        model_row.addWidget(self._btn_dl_more, 0)
        settings_form.addRow(self._lbl_model, model_row)

        # Language row
        self._lbl_lang = QtWidgets.QLabel("Ngôn ngữ:")
        self._lbl_lang.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_lang = QtWidgets.QComboBox()
        self._cmb_lang.addItems(["Tự động phát hiện (Auto)", "Tiếng Việt (vi)", "Tiếng Anh (en)", "Tiếng Trung (zh)", "Tiếng Nhật (ja)", "Tiếng Pháp (fr)"])
        settings_form.addRow(self._lbl_lang, self._cmb_lang)

        # Device selection row
        self._lbl_device = QtWidgets.QLabel("Phần cứng:")
        self._lbl_device.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_device = QtWidgets.QComboBox()
        self._cmb_device.addItems(["CPU", "GPU (CUDA)"])
        settings_form.addRow(self._lbl_device, self._cmb_device)

        # Thread count row
        self._lbl_threads = QtWidgets.QLabel("Số luồng CPU:")
        self._lbl_threads.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        cpu_cores = os.cpu_count() or 4
        self._cmb_threads = QtWidgets.QComboBox()
        self._cmb_threads.addItems([str(i) for i in range(1, cpu_cores + 1)])
        self._cmb_threads.setCurrentText(str(min(4, cpu_cores)))
        settings_form.addRow(self._lbl_threads, self._cmb_threads)

        settings_layout.addLayout(settings_form)

        parent_layout.addWidget(settings_group)
        parent_layout.addSpacing(16)

        # 3. Actions
        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(24)
        parent_layout.addWidget(self._progress)
        


        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(12)
        self._btn_start = QtWidgets.QPushButton("BẮT ĐẦU TẠO PHỤ ĐỀ")
        self._btn_start.setObjectName("StartBtn")
        self._btn_start.setMinimumHeight(48)
        add_glow(self._btn_start, color="#7c4dff", radius=20)
        
        self._btn_cancel = QtWidgets.QPushButton("Hủy bỏ")
        self._btn_cancel.setObjectName("CancelBtn")
        self._btn_cancel.setProperty("class", "NormalBtn")
        self._btn_cancel.setMinimumHeight(48)
        self._btn_cancel.setEnabled(False)
        
        self._btn_open = QtWidgets.QPushButton("Mở thư mục")
        self._btn_open.setObjectName("OpenFolderBtn")
        self._btn_open.setProperty("class", "NormalBtn")
        self._btn_open.setMinimumHeight(48)
        
        btn_layout.addWidget(self._btn_start, 2)
        btn_layout.addWidget(self._btn_cancel, 1)
        btn_layout.addWidget(self._btn_open, 1)
        parent_layout.addLayout(btn_layout)
        parent_layout.addStretch()

        # Connect actions
        self._btn_browse_input.clicked.connect(self._browse_input)
        self._btn_clear_input.clicked.connect(self._clear_input_list)
        self._btn_browse_output.clicked.connect(self._browse_output)
        self._btn_refresh_models.clicked.connect(self._refresh_models)
        self._btn_dl_more.clicked.connect(self._open_downloader_for_models)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_open.clicked.connect(self._open_output_folder)
        
        self._toggle_output_folder()

    def _toggle_output_folder(self):
        is_same = self._chk_same_folder.isChecked()
        self._output_edit.setEnabled(not is_same)
        self._btn_browse_output.setEnabled(not is_same)

    def _build_log(self, parent_layout):
        label = QtWidgets.QLabel("Nhật ký & Tiến độ chạy")
        label.setStyleSheet("font-weight: bold; color: #A3A3A3;")
        parent_layout.addWidget(label)
        
        self._log_text = QtWidgets.QTextEdit()
        self._log_text.setObjectName("LogText")
        self._log_text.setReadOnly(True)
        self._log_text.setFont(QtGui.QFont("Consolas", 10))
        self._log_text.setPlainText("Nhật ký và tiến độ chi tiết sẽ hiển thị ở đây...")
        parent_layout.addWidget(self._log_text, 1)

    def _add_input_file(self, path):
        if path in self._input_files_list:
            return
        self._input_files_list.append(path)

    def _update_drop_zone_visuals(self):
        while self._files_layout.count():
            item = self._files_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        count = len(self._input_files_list)
        if count == 0:
            self._lbl_drop.show()
            self._scroll_area.hide()
        else:
            self._lbl_drop.hide()
            self._scroll_area.show()
            
            for path in self._input_files_list:
                card = CardFrame(path)
                card.double_clicked.connect(self._remove_file_by_path)
                self._files_layout.addWidget(card)

    def _remove_file_by_path(self, path):
        if path in self._input_files_list:
            self._input_files_list.remove(path)
            self._update_drop_zone_visuals()
            self._save_settings()

    def _clear_input_list(self):
        self._input_files_list.clear()
        self._update_drop_zone_visuals()
        self._save_settings()

    def _load_settings(self):
        settings = QtCore.QSettings("WhisperSubtitler", "Settings")
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")
            
        self._last_input_dir = settings.value("last_input_dir", default_dir)
        self._last_output_dir = settings.value("last_output_dir", default_dir)
        
        self._output_edit.setText(settings.value("output_folder", ""))
        self._chk_same_folder.setChecked(settings.value("save_same_folder", True, type=bool))
        
        lang = settings.value("language", "Tự động phát hiện (Auto)")
        self._cmb_lang.setCurrentText(lang)
        
        # Load saved device setting, fallback/force to CPU if no CUDA is available
        default_idx = 1 if HAS_CUDA else 0
        device_idx = int(settings.value("device_index", default_idx))
        if not HAS_CUDA:
            device_idx = 0
            
        self._cmb_device.setCurrentIndex(device_idx)
        if not HAS_CUDA:
            self._cmb_device.setItemText(1, "GPU (CUDA) - Not Available")
            self._cmb_device.model().item(1).setEnabled(False)
        
        threads = int(settings.value("threads", min(4, os.cpu_count() or 4)))
        self._cmb_threads.setCurrentText(str(threads))

        self._input_files_list.clear()
        input_files = settings.value("input_files_list", [])
        if isinstance(input_files, str):
            if input_files and os.path.exists(input_files):
                self._add_input_file(input_files)
        elif isinstance(input_files, list):
            for path in input_files:
                if os.path.exists(path):
                    self._add_input_file(path)
        self._update_drop_zone_visuals()

        self._log_panel.setVisible(False)
        self.setMinimumWidth(550)
        self.resize(600, 850)
        self._toggle_output_folder()

    def _save_settings(self):
        settings = QtCore.QSettings("WhisperSubtitler", "Settings")
        settings.setValue("output_folder", self._output_edit.text())
        settings.setValue("save_same_folder", self._chk_same_folder.isChecked())
        settings.setValue("language", self._cmb_lang.currentText())
        settings.setValue("device_index", self._cmb_device.currentIndex())
        settings.setValue("threads", int(self._cmb_threads.currentText()))
        settings.setValue("input_files_list", self._input_files_list)
        
        if self._cmb_model.count() > 0 and not self._cmb_model.currentText().startswith("Chưa có model"):
            settings.setValue("model_filename", self._cmb_model.currentText())
        
        if self._input_files_list and os.path.exists(os.path.dirname(self._input_files_list[0])):
            self._last_input_dir = os.path.dirname(self._input_files_list[0])
            
        output_text = self._output_edit.text()
        if output_text and os.path.exists(output_text):
            self._last_output_dir = output_text
            
        settings.setValue("last_input_dir", self._last_input_dir)
        settings.setValue("last_output_dir", self._last_output_dir)

    def _toggle_log_panel(self):
        show = not self._log_panel.isVisible()
        self._log_panel.setVisible(show)
        self.setMinimumWidth(950 if show else 550)
        self.resize(1100 if show else 600, self.height())
        self._btn_toggle_log.setText("Hide Log" if show else "Show Log")

    def _add_files_and_update(self, paths):
        for path in paths:
            self._add_input_file(path)
        self._update_drop_zone_visuals()
        if paths:
            self._last_input_dir = os.path.dirname(paths[0])
            if not self._output_edit.text():
                self._output_edit.setText(os.path.dirname(paths[0]))
                self._last_output_dir = os.path.dirname(paths[0])
        self._save_settings()

    def _on_files_dropped(self, file_paths):
        self._add_files_and_update(file_paths)

    def _browse_input(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Chọn tệp video/âm thanh", self._last_input_dir, 
            "Media Files (*.mp4 *.mkv *.avi *.mp3 *.wav *.m4a *.flac *.mov *.ogg *.webm)"
        )
        if paths:
            self._add_files_and_update(paths)

    def _browse_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu phụ đề", self._last_output_dir)
        if path:
            self._output_edit.setText(path)
            self._last_output_dir = path
            self._save_settings()

    def _refresh_models(self):
        models = []
        if os.path.exists(MODELS_DIR):
            for file in os.listdir(MODELS_DIR):
                if file.endswith(".bin") and file.startswith("ggml-"):
                    models.append(file)
        
        self._cmb_model.clear()
        if models:
            self._cmb_model.addItems(models)
            settings = QtCore.QSettings("WhisperSubtitler", "Settings")
            saved = settings.value("model_filename", "")
            if saved in models:
                self._cmb_model.setCurrentText(saved)
            else:
                self._cmb_model.setCurrentIndex(0)
        else:
            self._cmb_model.addItem("Chưa có model! Hãy tải.")

    def _open_downloader_for_models(self):
        dl = DownloaderDialog(["Whisper Model"], self)
        if dl.exec() == QtWidgets.QDialog.Accepted:
            self._refresh_models()

    def _on_start(self):
        if not self._input_files_list:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tệp âm thanh hoặc video đầu vào!")
            return

        if not self._chk_same_folder.isChecked() and not self._output_edit.text():
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục lưu phụ đề đầu ra!")
            return

        model_selected = self._cmb_model.currentText()
        if not model_selected or model_selected.startswith("Chưa có model"):
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn hoặc tải mô hình Whisper trước!")
            return

        self._save_settings()
        self._running = True
        self._btn_start.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._progress.setValue(0)
        
        # Clear log panel
        self._log_text.clear()
        self._log_text.setPlainText("Bắt đầu xử lý...")

        device_val = "CPU" if self._cmb_device.currentIndex() == 0 else "GPU"
        self._worker = TranscribeWorker(
            self._input_files_list, 
            self._output_edit.text(), 
            self._chk_same_folder.isChecked(), 
            model_selected, 
            self._cmb_lang.currentText(), 
            int(self._cmb_threads.currentText()),
            device_val
        )
        self._worker_thread = QtCore.QThread()
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._on_log)
        self._worker.status_signal.connect(self._on_status)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_finished)

        self._status_label.setText("Đang khởi tạo tiến trình dịch...")
        self._worker_thread.start()

    def _on_cancel(self):
        self._status_label.setText("Đang dừng...")
        if self._worker:
            self._worker.cancel()
        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_cancel.setEnabled(False)

    def _on_log(self, msg):
        self._log_text.append(msg)
        self._log_text.moveCursor(QtGui.QTextCursor.End)

    def _on_status(self, msg):
        self._status_label.setText(msg)

    def _on_progress(self, percent):
        self._progress.setValue(percent)

    def _on_finished(self, success, saved_paths, failed_files):
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()

        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_cancel.setEnabled(False)

        self._worker = None
        self._worker_thread = None

        if success:
            self._status_label.setText("Hoàn tất tạo phụ đề!")
            popup = SuccessPopup(saved_paths, failed_files, self)
            popup.exec()
        else:
            self._status_label.setText("Đã hủy hoặc xảy ra lỗi.")
            QtWidgets.QMessageBox.warning(self, "Thông tin", "Tiến trình đã được dừng hoặc xảy ra lỗi.")

    def _open_output_folder(self):
        if self._chk_same_folder.isChecked() and self._input_files_list:
            open_directory(os.path.dirname(self._input_files_list[0]))
        else:
            open_directory(self._output_edit.text())

    def closeEvent(self, event):
        self._save_settings()
        if self._running:
            self._on_cancel()
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    missing = check_system_assets()
    if missing:
        # Launch downloader dialog first
        downloader = DownloaderDialog(missing)
        if downloader.exec() == QtWidgets.QDialog.Accepted:
            window = MainWindow()
            window.show()
            sys.exit(app.exec())
        else:
            sys.exit(0)
    else:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
