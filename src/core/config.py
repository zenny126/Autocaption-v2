import os
import sys
import subprocess

CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Constants & Paths
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BIN_DIR = os.path.join(BASE_DIR, "bin")
MODELS_DIR = os.path.join(BIN_DIR, "models")
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg.exe")
FFPROBE_PATH = os.path.join(BIN_DIR, "ffprobe.exe")
WHISPER_CLI_PATH = os.path.join(BIN_DIR, "whisper-cli.exe")
WHISPER_MAIN_PATH = os.path.join(BIN_DIR, "main.exe")

# Download URLs
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
WHISPER_URL_BLAS = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-blas-bin-x64.zip"
WHISPER_URL_CUDA_12 = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-cublas-12.4.0-bin-x64.zip"
WHISPER_URL_CUDA_11 = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-cublas-11.8.0-bin-x64.zip"

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
