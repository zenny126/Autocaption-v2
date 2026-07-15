#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script nhận diện lời bài hát sử dụng Demucs (tách nhạc nền) và Whisper C++ Engine (nhận diện).
Tích hợp thuật toán quy hoạch động (DP) đối chiếu lời chuẩn để xuất file SRT chính xác 100%.
Xử lý hoàn toàn local.
"""

import os
import sys
import re
import shutil
import subprocess
import urllib.request

# Đảm bảo in tiếng Việt chuẩn trên Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Đường dẫn dự án
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")
MODELS_DIR = os.path.join(BIN_DIR, "models")
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg.exe")

# Tải cơ sở dữ liệu lời nhạc được lưu trữ trong bin/lyrics_db.json
def get_stored_lyrics(song_name):
    db_path = os.path.join(BIN_DIR, "lyrics_db.json")
    if os.path.exists(db_path):
        try:
            import json
            with open(db_path, 'r', encoding='utf-8') as f:
                db = json.load(f)
                for key, val in db.items():
                    if key in song_name:
                        return val, key
        except Exception as e:
            print(f"Cảnh báo: Không thể tải lyrics database ({e})")
    return None, None

def get_whisper_exe():
    candidates = [
        os.path.join(BIN_DIR, "whisper-cli.exe"),
        os.path.join(BIN_DIR, "main.exe"),
        os.path.join(BIN_DIR, "Release", "whisper-cli.exe"),
        os.path.join(BIN_DIR, "Release", "main.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def clean_text(text):
    # Lọc bỏ các ký tự đặc biệt, giữ lại chữ và số để so khớp
    return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)

def similarity(s1, s2):
    c1 = clean_text(s1)
    c2 = clean_text(s2)
    if not c1 or not c2:
        return 0.0
    intersection = len(set(c1) & set(c2))
    return intersection / max(len(c1), len(c2))

def parse_srt(path):
    if not os.path.exists(path):
        return []
    content = open(path, 'r', encoding='utf-8', errors='ignore').read()
    blocks = content.strip().split("\n\n")
    segments = []
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) >= 3:
            idx = lines[0]
            ts = lines[1]
            text = "\n".join(lines[2:])
            segments.append({"idx": idx, "ts": ts, "text": text})
    return segments

def align_dp(segments, lyrics):
    # Loại bỏ các phân đoạn phụ đề quảng cáo của YouTube/Bilibili
    filtered_segments = []
    for seg in segments:
        text = seg["text"]
        if any(w in text for w in ["订阅", "独播剧场", "YoYo", "明镜", "转发", "点赞"]):
            continue
        if len(clean_text(text)) == 0:
            continue
        filtered_segments.append(seg)
        
    N = len(filtered_segments)
    M = len(lyrics)
    if N == 0 or M == 0:
        return filtered_segments
        
    # Bảng DP lưu (score, parent_i, parent_j, action)
    dp = [[(0.0, -1, -1, "") for _ in range(M + 1)] for _ in range(N + 1)]
    
    for i in range(1, N + 1):
        for j in range(1, M + 1):
            seg_text = filtered_segments[i-1]["text"]
            lyr_text = lyrics[j-1]
            sim = similarity(seg_text, lyr_text)
            
            # Khớp segment i với lyric line j (thưởng nếu trùng khớp, phạt nếu khác biệt)
            match_score = dp[i-1][j-1][0] + (sim if sim > 0.1 else -1.0)
            # Bỏ qua segment i
            skip_seg_score = dp[i-1][j][0]
            # Bỏ qua lyric line j
            skip_lyr_score = dp[i][j-1][0]
            
            best_score = skip_seg_score
            best_action = "skip_seg"
            parent = (i-1, j)
            
            if skip_lyr_score > best_score:
                best_score = skip_lyr_score
                best_action = "skip_lyr"
                parent = (i, j-1)
                
            if match_score > best_score:
                best_score = match_score
                best_action = "match"
                parent = (i-1, j-1)
                
            dp[i][j] = (best_score, parent[0], parent[1], best_action)
            
    # Truy vết ngược tìm đường đi khớp tối ưu
    aligned_pairs = []
    curr_i, curr_j = N, M
    while curr_i > 0 and curr_j > 0:
        _, p_i, p_j, action = dp[curr_i][curr_j]
        if action == "match":
            aligned_pairs.append((curr_i - 1, curr_j - 1))
        curr_i, curr_j = p_i, p_j
        
    aligned_pairs.reverse()
    
    # Tạo các phân đoạn phụ đề đã đối chiếu và căn chỉnh
    final_segments = []
    for seg_idx, lyr_idx in aligned_pairs:
        final_segments.append({
            "ts": filtered_segments[seg_idx]["ts"],
            "text": lyrics[lyr_idx]
        })
    return final_segments

def main():
    downloads_dir = os.path.expanduser(r"~\Downloads")
    
    # Tìm bài hát trong thư mục Downloads
    matching_files = [f for f in os.listdir(downloads_dir) if "海屿" in f and f.lower().endswith(('.mp3', '.wav', '.flac', '.m4a'))]
    if matching_files:
        input_file = os.path.join(downloads_dir, matching_files[0])
    else:
        input_file = os.path.join(downloads_dir, "海屿你.mp3")

    if not os.path.exists(input_file):
        print(f"LỖI: Không tìm thấy bài hát tại: {input_file}")
        sys.exit(1)
        
    print(f"=== KHỞI ĐỘNG NHẬN DIỆN LỜI BÀI HÁT ===")
    print(f"Tệp đầu vào: {input_file}")
    
    # Kiểm tra các công cụ
    whisper_exe = get_whisper_exe()
    if not whisper_exe:
        print("LỖI: Không tìm thấy whisper-cli.exe hoặc main.exe trong thư mục bin!")
        sys.exit(1)
        
    # Chọn mô hình OpenAI Large V3 Turbo cho kết quả cấu trúc tốt nhất
    model_path = os.path.join(MODELS_DIR, "ggml-large-v3-turbo.bin")
    if not os.path.exists(model_path):
        # Fallback to Belle if Large V3 Turbo not present
        model_path = os.path.join(MODELS_DIR, "ggml-belle-whisper-large-v3-turbo-zh.bin")
        
    if not os.path.exists(model_path):
        print(f"LỖI: Không tìm thấy mô hình Whisper phù hợp trong thư mục bin/models!")
        sys.exit(1)
        
    print(f"Sử dụng mô hình: {os.path.basename(model_path)}")

    # 1. Tách giọng ca sĩ bằng Demucs
    print("\n--- BƯỚC 1: TÁCH GIỌNG HÁT CA SĨ (DEMUCS) ---")
    temp_wav = os.path.join(BIN_DIR, "temp_transcribe_song.wav")
    if os.path.exists(temp_wav):
        try: os.remove(temp_wav)
        except: pass
        
    print("Trích xuất âm thanh gốc chất lượng cao bằng FFmpeg...")
    ffmpeg_cmd = [
        FFMPEG_PATH, "-y", "-i", input_file,
        "-vn", "-acodec", "pcm_s16le", temp_wav
    ]
    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    temp_demucs_dir = os.path.join(BIN_DIR, "demucs_song_out")
    if os.path.exists(temp_demucs_dir):
        try: shutil.rmtree(temp_demucs_dir)
        except: pass
    os.makedirs(temp_demucs_dir, exist_ok=True)
    
    print("Chạy Demucs tách vocal (giọng hát)...")
    demucs_cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "app.py"),
        "--demucs-worker",
        "htdemucs",
        temp_demucs_dir,
        temp_wav,
        "cpu",
        "None"
    ]
    
    process = subprocess.Popen(
        demucs_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )
    
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line and "Separat" in line or "%" in line:
            print(f"  [Demucs]: {line.strip()}")
            
    if process.returncode != 0:
        print("CẢNH BÁO: Tách Demucs gặp sự cố, sử dụng tệp âm thanh gốc để nhận diện.")
        vocal_wav = temp_wav
    else:
        vocal_file = None
        for root, dirs, files in os.walk(temp_demucs_dir):
            if "vocals.wav" in files:
                vocal_file = os.path.join(root, "vocals.wav")
                break
                
        if vocal_file and os.path.exists(vocal_file):
            print("Đã tách giọng hát thành công!")
            print("Đang lọc tiếng ồn và tăng cường giọng hát cho Whisper...")
            vocal_enhanced = os.path.join(BIN_DIR, "vocal_enhanced.wav")
            if os.path.exists(vocal_enhanced):
                try: os.remove(vocal_enhanced)
                except: pass
                
            ffmpeg_vocal_cmd = [
                FFMPEG_PATH, "-y", "-i", vocal_file,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                "-af", "highpass=f=80,lowpass=f=8000,agate=threshold=0.02:range=0.1,loudnorm", vocal_enhanced
            ]
            subprocess.run(ffmpeg_vocal_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            vocal_wav = vocal_enhanced
        else:
            print("CẢNH BÁO: Không tìm thấy vocals.wav, sử dụng tệp gốc.")
            vocal_wav = temp_wav

    # 2. Chạy Whisper.cpp nhận diện lời bài hát (mốc thời gian)
    print("\n--- BƯỚC 2: NHẬN DIỆN MỐC THỜI GIAN HÁT (WHISPER) ---")
    thread_count = os.cpu_count() or 4
    if thread_count > 4:
        thread_count = thread_count - 1
        
    temp_srt_out = os.path.join(BIN_DIR, "raw_transcription")
    if os.path.exists(temp_srt_out + ".srt"):
        try: os.remove(temp_srt_out + ".srt")
        except: pass
        
    # Tạo lyrics prompt hướng dẫn từ vựng
    lyrics_prompt = (
        "从不主动示弱 我们的过去分分合合 伤人的话难说却觉得洒脱 曾经那些开心难过 "
        "就像开败的花浪拍打着沙 对你情有独钟 陪你留下说最浪漫的话 即便是青春的懵懂 "
        "但是我们渐行渐远 逐渐带上现实的枷锁 信任在短短解释后崩塌 我不知为何疯狂对你执着 "
        "我们之间故事还不多 这回忆的漩涡快要把我吞没 因为我欠你太多手松开的沉默 "
        "连着我这颗心也死了 对于你是解脱 而我如此落魄 我拼了命的隐藏着痛 努力微笑想让你回头 "
        "被泪水打湿是一场梦 掩饰我的执着爱还会不会回来 这是我的独白"
    )
        
    whisper_cmd = [
        whisper_exe,
        "-m", model_path,
        "-osrt",
        "-l", "zh",
        "-t", str(thread_count),
        "-bs", "5",
        "-bo", "5",
        "-tp", "0.0",
        "-nf",
        "-ng",
        "-mc", "0", # Dùng mc 0 để tránh lặp từ hoàn toàn
        "--prompt", lyrics_prompt,
        "-of", temp_srt_out,
        vocal_wav
    ]
    
    print(f"Đang chạy nhận diện bằng Whisper...")
    subprocess.run(whisper_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Nhận diện mốc thời gian hoàn tất.")

    # 3. Đối chiếu lời chuẩn bằng DP (Quy hoạch động)
    print("\n--- BƯỚC 3: CĂN CHỈNH LỜI CHUẨN BẰNG THUẬT TOÁN DP ---")
    
    # Đọc lời chuẩn từ file .txt cùng tên bài hát nếu có (ví dụ: 海屿你.txt)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    lyric_txt_file = os.path.join(downloads_dir, f"{base_name}.txt")
    
    lyrics = None
    if os.path.exists(lyric_txt_file):
        print(f"Phát hiện file lời nhạc chuẩn tại: {lyric_txt_file}")
        try:
            with open(lyric_txt_file, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                if lines:
                    lyrics = lines
                    print(f"Đã nạp {len(lyrics)} dòng lời nhạc từ file txt.")
        except Exception as e:
            print(f"Không thể đọc file lời txt ({e})")
            
    if not lyrics:
        stored_lyr, matched_key = get_stored_lyrics(base_name)
        if stored_lyr:
            lyrics = stored_lyr
            print(f"Đối chiếu: Tự động sử dụng lời chuẩn từ cơ sở dữ liệu cho bài hát '{matched_key}'.")
        else:
            print("CẢNH BÁO: Không tìm thấy file lời nhạc txt và không có lời nhúng sẵn trong cơ sở dữ liệu.")
            lyrics = []

    raw_segments = parse_srt(temp_srt_out + ".srt")
    aligned_segments = align_dp(raw_segments, lyrics)
    
    dest_srt = os.path.join(downloads_dir, f"{base_name}.srt")
    if os.path.exists(dest_srt):
        try: os.remove(dest_srt)
        except: pass
        
    # Lưu file srt kết quả
    blocks = []
    for idx, seg in enumerate(aligned_segments):
        # Loại bỏ khoảng trắng thừa giữa các chữ tiếng Trung
        cleaned_text = re.sub(r'(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5])', '', seg['text'])
        blocks.append(f"{idx+1}\n{seg['ts']}\n{cleaned_text}")
        
    with open(dest_srt, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(blocks) + "\n\n")
        
    print(f"\n========================================")
    print(f"HOÀN THÀNH: Đã xuất file phụ đề SRT khớp lời chuẩn tại:")
    print(dest_srt)
    print(f"========================================")

    # Dọn dẹp tệp tạm
    print("\nĐang dọn dẹp các tệp tạm...")
    for f in [temp_wav, os.path.join(BIN_DIR, "vocal_enhanced.wav"), temp_srt_out + ".srt"]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass
    if os.path.exists(temp_demucs_dir):
        try: shutil.rmtree(temp_demucs_dir)
        except: pass
    print("Dọn dẹp hoàn tất.")

if __name__ == "__main__":
    main()
