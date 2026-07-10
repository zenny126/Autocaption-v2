# Autocaption v2

Phần mềm tự động tạo phụ đề (SRT) ngoại tuyến (offline) cho các tệp video và âm thanh sử dụng Whisper C++ Engine (`whisper.cpp`), tích hợp công cụ tách giọng ca sĩ **Demucs AI** (Meta) và giao diện đồ họa hiện đại **PySide6**.

Dự án này là phiên bản nâng cấp giao diện, tối ưu hóa cơ chế xử lý luồng dịch và bộ lọc chống nhiễu chuyên sâu từ kho mã nguồn AutoCaption gốc.

---

## Tính năng nổi bật

* **Giao diện hiện đại (PySide6)**: Hỗ trợ kéo thả (Drag & Drop) nhiều tệp tin cùng lúc với giao diện thẻ tệp trực quan, bảng điều khiển log xử lý chi tiết (Show/Hide Log).
* **Tách giọng ca sĩ & Nhạc nền (Demucs Integration)**: Tích hợp mô hình AI Demucs để tự động tách giọng nói (Vocal) chất lượng cao trước khi đưa vào dịch, xuất nhạc nền Karaoke (No-Vocal) chất lượng gốc tương ứng.
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

## Cài đặt và Sử dụng

### 1. Cài đặt Python và Thư viện phụ thuộc
Yêu cầu hệ thống đã cài đặt Python 3.9 trở lên.
Mở Terminal/CMD tại thư mục dự án và chạy lệnh sau để cài đặt các thư viện cần thiết:

```bash
pip install -r requirements.txt
```

### 2. Khởi chạy ứng dụng
Chạy ứng dụng bằng lệnh:

```bash
python app.py
```

### 3. Tải tài nguyên ban đầu
Ở lần đầu tiên khởi chạy ứng dụng, nếu hệ thống chưa phát hiện thấy các công cụ bổ trợ, phần mềm sẽ tự động hiển thị hộp thoại tải xuống:
* **FFmpeg**: Hỗ trợ trích xuất và chuyển đổi âm thanh.
* **Whisper Model (GGML .bin)**: Mô hình mặc định (Base hoặc Large V3 Turbo) được tự động tải về từ kho [ggml-org on HuggingFace](https://huggingface.co/ggml-org) và lưu ngoại tuyến tại thư mục `bin/models/`.

Sau khi tải xong, phần mềm sẽ khởi chạy hoàn toàn ngoại tuyến mà không yêu cầu kết nối internet.

---

## Tích hợp DaVinci Resolve (`AutoCaption4DR.lua`)

Script Lua chạy trực tiếp bên trong DaVinci Resolve giúp tự động tạo phụ đề cho Timeline một cách nhanh chóng mà **không cần cài đặt môi trường Python**:

### Cơ chế hoạt động:
* **Không yêu cầu Python**: Gọi trực tiếp công cụ `whisper-cli.exe` và `ffmpeg.exe` có sẵn trong thư mục ứng dụng chính của bạn để trích xuất âm thanh 16kHz WAV và dịch phụ đề C++. (Nếu cấu hình thủ công, bạn có thể tải bản dựng sẵn tại [whisper.cpp releases](https://github.com/ggerganov/whisper.cpp/releases) và [FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/)).
* **Quy trình một chạm (All-in-one)**: Chỉ cần chọn đường dẫn đến `whisper-cli.exe` và mô hình `.bin` mong muốn ở lần đầu tiên chạy. Các lần tiếp theo, script sẽ chạy ngầm bằng cấu hình đã lưu mà không hiển thị lại hộp thoại. (Bạn có thể tải thủ công các mô hình GGML phổ biến tại đây: [ggml-large-v3-turbo.bin](https://huggingface.co/ggml-org/whisper-large-v3-turbo/resolve/main/ggml-large-v3-turbo.bin) | [ggml-base.bin](https://huggingface.co/ggml-org/whisper-base/resolve/main/ggml-base.bin) | [ggml-small.bin](https://huggingface.co/ggml-org/whisper-small/resolve/main/ggml-small.bin)).
* **Tự động nhận diện Clip**: Tự động nhận diện và dịch tệp tin của **Clip đang nằm dưới vạch Playhead** trên track video hiện tại của bạn. Nếu Playhead trống, script sẽ tự động hiện bảng chọn tệp làm dự phòng.
* **Tích hợp VAD tự động**: Nếu phát hiện thấy tệp mô hình VAD `ggml-silero-vad.bin` trong thư mục `models/`, script sẽ tự động kích hoạt bộ lọc `--vad` để nâng cao độ chính xác. (Bạn có thể tải thủ công mô hình tại: [Silero VAD model link](https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-vad.bin)).

### Cài đặt và sử dụng:
1. Sao chép tệp `AutoCaption4DR.lua` vào thư mục Script của DaVinci Resolve trên máy tính:
   * **Windows**: `C:\Users\<Tên-User>\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Comp\`
   * **macOS**: `/Users/<Tên-User>/Library/Application Support/Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Comp/`
2. Mở DaVinci Resolve, chọn **Workspace → Scripts → AutoCaption4DR** để chạy.

---

## Biên dịch đóng gói thành file thực thi độc lập

Để tạo ra bộ chạy độc lập trên Windows mà không cần cài đặt Python trên máy của người dùng cuối:

1. Cài đặt PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Mở Terminal/CMD tại thư mục và chạy lệnh sau:
   ```bash
   python -m PyInstaller --clean --noconfirm WhisperSubtitler.spec
   ```
3. Sau khi quá trình hoàn tất, file chạy độc lập sẽ được xuất ra tại thư mục:  
   `dist/WhisperSubtitler/WhisperSubtitler.exe`

---

## Giấy phép sử dụng

Dự án phát hành theo giấy phép **MIT License**.
