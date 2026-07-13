# Autocaption v2

Phần mềm tự động tạo phụ đề (SRT) ngoại tuyến (offline) cho các tệp video và âm thanh sử dụng Whisper C++ Engine (`whisper.cpp`), tích hợp công cụ tách giọng ca sĩ **Demucs AI** (Meta) và giao diện đồ họa hiện đại **PySide6**.

Dự án này là phiên bản nâng cấp giao diện, tối ưu hóa cơ chế xử lý luồng dịch và bộ lọc chống nhiễu chuyên sâu từ kho mã nguồn AutoCaption gốc.

---

## Tính năng nổi bật

* **Giao diện hiện đại (PySide6)**: Hỗ trợ kéo thả (Drag & Drop) nhiều tệp tin cùng lúc với giao diện thẻ tệp trực quan, bảng điều khiển log xử lý chi tiết (Show/Hide Log).
* **Tách giọng ca sĩ & Nhạc nền (Demucs Integration)**: Tích hợp mô hình AI Demucs để tự động tách giọng nói (Vocal) chất lượng cao trước khi dịch, xuất nhạc nền Karaoke (No-Vocal) chất lượng gốc tương ứng.
* **Tiến trình con cô lập (Subprocess Worker Memory Model)**: Để tránh tình trạng PyTorch và các DLL liên quan chiếm giữ RAM vĩnh viễn trên Windows, Demucs được khởi chạy trong một tiến trình con độc lập. Hệ điều hành tự động thu hồi 100% bộ nhớ RAM/VRAM ngay sau khi tách xong, giữ cho ứng dụng giao diện chính luôn nhẹ nhàng ở mức ~38MB.
* **Tối ưu phần cứng & GPU**: 
  * Tự động phát hiện và khóa chế độ chọn thiết bị phù hợp (CPU/GPU) qua lệnh `nvidia-smi`.
  * Hỗ trợ **Flash Attention (`-fa`)** khi dịch bằng GPU để tăng tốc độ dịch thêm **20% - 40%**.
* **Chống lặp từ & Ảo giác dịch nhầm**: 
  * Hỗ trợ bộ lọc phát hiện giọng nói **VAD (`--vad`)** thông qua mô hình Silero VAD tải tự động từ HuggingFace.
  * Tối ưu tham số giải mã Whisper (`-bs 5 -bo 5 -tp 0.0 -nf`) chống lặp từ khi ca sĩ ngân nốt dài.
  * Tích hợp bộ lọc tiếng vang/tiếng ồn (`agate=threshold=0.02`) trước khi dịch.
* **Đóng gói độc lập cực nhẹ**: Đã loại bỏ toàn bộ các thư viện AI dư thừa như `sympy`, `networkx`, `matplotlib` khỏi cấu hình PyInstaller và tối ưu hóa bytecode (`optimize=2`) giúp giảm thiểu kích thước tối đa.

---

## Cấu trúc thư mục dự án

```
Autocaption-v2/
├── app.py                  # File khởi chạy ứng dụng chính (PySide6)
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
        ├── download_worker.py   # Quản lý luồng tải tài nguyên
        └── transcribe_worker.py # Quản lý luồng tách âm thanh Demucs và chạy Whisper
```

---

## Hướng dẫn Khởi chạy Ứng dụng

Bạn có thể khởi chạy và sử dụng ứng dụng bằng hai cách độc lập dưới đây tùy theo mục đích:

### CÁCH 1: Chạy bằng file thực thi (.exe) độc lập (Khuyên dùng cho người dùng cuối)
Cách này giúp bạn chạy trực tiếp ứng dụng bằng file `.exe` duy nhất mà không cần cài đặt Python hay môi trường lập trình trên máy.

1. **Biên dịch thành tệp thực thi**:
   * **Cài đặt Python**: Máy tính biên dịch cần cài đặt Python (khuyên dùng Python 3.11, xem hướng dẫn chi tiết cách tải và tích chọn "Add Python to PATH" ở Cách 2).
   * Cài đặt các thư viện phụ thuộc:
     ```bash
     python -m pip install --upgrade pip
     pip install -r requirements.txt
     ```
   * Cài đặt thư viện PyInstaller:
     ```bash
     pip install pyinstaller
     ```
   * Chạy lệnh đóng gói tại thư mục dự án:
     ```bash
     python -m PyInstaller --clean --noconfirm WhisperSubtitler.spec
     ```
2. **Khởi chạy**:
   * Sau khi biên dịch xong, truy cập vào thư mục: `dist/WhisperSubtitler/` và nhấp đúp vào **`WhisperSubtitler.exe`** để mở ứng dụng.

---

### CÁCH 2: Khởi chạy trực tiếp từ mã nguồn Python (Dành cho nhà phát triển)
Cách này phù hợp nếu bạn muốn phát triển, chỉnh sửa tính năng hoặc chạy thử nghiệm trực tiếp trên mã nguồn Python.

1. **Yêu cầu cài đặt Python**:
   * Hỗ trợ các phiên bản **Python từ 3.9 đến 3.12** (khuyên dùng phiên bản **Python 3.11**).
   * Tải bộ cài đặt chính thức: [Tải Python 3.11.9 (64-bit)](https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe).
   * **BẮT BUỘC**: Phải tích chọn ô **"Add Python.exe to PATH"** trong trình cài đặt trước khi nhấn Install.

2. **Khởi tạo môi trường ảo & cài đặt thư viện**:
   * Mở Terminal/CMD tại thư mục dự án:
     ```cmd
     cd d:\Project\Autocaption-v2
     ```
   * Khởi tạo và kích hoạt môi trường ảo `.venv`:
     * **Windows (CMD)**:
       ```cmd
       python -m venv .venv
       .venv\Scripts\activate.bat
       ```
     * **Windows (PowerShell)**:
       ```powershell
       python -m venv .venv
       .venv\Scripts\Activate.ps1
       ```
     * **macOS / Linux**:
       ```bash
       python -m venv .venv
       source .venv/bin/activate
       ```
   * Cài đặt các thư viện phụ thuộc:
     ```bash
     python -m pip install --upgrade pip
     pip install -r requirements.txt
     ```

3. **Khởi chạy**:
   * Chạy lệnh sau trong môi trường ảo đã kích hoạt `(.venv)` để mở phần mềm:
     ```bash
     python app.py
     ```

---

### LƯU Ý CHUNG: Tải tài nguyên ban đầu (Chạy offline)
Dù chạy theo Cách 1 hay Cách 2, ở lần đầu khởi chạy, ứng dụng sẽ tự động phát hiện và mở hộp thoại tải xuống các tài nguyên cần thiết bao gồm:
* **FFmpeg**: Công cụ chuyển đổi định dạng âm thanh.
* **Mô hình Whisper (.bin)**: Bạn chọn mô hình phù hợp (mặc định là Base), hệ thống sẽ lưu offline tại thư mục `bin/models/`.

Sau khi tải xong một lần duy nhất, ứng dụng có thể hoạt động hoàn toàn ngoại tuyến không cần internet.

---

## Tích hợp DaVinci Resolve (`AutoCaption4DR.lua`)

Script Lua chạy trực tiếp bên trong DaVinci Resolve giúp tự động tạo phụ đề cho Timeline một cách nhanh chóng mà **không cần cài đặt môi trường Python**:

### Cơ chế hoạt động:
* **Không yêu cầu Python**: Gọi trực tiếp công cụ `whisper-cli.exe` và `ffmpeg.exe` có sẵn trong thư mục ứng dụng chính của bạn để trích xuất âm thanh 16kHz WAV và dịch phụ đề C++.
* **Quy trình một chạm (All-in-one)**: Chỉ cần chọn đường dẫn đến `whisper-cli.exe` và mô hình `.bin` mong muốn ở lần đầu tiên chạy. Các lần tiếp theo, script sẽ chạy ngầm bằng cấu hình đã lưu mà không hiển thị lại hộp thoại.
* **Tự động nhận diện Clip**: Tự động nhận diện và dịch tệp tin của **Clip đang nằm dưới vạch Playhead** trên track video hiện tại của bạn. Nếu Playhead trống, script sẽ tự động hiện bảng chọn tệp làm dự phòng.
* **Tích hợp VAD tự động**: Nếu phát hiện thấy tệp mô hình VAD `ggml-silero-vad.bin` trong thư mục `models/`, script sẽ tự động kích hoạt bộ lọc `--vad` để nâng cao độ chính xác.

### Cài đặt và sử dụng:
1. Sao chép tệp `AutoCaption4DR.lua` vào thư mục Script của DaVinci Resolve trên máy tính:
   * **Windows**: `C:\Users\<Tên-User>\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Comp\`
   * **macOS**: `/Users/<Tên-User>/Library/Application Support/Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Comp/`
2. Mở DaVinci Resolve, chọn **Workspace → Scripts → AutoCaption4DR** để chạy.

---

## Giấy phép sử dụng

Dự án phát hành theo giấy phép **MIT License**.
