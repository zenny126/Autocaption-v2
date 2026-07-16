import os
import sys
import shutil
import subprocess
from PySide6 import QtCore
from src.core.config import BIN_DIR, MODELS_DIR, FFMPEG_PATH, CREATION_FLAGS
from src.core.utils import get_audio_codec, get_whisper_exe

class TranscribeWorker(QtCore.QThread):
    log_signal = QtCore.Signal(str)
    progress_signal = QtCore.Signal(int)
    status_signal = QtCore.Signal(str)
    finished_signal = QtCore.Signal(bool, list, list) # success, saved_paths, failed_files
    
    def __init__(self, input_files, output_folder, save_same_folder, model_filename, lang_text, thread_count, device, demucs_enabled, demucs_model="htdemucs"):
        super().__init__()
        self.input_files = input_files
        self.output_folder = output_folder
        self.save_same_folder = save_same_folder
        self.model_filename = model_filename
        self.lang_text = lang_text
        self.thread_count = thread_count
        self.device = device
        self.demucs_enabled = demucs_enabled
        self.demucs_model = demucs_model
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
        try:
            self._run_impl()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.log_signal.emit(f"\n[CRITICAL ERROR in Worker Thread]:\n{e}\n{tb}")
            self.finished_signal.emit(False, [], [])

    def _run_impl(self):
        saved_paths = []
        failed_files = []
        total_files = len(self.input_files)
        
        # 1. Convert all input files to WAV sequentially (and apply Demucs if enabled)
        temp_wav_files = []
        
        for idx, input_file in enumerate(self.input_files):
            if self.cancelled:
                break
                
            filename = os.path.basename(input_file)
            self.status_signal.emit(f"Đang chuyển đổi tệp {idx+1}/{total_files}: {filename}...")
            
            temp_wav = os.path.join(BIN_DIR, f"temp_transcribe_{idx}.wav")
            if os.path.exists(temp_wav):
                try: os.remove(temp_wav)
                except: pass
                
            if self.demucs_enabled:
                self.log_signal.emit(f"FFmpeg: Trích xuất âm thanh gốc chất lượng cao từ {filename}...")
                ffmpeg_cmd = [
                    FFMPEG_PATH, "-y", "-i", input_file,
                    "-vn", "-acodec", "pcm_s16le", temp_wav
                ]
            else:
                self.log_signal.emit(f"FFmpeg: Chuyển đổi {filename} sang WAV 16kHz...")
                ffmpeg_cmd = [
                    FFMPEG_PATH, "-y", "-i", input_file,
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", temp_wav
                ]
            
            self.current_process = subprocess.Popen(
                ffmpeg_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                creationflags=CREATION_FLAGS
            )
            
            _, stderr = self.current_process.communicate()
            
            if self.cancelled:
                break
                
            if self.current_process.returncode != 0 or not os.path.exists(temp_wav):
                err_msg = stderr.decode('utf-8', errors='ignore')
                self.log_signal.emit(f"LỖI: FFmpeg chuyển đổi thất bại cho {filename}:\n{err_msg}")
                failed_files.append((input_file, "FFmpeg failed"))
                continue
                
            # If Demucs voice separation is enabled, perform it now
            if self.demucs_enabled:
                self.status_signal.emit(f"Đang tách giọng nói tệp {idx+1}/{total_files}...")
                self.log_signal.emit(f"Demucs: Tách giọng nói (vocal) cho tệp {filename}...")
                
                temp_demucs_dir = os.path.join(BIN_DIR, f"demucs_out_{idx}")
                if os.path.exists(temp_demucs_dir):
                    try: shutil.rmtree(temp_demucs_dir)
                    except: pass
                os.makedirs(temp_demucs_dir, exist_ok=True)
                
                try:
                    demucs_device = "cuda" if self.device == "GPU" else "cpu"
                    demucs_segment = "5" if demucs_device == "cuda" else "None"
                    
                    if getattr(sys, 'frozen', False):
                        worker_cmd = [
                            sys.executable, 
                            "--demucs-worker", 
                            self.demucs_model, 
                            temp_demucs_dir, 
                            temp_wav, 
                            demucs_device, 
                            demucs_segment
                        ]
                    else:
                        worker_cmd = [
                            sys.executable, 
                            os.path.abspath(sys.argv[0]), 
                            "--demucs-worker", 
                            self.demucs_model, 
                            temp_demucs_dir, 
                            temp_wav, 
                            demucs_device, 
                            demucs_segment
                        ]
                    
                    self.current_process = subprocess.Popen(
                        worker_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                        creationflags=CREATION_FLAGS
                    )
                    
                    # Pipe output to log panel in real-time
                    while True:
                        line = self.current_process.stdout.readline()
                        if not line and self.current_process.poll() is not None:
                            break
                        if line:
                            clean_line = line.strip()
                            if clean_line:
                                self.log_signal.emit(f"Demucs: {clean_line}")
                                
                    demucs_success = (self.current_process.returncode == 0)
                except Exception as demucs_err:
                    self.log_signal.emit(f"Cảnh báo: Không thể khởi chạy Demucs subprocess: {demucs_err}")
                    demucs_success = False
                    
                if self.cancelled:
                    if os.path.exists(temp_demucs_dir):
                        try: shutil.rmtree(temp_demucs_dir)
                        except: pass
                    break
                    
                if not demucs_success:
                    self.log_signal.emit("Tiếp tục bằng âm thanh gốc do Demucs gặp sự cố.")
                else:
                    # Search for output files
                    vocal_file = None
                    no_vocal_file = None
                    for root, dirs, files in os.walk(temp_demucs_dir):
                        if "vocals.wav" in files:
                            vocal_file = os.path.join(root, "vocals.wav")
                        if "no_vocals.wav" in files:
                            no_vocal_file = os.path.join(root, "no_vocals.wav")
                            
                    if vocal_file and no_vocal_file and os.path.exists(vocal_file) and os.path.exists(no_vocal_file):
                        self.log_signal.emit("Tách giọng nói thành công!")
                        
                        input_dir = os.path.dirname(input_file)
                        input_base = os.path.splitext(os.path.basename(input_file))[0]
                        
                        # 1. Convert no_vocals.wav to original format and save in input_dir
                        codec = get_audio_codec(input_file)
                        if codec in ["aac", "mp4a"]:
                            out_ext = "m4a"
                            acodec = "aac"
                            acodec_opts = ["-b:a", "192k"]
                        elif codec in ["mp3", "mp3float"]:
                            out_ext = "mp3"
                            acodec = "libmp3lame"
                            acodec_opts = ["-q:a", "2"]
                        elif codec == "flac":
                            out_ext = "flac"
                            acodec = "flac"
                            acodec_opts = []
                        elif codec in ["pcm_s16le", "pcm_s24le", "pcm_f32le", "wav"]:
                            out_ext = "wav"
                            acodec = "pcm_s16le"
                            acodec_opts = []
                        else:
                            out_ext = "mp3"
                            acodec = "libmp3lame"
                            acodec_opts = ["-q:a", "2"]

                        no_vocals_dest = os.path.join(input_dir, f"{input_base}_no_vocals.{out_ext}")
                        self.log_signal.emit(f"Đang xuất tệp nhạc nền định dạng {out_ext.upper()}...")
                        
                        if os.path.exists(no_vocals_dest):
                            try: os.remove(no_vocals_dest)
                            except: pass
                            
                        if out_ext == "wav":
                            try:
                                shutil.move(no_vocal_file, no_vocals_dest)
                                self.log_signal.emit(f"Đã lưu tệp không lời tại: {no_vocals_dest}")
                            except Exception as move_err:
                                self.log_signal.emit(f"Cảnh báo: Không thể di chuyển tệp không lời: {move_err}")
                        else:
                            ffmpeg_novoc_cmd = [
                                FFMPEG_PATH, "-y", "-i", no_vocal_file,
                                "-acodec", acodec
                            ] + acodec_opts + [no_vocals_dest]
                            
                            self.current_process = subprocess.Popen(
                                ffmpeg_novoc_cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                creationflags=CREATION_FLAGS
                            )
                            self.current_process.communicate()
                            
                            if self.current_process.returncode == 0 and os.path.exists(no_vocals_dest):
                                self.log_signal.emit(f"Đã lưu tệp không lời tại: {no_vocals_dest}")
                            else:
                                fallback_dest = os.path.join(input_dir, f"{input_base}_no_vocals.wav")
                                if os.path.exists(fallback_dest):
                                    try: os.remove(fallback_dest)
                                    except: pass
                                try:
                                    shutil.move(no_vocal_file, fallback_dest)
                                    self.log_signal.emit(f"Cảnh báo: Chuyển đổi nhạc nền thất bại, đã lưu tệp WAV gốc tại: {fallback_dest}")
                                except Exception as move_err:
                                    self.log_signal.emit(f"Cảnh báo: Không thể di chuyển tệp không lời: {move_err}")
                            
                        # 2. Move vocals.wav to same directory as input_file
                        vocals_dest = os.path.join(input_dir, f"{input_base}_vocals.wav")
                        vocals_source_for_convert = vocal_file
                        try:
                            if os.path.exists(vocals_dest):
                                try: os.remove(vocals_dest)
                                except: pass
                            shutil.move(vocal_file, vocals_dest)
                            self.log_signal.emit(f"Đã lưu tệp giọng nói tại: {vocals_dest}")
                            vocals_source_for_convert = vocals_dest
                        except Exception as move_err:
                            self.log_signal.emit(f"Cảnh báo: Không thể di chuyển tệp giọng nói sang thư mục gốc: {move_err}")
                            
                        # 3. Re-convert vocals_source_for_convert to 16kHz mono WAV with Enhancement (highpass, lowpass, loudnorm), replacing temp_wav
                        self.log_signal.emit("Đang lọc nhiễu và tăng cường giọng nói (vocal) cho Whisper...")
                        temp_vocal_wav = os.path.join(BIN_DIR, f"temp_vocal_{idx}.wav")
                        if os.path.exists(temp_vocal_wav):
                            try: os.remove(temp_vocal_wav)
                            except: pass
                            
                        ffmpeg_vocal_cmd = [
                            FFMPEG_PATH, "-y", "-i", vocals_source_for_convert,
                            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                            "-af", "highpass=f=80,lowpass=f=8000,agate=threshold=0.02:range=0.1,loudnorm", temp_vocal_wav
                        ]
                        
                        self.current_process = subprocess.Popen(
                            ffmpeg_vocal_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            creationflags=CREATION_FLAGS
                        )
                        self.current_process.communicate()
                        
                        if self.current_process.returncode == 0 and os.path.exists(temp_vocal_wav):
                            try: os.remove(temp_wav)
                            except: pass
                            os.rename(temp_vocal_wav, temp_wav)
                            self.log_signal.emit("Tăng cường chất lượng giọng nói thành công!")
                        else:
                            self.log_signal.emit("Cảnh báo: Tăng cường giọng nói thất bại, dùng tệp âm thanh gốc.")
                    else:
                        self.log_signal.emit("Cảnh báo: Không tìm thấy tệp kết quả của Demucs, dùng tệp âm thanh gốc.")
                        
                # Cleanup temp demucs dir
                if os.path.exists(temp_demucs_dir):
                    try: shutil.rmtree(temp_demucs_dir)
                    except: pass
                    
            temp_wav_files.append((input_file, temp_wav))
            # Conversion/Separation progress contributes to first 30%
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
        
        # Check and download VAD model
        vad_model_path = os.path.join(MODELS_DIR, "ggml-silero-vad.bin")
        use_vad = False
        try:
            if not os.path.exists(vad_model_path):
                self.log_signal.emit("Mô hình VAD (Silero) chưa có. Đang tải tự động từ HuggingFace...")
                import urllib.request
                url = "https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-vad.bin"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(vad_model_path, 'wb') as out_file:
                    out_file.write(response.read())
                self.log_signal.emit("Đã tải xong mô hình VAD!")
            use_vad = True
        except Exception as e:
            self.log_signal.emit(f"Cảnh báo: Tải mô hình VAD thất bại ({e}). Tắt tính năng VAD để tránh lỗi.")

        whisper_cmd = [
            whisper_exe,
            "-m", model_path,
            "-osrt",
            "-l", lang_code,
            "-t", str(self.thread_count),
            "-bs", "5",
            "-bo", "5",
            "-tp", "0.0",
            "-nf",
            "-mc", "0"
        ]
        
        if use_vad:
            whisper_cmd.extend(["--vad", "-vm", vad_model_path])
            
        if self.device == "CPU":
            whisper_cmd.append("-ng")
        else:
            whisper_cmd.append("-fa")
            
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
            creationflags=CREATION_FLAGS
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
                        import re
                        base_name_only = os.path.splitext(filename)[0]
                        input_dir = os.path.dirname(input_file)
                        downloads_dir = os.path.expanduser(r"~\Downloads")
                        
                        # Tìm file lời nhạc tương ứng
                        lyric_txt = None
                        candidates_txt = [
                            os.path.join(input_dir, f"{base_name_only}.txt"),
                            os.path.join(downloads_dir, f"{base_name_only}.txt"),
                        ]
                        for c in candidates_txt:
                            if os.path.exists(c):
                                lyric_txt = c
                                break
                                
                        lyrics_list = None
                        if lyric_txt:
                            self.log_signal.emit(f"Đối chiếu: Phát hiện file lời nhạc tại: {lyric_txt}")
                            with open(lyric_txt, 'r', encoding='utf-8', errors='ignore') as f:
                                lyrics_list = [l.strip() for l in f.readlines() if l.strip()]
                        else:
                            # Tự động tìm trong cơ sở dữ liệu lời nhạc nhúng sẵn
                            try:
                                from run_local_transcribe import get_stored_lyrics
                                stored_lyr, matched_key = get_stored_lyrics(base_name_only)
                                if stored_lyr:
                                    self.log_signal.emit(f"Đối chiếu: Tự động sử dụng lời chuẩn từ cơ sở dữ liệu cho '{matched_key}'.")
                                    lyrics_list = stored_lyr
                            except Exception as import_err:
                                self.log_signal.emit(f"Cảnh báo: Không thể tải từ cơ sở dữ liệu lời nhạc: {import_err}")
                                
                        if lyrics_list:
                            self.log_signal.emit("Đang đối chiếu căn chỉnh lời nhạc bằng thuật toán DP (Quy hoạch động)...")
                            try:
                                from run_local_transcribe import parse_srt, align_dp
                                raw_segs = parse_srt(found_srt)
                                aligned = align_dp(raw_segs, lyrics_list)
                                
                                blocks = []
                                for aligned_idx, seg in enumerate(aligned):
                                    # Loại bỏ khoảng trắng thừa giữa các chữ tiếng Trung
                                    cleaned_text = re.sub(r'(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])', '', seg['text'])
                                    blocks.append(f"{aligned_idx+1}\n{seg['ts']}\n{cleaned_text}")
                                    
                                with open(found_srt, 'w', encoding='utf-8') as f:
                                    f.write("\n\n".join(blocks) + "\n\n")
                                self.log_signal.emit("Căn chỉnh đối chiếu lời chuẩn hoàn tất.")
                            except Exception as dp_err:
                                self.log_signal.emit(f"Cảnh báo: Lỗi chạy thuật toán DP căn chỉnh: {dp_err}")
                    except Exception as align_err:
                        self.log_signal.emit(f"Cảnh báo: Lỗi chuẩn bị đối chiếu lời nhạc: {align_err}")
                        
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
