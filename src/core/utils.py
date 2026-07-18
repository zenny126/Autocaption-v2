import os
import re
import subprocess
from src.core.config import FFMPEG_PATH, FFPROBE_PATH, CREATION_FLAGS, WHISPER_CLI_PATH, WHISPER_MAIN_PATH, BIN_DIR, MODELS_DIR, WHISPER_URL_CUDA_12, WHISPER_URL_CUDA_11, WHISPER_URL_BLAS

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
    import sys
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        from src.core.config import BASE_DIR
        base_dir = BASE_DIR
        
    css_path = os.path.join(base_dir, "src", "assets", "AutoCaption.css")
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""

def check_cuda_backend_exists():
    """Check if ggml-cuda.dll exists in the bin directory (including subdirs like Release/)."""
    search_dirs = [BIN_DIR, os.path.join(BIN_DIR, "Release")]
    for d in search_dirs:
        if os.path.exists(os.path.join(d, "ggml-cuda.dll")):
            return True
    return False

def get_cuda_version():
    """Detect CUDA version from nvidia-smi. Returns major version (e.g. 12, 11) or 0 if not available."""
    try:
        res = subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=CREATION_FLAGS,
            timeout=5
        )
        if res.returncode != 0:
            return 0
        output = res.stdout.decode("utf-8", errors="ignore")
        # Parse "CUDA Version: XX.Y" from nvidia-smi output
        match = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", output)
        if match:
            return int(match.group(1))
        return 0
    except:
        return 0

CUDA_VERSION = get_cuda_version()
HAS_CUDA = CUDA_VERSION > 0

def check_gpu_available():
    return HAS_CUDA

def check_system_assets():
    missing = []
    if not os.path.exists(FFMPEG_PATH) or not os.path.exists(FFPROBE_PATH):
        missing.append("FFmpeg (Audio Converter)")
        
    whisper_exe = get_whisper_exe()
    if not whisper_exe:
        missing.append("Whisper.cpp (C++ Engine)")
    elif HAS_CUDA and not check_cuda_backend_exists():
        # Whisper exe exists but CUDA backend is missing — need to re-download CUDA version
        missing.append("Whisper.cpp (C++ Engine)")
        
    models = []
    if os.path.exists(MODELS_DIR):
        models = [f for f in os.listdir(MODELS_DIR) if f.endswith(".bin") and f.startswith("ggml-")]
    if not models:
        missing.append("Whisper Model")
        
    return missing

def get_whisper_download_url():
    """Return the appropriate whisper.cpp download URL based on GPU/CUDA availability."""
    if CUDA_VERSION >= 12:
        return WHISPER_URL_CUDA_12
    elif CUDA_VERSION >= 11:
        return WHISPER_URL_CUDA_11
    else:
        return WHISPER_URL_BLAS
