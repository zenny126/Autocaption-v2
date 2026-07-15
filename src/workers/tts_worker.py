import os
import re
import shutil
import tempfile
import subprocess
from datetime import timedelta
from PySide6 import QtCore
from src.core.config import FFMPEG_PATH, CREATION_FLAGS

class TTSWorker(QtCore.QThread):
    log_signal = QtCore.Signal(str)
    progress_signal = QtCore.Signal(int)
    status_signal = QtCore.Signal(str)
    finished_signal = QtCore.Signal(bool, str) # success, saved_path
    
    def __init__(self, srt_path, ref_wav_path, output_dir, device="CPU", auto_speed=True):
        super().__init__()
        self.srt_path = srt_path
        self.ref_wav_path = ref_wav_path
        self.output_dir = output_dir
        self.device = device
        self.auto_speed = auto_speed
        self.cancelled = False
        self.current_process = None
        
    def cancel(self):
        self.cancelled = True
        if self.current_process:
            try:
                self.current_process.terminate()
            except:
                pass
                
    def run(self):
        try:
            self._run_impl()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log_signal.emit(f"\n[LỖI NGHIÊM TRỌNG TRONG TIẾN TRÌNH TTS]:\n{e}\n{tb}")
            self.finished_signal.emit(False, "")
            
    def _parse_srt(self, path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        try:
            import srt
            return list(srt.parse(content))
        except Exception as e:
            self.log_signal.emit(f"Cảnh báo: Lỗi sử dụng thư viện srt ({e}), chuyển sang parse thủ công...")
            
        # Fallback manual parser
        blocks = content.strip().replace('\r\n', '\n').split('\n\n')
        subs = []
        for b in blocks:
            lines = b.strip().split('\n')
            if len(lines) >= 3:
                try:
                    idx = int(lines[0])
                    ts_line = lines[1]
                    text = '\n'.join(lines[2:])
                    m = re.match(r'(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)', ts_line)
                    if m:
                        start = timedelta(hours=int(m.group(1)), minutes=int(m.group(2)), seconds=int(m.group(3)), milliseconds=int(m.group(4)))
                        end = timedelta(hours=int(m.group(5)), minutes=int(m.group(6)), seconds=int(m.group(7)), milliseconds=int(m.group(8)))
                        class DummySub:
                            def __init__(self, idx, start, end, content):
                                self.index = idx
                                self.start = start
                                self.end = end
                                self.content = content
                        subs.append(DummySub(idx, start, end, text))
                except:
                    pass
        return subs

    def _run_impl(self):
        if not os.path.exists(self.srt_path):
            self.log_signal.emit(f"LỖI: Không tìm thấy tệp phụ đề SRT: {self.srt_path}")
            self.finished_signal.emit(False, "")
            return
            
        if not os.path.exists(self.ref_wav_path):
            self.log_signal.emit(f"LỖI: Không tìm thấy tệp giọng mẫu: {self.ref_wav_path}")
            self.finished_signal.emit(False, "")
            return
            
        self.status_signal.emit("Đang phân tích tệp phụ đề...")
        subtitles = self._parse_srt(self.srt_path)
        if not subtitles:
            self.log_signal.emit("LỖI: Không đọc được phân đoạn phụ đề nào từ tệp SRT!")
            self.finished_signal.emit(False, "")
            return
            
        self.log_signal.emit(f"Đã đọc xong {len(subtitles)} dòng phụ đề.")
        
        # 1. Load XTTS-v2 model
        import torch
        from TTS.api import TTS
        
        self.status_signal.emit("Đang tải mô hình XTTS-v2...")
        self.log_signal.emit("Khởi động mô hình XTTS-v2 cục bộ...")
        
        model_device = "cuda" if (self.device == "GPU" and torch.cuda.is_available()) else "cpu"
        self.log_signal.emit(f"Thiết bị xử lý: {model_device.upper()}")
        
        try:
            # This will automatically download and cache model files at ~/.local/share/tts
            tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(model_device)
            self.log_signal.emit("Tải mô hình XTTS-v2 thành công!")
        except Exception as e:
            self.log_signal.emit(f"LỖI: Không khởi tạo được mô hình XTTS-v2: {e}")
            self.finished_signal.emit(False, "")
            return
            
        # Initialize pydub
        from pydub import AudioSegment
        AudioSegment.converter = FFMPEG_PATH
        
        # Determine total duration of timeline (last subtitle end time + 2 seconds buffer)
        last_sub = subtitles[-1]
        total_duration_ms = int(last_sub.end.total_seconds() * 1000) + 2000
        final_audio = AudioSegment.silent(duration=total_duration_ms)
        
        self.log_signal.emit(f"Khởi tạo dòng thời gian thuyết minh rỗng dài {total_duration_ms/1000:.2f} giây.")
        
        total_subs = len(subtitles)
        temp_files_to_cleanup = []
        
        for idx, sub in enumerate(subtitles):
            if self.cancelled:
                break
                
            text = sub.content.strip()
            # Clean up SRT formatting tags (like <i>, </i>, color, font tags, etc.)
            text = re.sub(r'<[^>]*>', '', text)
            
            if not text:
                continue
                
            self.status_signal.emit(f"Đang sinh giọng nói {idx+1}/{total_subs}...")
            self.log_signal.emit(f"Đang thuyết minh [{idx+1}/{total_subs}]: \"{text}\"")
            
            temp_wav = os.path.join(tempfile.gettempdir(), f"temp_tts_sub_{idx}.wav")
            temp_files_to_cleanup.append(temp_wav)
            
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except: pass
                
            try:
                # Run speech synthesis
                tts.tts_to_file(
                    text=text,
                    speaker_wav=self.ref_wav_path,
                    language="vi",
                    file_path=temp_wav
                )
            except Exception as tts_err:
                self.log_signal.emit(f"Cảnh báo: Lỗi thuyết minh dòng {idx+1}: {tts_err}")
                continue
                
            if not os.path.exists(temp_wav):
                self.log_signal.emit(f"Cảnh báo: Không tạo được file âm thanh cho dòng {idx+1}")
                continue
                
            # Load segment
            segment = AudioSegment.from_file(temp_wav)
            seg_duration_ms = len(segment)
            
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            srt_duration_ms = end_ms - start_ms
            
            # Check if duration matches
            if self.auto_speed and seg_duration_ms > srt_duration_ms and srt_duration_ms > 500:
                speed_factor = seg_duration_ms / srt_duration_ms
                # Cap speed factor at 2.0x
                if speed_factor > 2.0:
                    speed_factor = 2.0
                    
                self.log_signal.emit(f"   -> Câu thuyết minh dài hơn phụ đề ({seg_duration_ms/1000:.2f}s > {srt_duration_ms/1000:.2f}s). Tăng tốc {speed_factor:.2f}x...")
                
                sped_wav = os.path.join(tempfile.gettempdir(), f"temp_tts_sub_{idx}_speed.wav")
                temp_files_to_cleanup.append(sped_wav)
                if os.path.exists(sped_wav):
                    try: os.remove(sped_wav)
                    except: pass
                    
                # Run ffmpeg to change speed
                cmd = [
                    FFMPEG_PATH, "-y", "-i", temp_wav,
                    "-filter:a", f"atempo={speed_factor}", sped_wav
                ]
                self.current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATION_FLAGS)
                self.current_process.communicate()
                
                if os.path.exists(sped_wav) and os.path.getsize(sped_wav) > 0:
                    segment = AudioSegment.from_file(sped_wav)
            
            # Overlay segment at correct position on timeline
            final_audio = final_audio.overlay(segment, position=start_ms)
            self.progress_signal.emit(int((idx + 1) * 100 / total_subs))
            
        # Clean up all temp files
        for tf in temp_files_to_cleanup:
            if os.path.exists(tf):
                try: os.remove(tf)
                except: pass
                
        if self.cancelled:
            self.finished_signal.emit(False, "")
            return
            
        # Export final timeline audio file
        base_name = os.path.splitext(os.path.basename(self.srt_path))[0]
        out_path = os.path.join(self.output_dir, f"{base_name}_speech.wav")
        
        if os.path.exists(out_path):
            try: os.remove(out_path)
            except: pass
            
        self.status_signal.emit("Đang xuất file thuyết minh...")
        try:
            final_audio.export(out_path, format="wav")
            self.log_signal.emit(f"\n========================================\n"
                                 f"Thuyết minh hoàn tất thành công!\n"
                                 f"Đã lưu tệp tại: {out_path}\n"
                                 f"========================================")
            self.finished_signal.emit(True, out_path)
        except Exception as export_err:
            self.log_signal.emit(f"LỖI: Không thể xuất file kết quả: {export_err}")
            self.finished_signal.emit(False, "")
