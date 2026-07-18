# Autocaption v2

Phần mềm tự động hóa quy trình xử lý Video All-in-One: **Xóa Logo**, **Tách giọng hát (Demucs AI)**, và **Tạo phụ đề tự động (Whisper C++)**. Được thiết kế để chạy hoàn toàn ngoại tuyến (offline) với giao diện đồ họa hiện đại **PySide6**.

Dự án này là phiên bản nâng cấp toàn diện, hợp nhất mọi công đoạn xử lý video và âm thanh vào một Pipeline duy nhất.

---

## Tính năng nổi bật

* **Giao diện hiện đại All-in-One (PySide6)**: Hỗ trợ kéo thả (Drag & Drop) nhiều tệp tin cùng lúc. Bạn có thể bật/tắt linh hoạt 3 chế độ xử lý độc lập hoặc chạy nối tiếp nhau:
  * **Xóa Logo**: Tự động làm mờ logo/watermark trên video tại các vị trí chỉ định.
  * **Tách giọng ca sĩ & Nhạc nền (Demucs Integration)**: Sử dụng mô hình `mdx_extra` chất lượng cao, siêu nhẹ và không yêu cầu C++ Build Tools.
  * **Tạo Phụ Đề (Whisper C++)**: Dịch siêu tốc bằng C++ Engine.
* **Tiến trình con cô lập (Subprocess Worker Memory Model)**: Để tránh tình trạng PyTorch chiếm giữ RAM vĩnh viễn trên Windows, Demucs được khởi chạy trong một tiến trình con độc lập. Hệ điều hành tự động thu hồi 100% bộ nhớ RAM/VRAM ngay sau khi tách xong.
* **Tối ưu phần cứng & GPU**: 
  * Tự động phát hiện và khóa chế độ chọn thiết bị phù hợp (CPU/GPU) qua lệnh `nvidia-smi`.
  * Hỗ trợ **Flash Attention (`-fa`)** khi dịch bằng GPU để tăng tốc độ dịch thêm **20% - 40%**.
* **Chống lặp từ & Ảo giác dịch nhầm**: 
  * Hỗ trợ bộ lọc phát hiện giọng nói **VAD (`--vad`)** qua mô hình Silero VAD v5.
  * Tối ưu tham số giải mã Whisper (`-bs 5 -bo 5 -tp 0.0 -nf`) chống lặp từ.
* **Đóng gói độc lập cực nhẹ**: Đã tối ưu hóa Ponytail (loại bỏ code dư thừa) và loại bỏ các thư viện AI không cần thiết, giúp ứng dụng chạy cực mượt.

---

## Cấu trúc thư mục dự án

```
Autocaption-v2/
├── app.py                  # File khởi chạy ứng dụng chính (PySide6 & Demucs worker)
├── AutoCaption4DR.lua      # Script tích hợp tự động cho DaVinci Resolve
├── requirements.txt        # Các thư viện Python phụ thuộc
├── WhisperSubtitler.spec   # Cấu hình biên dịch đóng gói PyInstaller
├── DOC.md                  # Tài liệu cấu trúc và kiến trúc phần mềm
└── src/                    # Thư mục mã nguồn chính (đã mô-đun hóa)
    ├── assets/
    │   └── AutoCaption.css # File CSS tạo kiểu giao diện Dark-mode
    ├── core/
    │   ├── config.py       # Cấu hình hệ thống và định nghĩa đường dẫn
    │   └── utils.py        # Các hàm tiện ích (dò GPU, check tài nguyên)
    ├── ui/
    │   ├── components.py   # Các thành phần giao diện Qt dùng chung
    │   ├── downloader.py   # Hộp thoại tải FFmpeg, VAD và Whisper Model
    │   └── main_window.py  # Cửa sổ điều khiển chính của GUI
    └── workers/
        ├── download_worker.py   # Quản lý luồng tải tài nguyên (tối ưu UI)
        └── transcribe_worker.py # Trái tim của hệ thống: Xử lý Delogo, Demucs và Whisper
```

---

## Hướng dẫn Khởi chạy Ứng dụng

Bạn có thể khởi chạy và sử dụng ứng dụng bằng hai cách độc lập dưới đây tùy theo mục đích:

### CÁCH 1: Chạy bằng file thực thi (.exe) độc lập (Khuyên dùng cho người dùng cuối)
Cách này giúp bạn chạy trực tiếp ứng dụng bằng file `.exe` duy nhất mà không cần cài đặt Python hay môi trường lập trình trên máy.

1. **Biên dịch thành tệp thực thi**:
   * **Cài đặt Python**: Máy tính biên dịch cần cài đặt Python (khuyên dùng Python 3.11, xem hướng dẫn tích chọn "Add Python to PATH" ở Cách 2).
   * Mở Terminal/CMD tại thư mục dự án và chạy:
     ```bash
     python -m pip install -r requirements.txt
     pip install pyinstaller
     python -m PyInstaller -y WhisperSubtitler.spec
     ```
2. **Khởi chạy**:
   * Sau khi biên dịch xong, truy cập vào thư mục: `dist/WhisperSubtitler/` và nhấp đúp vào **`WhisperSubtitler.exe`** để mở ứng dụng.

---

### CÁCH 2: Khởi chạy trực tiếp từ mã nguồn Python (Dành cho nhà phát triển)
Cách này phù hợp nếu bạn muốn phát triển, chỉnh sửa tính năng hoặc chạy thử nghiệm trực tiếp trên mã nguồn Python.

1. **Yêu cầu cài đặt Python**:
   * Hỗ trợ các phiên bản **Python từ 3.9 đến 3.12** (khuyên dùng **Python 3.11**).
   * **BẮT BUỘC**: Tích chọn ô **"Add Python.exe to PATH"** trong trình cài đặt.

2. **Khởi tạo môi trường ảo & cài đặt thư viện**:
   * Khởi tạo và kích hoạt môi trường ảo `.venv`:
     * **Windows (CMD)**: `python -m venv .venv` rồi `.venv\Scripts\activate.bat`
     * **Windows (PowerShell)**: `python -m venv .venv` rồi `.venv\Scripts\Activate.ps1`
   * Cài đặt các thư viện:
     ```bash
     pip install -r requirements.txt
     ```

3. **Khởi chạy**:
   * Mở phần mềm bằng lệnh:
     ```bash
     python app.py
     ```

---

### LƯU Ý CHUNG: Tải tài nguyên ban đầu (Chạy offline)
Ở lần đầu khởi chạy, ứng dụng sẽ tự động tải các tài nguyên (nếu thiếu):
* **FFmpeg**: Công cụ chuyển đổi định dạng và xóa logo.
* **Mô hình Whisper (.bin)** và **Mô hình Silero VAD**: Lưu offline tại `bin/models/`.
* **Mô hình Demucs**: Hệ thống sẽ ngầm tải (khoảng 150-300MB) ở lần chạy đầu tiên.

Sau khi tải xong một lần duy nhất, ứng dụng có thể hoạt động hoàn toàn ngoại tuyến không cần internet.

---

## Tích hợp DaVinci Resolve (`AutoCaption4DR.lua`)

Script Lua chạy trực tiếp bên trong DaVinci Resolve giúp tự động tạo phụ đề cho Timeline:
* **Không yêu cầu Python**: Gọi trực tiếp công cụ `whisper-cli.exe` và `ffmpeg.exe` có sẵn.
* **Tự động nhận diện Clip**: Tự động nhận diện và dịch tệp tin của **Clip đang nằm dưới vạch Playhead**.
* **Cài đặt**: Sao chép tệp `AutoCaption4DR.lua` vào thư mục Script của DaVinci Resolve:
  * **Windows**: `C:\Users\<Tên-User>\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Comp\`

---

## Giấy phép sử dụng

Dự án phát hành theo giấy phép **MIT License**.
