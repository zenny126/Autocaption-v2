# Tài liệu Kiến trúc & Hướng dẫn Kỹ thuật Dự án Autocaption v2

Tài liệu này cung cấp cái nhìn chi tiết về kiến trúc hệ thống, các công nghệ sử dụng, cấu trúc mã nguồn, tác dụng của từng file và luồng xử lý dữ liệu của phần mềm tự động tạo phụ đề **Autocaption v2**.

---

## 1. Tổng quan các Công nghệ & Mô hình Sử dụng

Dự án tích hợp nhiều công nghệ hiện đại để tối ưu hóa hiệu năng dịch thuật offline và mang lại trải nghiệm giao diện người dùng mượt mà:

* **Ngôn ngữ lập trình chính**: Python 3.9+
* **Giao diện đồ họa (GUI)**: **PySide6 (Qt for Python)** - mang lại giao diện Dark-mode hiện đại, hỗ trợ hiệu ứng bóng đổ, bo góc và kéo thả (Drag & Drop).
* **Công cụ xử lý âm thanh & hình ảnh**: **FFmpeg** - xóa logo video (`delogo`), trích xuất âm thanh gốc, chuyển đổi định dạng, lọc nhiễu tần số, lọc cổng tiếng ồn (Noise Gate) và chuẩn hóa âm lượng.
* **Mô hình tách giọng AI**: **Demucs (Meta AI)** - tách giọng hát/nói (Vocal) khỏi nhạc nền (Accompaniment) một cách chính xác trước khi đưa vào Whisper dịch. Sử dụng mô hình `mdx_extra` cao cấp, tối giản cài đặt.
* **Engine dịch phụ đề (Speech-to-Text)**: **Whisper C++ (`whisper.cpp`)** - bản port C++ siêu nhẹ của OpenAI Whisper, tối ưu hóa CPU/GPU tốt hơn bản gốc chạy Python.
* **Bộ lọc khoảng lặng (VAD)**: **Silero VAD v5 (`ggml-silero-vad.bin`)** - phát hiện giọng nói để Whisper bỏ qua nhạc dạo/khoảng lặng, chống ảo giác dịch nhầm hoặc lặp từ vô nghĩa.
* **Công nghệ đóng gói**: **PyInstaller** - cấu hình đóng gói tối ưu để tạo file chạy độc lập trên Windows mà không bị phình bộ nhớ RAM/VRAM do nạp DLL thừa.

---

## 2. Cấu trúc Thư mục Dự án

```
Autocaption-v2/
├── app.py                      # Điểm khởi chạy giao diện GUI & Subprocess Worker
├── AutoCaption4DR.lua          # Script tích hợp một chạm cho DaVinci Resolve
├── requirements.txt            # Danh sách thư viện Python phụ thuộc
├── WhisperSubtitler.spec       # Cấu hình biên dịch đóng gói ứng dụng bằng PyInstaller
├── DOC.md                      # [File này] Tài liệu kiến trúc kỹ thuật chi tiết
├── README.md                   # Hướng dẫn cài đặt và sử dụng cho người dùng cuối
└── src/                        # Thư mục mã nguồn chính của ứng dụng
    ├── __init__.py             # Đánh dấu src là một package Python
    ├── assets/
    │   └── AutoCaption.css     # Định nghĩa kiểu dáng CSS giao diện Dark-mode
    ├── core/
    │   ├── __init__.py
    │   ├── config.py           # Định nghĩa các hằng số, đường dẫn và link tải tài nguyên
    │   └── utils.py            # Các hàm tiện ích (dò tìm GPU, tải CSS, kiểm tra file...)
    ├── ui/
    │   ├── __init__.py
    │   ├── components.py       # Thành phần giao diện dùng chung (thẻ file, vùng kéo thả...)
    │   ├── downloader.py       # Hộp thoại tự động tải FFmpeg, Whisper CLI và Whisper Models
    │   └── main_window.py      # Cửa sổ chính quản lý trạng thái giao diện và tương tác
    └── workers/
        ├── __init__.py
        ├── download_worker.py   # Quản lý luồng chạy ngầm tải tài nguyên hệ thống (không chặn UI)
        └── transcribe_worker.py # Quản lý luồng xử lý âm thanh, tách nhạc (Demucs) và chạy Whisper
```

---

## 3. Tác dụng Chi tiết của Từng File

### A. Thư mục gốc (Root)
* **[app.py](file:///d:/Project/Autocaption-v2/app.py)**: 
  * Là điểm khởi chạy chính của ứng dụng.
  * Đóng vai trò kép: khởi động giao diện PySide6 và xử lý tham số `--demucs-worker` từ tiến trình con. Khi được gọi bằng cờ này, file chạy Demucs độc lập nhằm tối ưu hóa giải phóng 100% RAM sau khi hoàn tất.
* **[AutoCaption4DR.lua](file:///d:/Project/Autocaption-v2/AutoCaption4DR.lua)**:
  * Script viết bằng Lua chạy trực tiếp trong phần mềm làm phim **DaVinci Resolve** (Fusion).
  * Cho phép người dùng Resolve tạo phụ đề nhanh cho clip đang chỉnh sửa bằng cách gọi trực tiếp các file thực thi `whisper-cli.exe` và `ffmpeg.exe` trong thư mục của ứng dụng mà không cần cài đặt Python.
* **[requirements.txt](file:///d:/Project/Autocaption-v2/requirements.txt)**:
  * Liệt kê các thư viện Python cần thiết: `PySide6`, `demucs`, `soundfile`, `pyinstaller`.
* **[WhisperSubtitler.spec](file:///d:/Project/Autocaption-v2/WhisperSubtitler.spec)**:
  * File cấu hình hướng dẫn PyInstaller đóng gói ứng dụng thành file `.exe` duy nhất.

### B. Module core (`src/core/`)
* **[config.py](file:///d:/Project/Autocaption-v2/src/core/config.py)**:
  * Chứa toàn bộ cấu hình tĩnh: Danh sách URL tải các phiên bản Whisper CLI (CPU/GPU), các phiên bản mô hình Whisper (Tiny, Base, Small, Medium, Large V3 Turbo), và các đuôi định dạng video/âm thanh được hỗ trợ.
  * Tự động tạo các thư mục lưu trữ cục bộ: `bin/` và `bin/models/`.
* **[utils.py](file:///d:/Project/Autocaption-v2/src/core/utils.py)**:
  * Chứa các chức năng trợ giúp độc lập hệ thống:
    * `get_cuda_version()` & `check_gpu_available()`: Gọi lệnh `nvidia-smi` để kiểm tra máy tính có card đồ họa NVIDIA hỗ trợ CUDA hay không và xác định phiên bản CUDA thích hợp.
    * `load_stylesheet()`: Đọc tệp tin CSS giao diện để áp dụng hiệu ứng cho cửa sổ.
    * `check_system_assets()`: Kiểm tra xem các file chạy cần thiết như `ffmpeg.exe`, `whisper-cli.exe` và các mô hình dịch đã có sẵn trong thư mục ứng dụng hay chưa.

### C. Module giao diện (`src/ui/`)
* **[components.py](file:///d:/Project/Autocaption-v2/src/ui/components.py)**:
  * Thiết kế các widget giao diện Qt tùy biến: `CardFrame` (Thẻ file), `DropZoneFrame` (Kéo thả).
* **[downloader.py](file:///d:/Project/Autocaption-v2/src/ui/downloader.py)**:
  * Thiết kế hộp thoại tải xuống tài nguyên FFmpeg, VAD, Whisper tự động.
* **[main_window.py](file:///d:/Project/Autocaption-v2/src/ui/main_window.py)**:
  * Trung tâm điều khiển giao diện chính của ứng dụng.
  * Hỗ trợ 3 tùy chọn chạy độc lập: Xóa Logo, Demucs, Whisper.
  * Quản lý trạng thái giao diện, điều phối việc tắt/mở khung Log và gọi tiến trình xử lý.

### D. Module luồng chạy ngầm (`src/workers/`)
* **[download_worker.py](file:///d:/Project/Autocaption-v2/src/workers/download_worker.py)**:
  * Tải các file dung lượng lớn không gây treo giao diện (giới hạn tần suất emit).
* **[transcribe_worker.py](file:///d:/Project/Autocaption-v2/src/workers/transcribe_worker.py)**:
  * Trái tim All-in-One của hệ thống. Tự động kiểm tra và xâu chuỗi các bước (Delogo -> Demucs -> Whisper) dựa trên cấu hình tùy chỉnh của người dùng.

---

## 4. Luồng Xử lý Dữ liệu (All-in-One Pipeline)

Khi người dùng nhấn nút **"BẮT ĐẦU XỬ LÝ"**, hệ thống thực thi chuỗi Pipeline linh hoạt:

```mermaid
flowchart TD
    subgraph Input_Phase [1. Chuẩn bị đầu vào]
        A[Danh sách tệp tin] --> B{Kiểm tra file thực thi & Mô hình}
        B -- Thiếu --> C[Mở Downloader Dialog]
        B -- Đủ --> D[Khởi chạy TranscribeWorker]
    end

    subgraph Delogo_Phase [2. Xóa Logo (Tùy chọn)]
        D --> E{Có bật Xóa Logo?}
        E -- Có --> F[Dùng FFmpeg delogo filter xóa logo theo kích thước]
        F --> G[Tạo video _nologo.mp4]
        G --> H{Tiếp tục xử lý âm thanh?}
        E -- Không --> H
    end

    subgraph Demucs_Phase [3. Tách Âm Thanh (Tùy chọn)]
        H -- Có (Demucs Bật) --> I[Trích xuất âm thanh HQ từ video gốc/nologo]
        I --> J[Chạy subprocess: app.py --demucs-worker (mdx_extra)]
        J --> K[Tách vocals.wav & no_vocals]
        K --> L[Lưu file no_vocals định dạng tự động bằng FFmpeg]
        H -- Không bật Demucs --> M[Chỉ trích xuất âm thanh nguyên bản ra WAV]
    end

    subgraph Filter_Phase [4. Lọc Nhiễu Âm Thanh]
        L --> N[Nhận vocals.wav]
        N --> O[Lọc FFmpeg: highpass 80Hz, lowpass 8000Hz, agate noise gate, loudnorm]
        M --> O
        O --> P[Xuất file temp_transcribe.wav (16kHz, Mono, 16-bit)]
    end

    subgraph Whisper_Phase [5. Dịch Phụ Đề (Tùy chọn)]
        P --> Q{Có bật tạo SRT?}
        Q -- Không --> R[Kết thúc & Xóa file rác]
        Q -- Có --> S{Kiểm tra VAD}
        S -- Chưa có --> T[Tự động tải ggml-silero-v5.1.2.bin]
        S -- Đã có --> U
        T --> U[Gọi whisper-cli.exe dịch tự động]
        U --> V[Tối ưu: -bs 5 -bo 5 -tp 0.0 -nf, --vad]
        V --> W[Xuất SRT và đưa về thư mục đích]
        W --> R
    end
```

### Chi tiết các giai đoạn:

#### 1. Bước chuẩn bị (Input & Setup)
* Nhận danh sách tệp qua giao diện kéo-thả.
* Kiểm tra `ffmpeg.exe`, `whisper-cli.exe` và các tệp mô hình (`ggml-*.bin`).

#### 2. Xóa Logo Video
* Nếu bật tính năng **Xóa Logo**, hệ thống sẽ nhận diện độ phân giải video.
* Tính toán vị trí và kích thước filter `delogo` tự động theo tỉ lệ tương đối hoặc cố định, giúp làm mờ watermark trên màn hình nhanh chóng.

#### 3. Tách giọng hát (Vocal Separation - Demucs AI)
* Nếu chọn **Tách giọng**, tiến trình con `app.py --demucs-worker` được gọi.
* Hệ điều hành sẽ tự động quản lý và giải phóng toàn bộ RAM khi tách xong.
* **Vocal** tiếp tục đi vào bước Whisper, **No-Vocal** được giữ lại định dạng gốc trả về thư mục.

#### 4. Lọc nhiễu & Chuẩn hóa giọng nói (Audio Enhancement)
* Sử dụng `highpass=80,lowpass=8000` (giới hạn dải tần con người).
* `agate` triệt tiêu tiếng vang (reverb) và tiếng tạp âm nhỏ.
* Chuyển hóa toàn bộ tín hiệu thành **16kHz, 16-bit Mono PCM**.

#### 5. Chạy dịch thuật ngoại tuyến (Offline Transcription Engine)
* **Whisper C++** đảm nhiệm dịch chính xác với mô hình VAD (`--vad`) giúp lướt qua đoạn không có tiếng người.
* Tự động kích hoạt GPU (`-fa`) nếu card đồ họa NVIDIA có sẵn.
* Các tham số siêu chặt `-bs 5 -bo 5 -tp 0.0 -nf` chống việc Whisper tự biên bịa từ (ảo giác).

---

## 5. Hướng dẫn Xử lý các Lỗi Thường Gặp (Troubleshooting)

### A. Ứng dụng "treo" (đơ) lúc mới chạy lần đầu
* **Nguyên nhân**: Hệ thống tải mô hình Demucs (`mdx_extra` ~150-300MB) về thư mục `.cache/huggingface` trên Windows ngầm.
* **Cách khắc phục**: Hãy chờ đợi từ 3-5 phút tùy tốc độ mạng. Cảnh báo Symlink của HF đã được tự động loại bỏ. Sau khi tải xong 1 lần, các lần tiếp theo sẽ chạy siêu tốc.

### B. Lỗi ModuleNotFoundError / ImportError
* **Khắc phục**: Khởi tạo và kích hoạt môi trường ảo (venv), cài đặt đầy đủ theo file `requirements.txt`. Đảm bảo sử dụng Python từ `3.9` đến `3.12`.

### C. Ứng dụng không nhận diện được GPU (CUDA)
* **Khắc phục**: Cập nhật Driver NVIDIA lên bản mới nhất. Đảm bảo file `ggml-cuda.dll` tồn tại trong thư mục `bin/`. Nếu chưa có, xóa `whisper-cli.exe` để phần mềm ép tự động tải lại phiên bản GPU.

### D. Báo lỗi tràn RAM (OOM) khi Demucs
* **Khắc phục**: Chuyển "Phần cứng" sang **CPU** thay vì GPU, hoặc chỉnh Demucs shift về 1 để giảm thiểu tính toán.
