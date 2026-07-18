import subprocess
import json
import os
from PySide6.QtGui import QImage
from src.core.config import FFMPEG_PATH, FFPROBE_PATH, CREATION_FLAGS

class VideoReader:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.fps = 0.0
        self.total_frames = 0
        self.duration = 0.0
        self.filepath = ""

    def open(self, filepath: str) -> bool:
        """Mở file video và đọc các thông số cơ bản bằng ffprobe."""
        self.filepath = filepath
        
        command = [
            FFPROBE_PATH, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration", 
            "-of", "json", filepath
        ]
        
        try:
            result = subprocess.run(command, capture_output=True, text=True, creationflags=CREATION_FLAGS)
            info = json.loads(result.stdout)
            if not info.get("streams"):
                return False
                
            stream = info["streams"][0]
            
            self.width = int(stream.get("width", 0))
            self.height = int(stream.get("height", 0))
            
            # Tính fps từ r_frame_rate
            fps_str = stream.get("r_frame_rate", "0/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                self.fps = float(num) / float(den) if float(den) != 0 else 0.0
            else:
                self.fps = float(fps_str)
                
            self.duration = float(stream.get("duration", 0.0))
            if self.duration > 0 and self.fps > 0:
                self.total_frames = int(self.duration * self.fps)
            else:
                self.total_frames = 0
                
            return True
        except Exception as e:
            print(f"Error reading video info: {e}")
            return False

    def get_qimage_at(self, frame_index: int) -> QImage:
        """Trích xuất khung hình tĩnh bằng ffmpeg qua pipe."""
        if self.fps <= 0 or not self.filepath:
            return QImage()
            
        frame_index = max(0, min(frame_index, self.total_frames - 1))
        time_sec = frame_index / self.fps

        command = [
            FFMPEG_PATH,
            "-ss", str(time_sec),
            "-i", self.filepath,
            "-frames:v", "1",
            "-f", "image2pipe",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-v", "quiet",
            "-"
        ]
        
        try:
            process = subprocess.run(command, capture_output=True, creationflags=CREATION_FLAGS)
            raw_image = process.stdout
            
            if not raw_image:
                return QImage()
                
            # Tạo QImage từ dữ liệu nhị phân thô
            q_img = QImage(raw_image, self.width, self.height, self.width * 3, QImage.Format_RGB888)
            return q_img.copy()
        except Exception as e:
            print(f"Error extracting frame: {e}")
            return QImage()

    def close(self):
        """Giải phóng tài nguyên."""
        self.filepath = ""
        self.width = 0
        self.height = 0
        self.fps = 0.0
        self.total_frames = 0
        self.duration = 0.0
