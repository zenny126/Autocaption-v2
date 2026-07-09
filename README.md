# Autocaption v2

Phần mềm tự động tạo phụ đề (SRT) ngoại tuyến (offline) cho các tệp video và âm thanh sử dụng Whisper C++ Engine (`whisper.cpp`) và giao diện đồ họa hiện đại PySide6.

Dự án này là phiên bản nâng cấp giao diện, tối ưu hóa cơ chế xử lý luồng dịch và đóng gói nhẹ từ kho mã nguồn AutoCaption gốc.

---

## Tính năng nổi bật

* **Giao diện hiện đại (PySide6)**: Hỗ trợ kéo thả (Drag & Drop) nhiều tệp tin cùng lúc với giao diện thẻ tệp trực quan, bảng điều khiển log xử lý chi tiết (Show/Hide Log).
* **Nạp mô hình đúng một lần duy nhất (Single-Load)**: Khi xử lý hàng loạt nhiều tệp đầu vào, luồng Worker sẽ thực hiện chuyển đổi toàn bộ danh sách tệp sang WAV trước, sau đó gọi tiến trình dịch `whisper-cli.exe` một lần duy nhất. Mô hình Whisper chỉ được nạp vào RAM/VRAM một lần duy nhất cho toàn bộ phiên xử lý, giúp tiết kiệm bộ nhớ và giảm tối đa thời gian chờ đợi.
* **Hỗ trợ phần cứng CPU & GPU (CUDA)**: Tự động chạy lệnh phát hiện card đồ họa hỗ trợ CUDA (`nvidia-smi`) khi khởi động ứng dụng. Lựa chọn cấu hình thiết bị sẽ tự động khóa (disable) và ép buộc chọn CPU nếu hệ thống không có GPU phù hợp.
* **Tải mô hình từ liên kết tùy chọn**: Bổ sung hộp thoại quản lý và tải mô hình tự động trực tiếp từ liên kết HTTP/HTTPS của các tệp GGML `.bin` tùy thích. Tên tệp tải về sẽ tự động được hệ thống chuẩn hóa (loại bỏ tham số, thêm tiền tố `ggml-` và đuôi `.bin`).
* **Đóng gói độc lập cực nhẹ**: Tệp đóng gói biên dịch cuối cùng `.exe` chỉ nặng khoảng **30MB**, hoàn toàn không chứa các thư viện AI cồng kềnh như PyTorch hay CTranslate2.

---

## Cấu trúc thư mục dự án

```
Autocaption-v2/
├── STT/                        # Thư mục chính chứa mã nguồn ứng dụng
│   ├── app.py                  # File khởi chạy ứng dụng chính (PySide6)
│   ├── AutoCaption.css         # CSS tạo kiểu giao diện Dark-mode cao cấp
│   ├── AutoCaption_logic.py    # Module cốt lõi định dạng và dịch phụ đề
│   ├── AutoCaption4DR.lua      # Script tích hợp tự động cho DaVinci Resolve
│   ├── requirements.txt        # Các thư viện Python phụ thuộc (PySide6, requests, tqdm)
│   └── WhisperSubtitler.spec   # Cấu hình biên dịch file thực thi PyInstaller
```

---

## Cài đặt và Sử dụng

### 1. Cài đặt Python và Thư viện phụ thuộc
Yêu cầu hệ thống đã cài đặt Python 3.9 trở lên.
Mở Terminal/CMD tại thư mục dự án và chạy lệnh sau để cài đặt các thư viện cần thiết:

```bash
pip install -r STT/requirements.txt
```

### 2. Khởi chạy ứng dụng
Chạy ứng dụng bằng lệnh:

```bash
python STT/app.py
```

### 3. Tải tài nguyên ban đầu
Ở lần đầu tiên khởi chạy ứng dụng, nếu hệ thống chưa phát hiện thấy các công cụ bổ trợ, phần mềm sẽ tự động hiển thị hộp thoại tải xuống:
* **FFmpeg**: Hỗ trợ trích xuất và chuyển đổi âm thanh.
* **Whisper Model (GGML .bin)**: Mô hình mặc định (ví dụ: `Base` hoặc `Large V3 Turbo`) được tải về và lưu ngoại tuyến tại thư mục `bin/models/`.

Sau khi tải xong, phần mềm sẽ khởi chạy hoàn toàn ngoại tuyến mà không yêu cầu kết nối internet.

---

## DaVinci Resolve Integration (`AutoCaption4DR.lua`)

Script Lua chạy độc lập trực tiếp bên trong phần mềm DaVinci Resolve để tạo phụ đề tự động cho Timeline hiện tại của bạn:
1. Sao chép tệp `STT/AutoCaption4DR.lua` vào thư mục Script của DaVinci Resolve trên máy tính:
   * **Windows**: `C:\Users\<Tên-User>\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Comp\`
   * **macOS**: `/Users/<Tên-User>/Library/Application Support/Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Comp/`
2. Mở DaVinci Resolve, chọn **Workspace → Scripts → AutoCaption4DR** để chạy.

---

## Biên dịch đóng gói thành file thực thi `.exe` độc lập

Để tạo ra file chạy `.exe` độc lập trên Windows mà không cần cài đặt Python trên máy của người dùng cuối:

1. Cài đặt PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Mở Terminal/CMD tại thư mục `STT/` và chạy lệnh sau:
   ```bash
   python -m PyInstaller --clean --noconfirm WhisperSubtitler.spec
   ```
3. Sau khi quá trình hoàn tất, file chạy độc lập sẽ được xuất ra tại thư mục:  
   `STT/dist/WhisperSubtitler/WhisperSubtitler.exe`

---

## Giấy phép sử dụng

Dự án phát hành theo giấy phép **MIT License**.
