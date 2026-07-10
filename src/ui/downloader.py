from PySide6 import QtWidgets, QtCore
from src.core.config import MODEL_URLS
from src.core.utils import HAS_CUDA, CUDA_VERSION
from src.workers.download_worker import DownloadWorker

class DownloaderDialog(QtWidgets.QDialog):
    def __init__(self, missing_items, parent=None):
        super().__init__(parent)
        self.missing_items = missing_items
        self.setWindowTitle("Tải tài nguyên hệ thống")
        self.resize(520, 520)
        self.setStyleSheet("QDialog { background-color: #121214; }")
        
        self.thread = None
        self.worker = None
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        
        lbl_title = QtWidgets.QLabel("TẢI TÀI NGUYÊN HỆ THỐNG")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #7c4dff;")
        lbl_title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(lbl_title)
        
        lbl_desc = QtWidgets.QLabel("Ứng dụng cần tải một số tệp thực thi nhẹ để chạy offline (chỉ tải một lần duy nhất).")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #9fa8da; font-size: 11px;")
        layout.addWidget(lbl_desc)
        
        frame_items = QtWidgets.QFrame()
        frame_items.setStyleSheet("background-color: #1e1e24; border: 1px solid #2e2e38; border-radius: 12px;")
        items_layout = QtWidgets.QVBoxLayout(frame_items)
        items_layout.setContentsMargins(16, 16, 16, 16)
        
        lbl_items_title = QtWidgets.QLabel("Các tệp cần tải:")
        lbl_items_title.setStyleSheet("font-weight: bold; color: #ffffff; border: none; background: transparent;")
        items_layout.addWidget(lbl_items_title)
        
        for item in self.missing_items:
            display_item = item
            if item == "Whisper.cpp (C++ Engine)" and HAS_CUDA:
                display_item = f"{item} [CUDA {CUDA_VERSION}.x - GPU]"
            elif item == "Whisper.cpp (C++ Engine)":
                display_item = f"{item} [BLAS - CPU]"
            lbl_item = QtWidgets.QLabel(f"• {display_item}")
            lbl_item.setStyleSheet("color: #9fa8da; border: none; background: transparent;")
            items_layout.addWidget(lbl_item)
            
        layout.addWidget(frame_items)
        
        self.model_combo_row = QtWidgets.QHBoxLayout()
        self.lbl_select_model = QtWidgets.QLabel("Chọn kích thước mô hình:")
        self.lbl_select_model.setStyleSheet("color: #ffffff;")
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.addItems(list(MODEL_URLS.keys()))
        self.model_combo.setCurrentIndex(1) # Default Base
        
        self.model_combo_row.addWidget(self.lbl_select_model)
        self.model_combo_row.addWidget(self.model_combo, 1)
        
        if "Whisper Model" in self.missing_items:
            layout.addLayout(self.model_combo_row)
            
            # Custom model check & input
            self.custom_model_layout = QtWidgets.QVBoxLayout()
            self.custom_model_layout.setSpacing(6)
            
            self.chk_custom_model = QtWidgets.QCheckBox("Nhập link tải mô hình tùy chọn (GGML)")
            self.chk_custom_model.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent; border: none;")
            self.custom_model_layout.addWidget(self.chk_custom_model)
            
            self.edit_custom_url = QtWidgets.QLineEdit()
            self.edit_custom_url.setPlaceholderText("Ví dụ: https://huggingface.co/.../ggml-base.bin")
            self.edit_custom_url.setEnabled(False)
            self.custom_model_layout.addWidget(self.edit_custom_url)
            
            self.lbl_custom_info = QtWidgets.QLabel(
                "Yêu cầu: Link trực tiếp tải tệp định dạng GGML (*.bin).\n"
                "Tên mô hình tải về bắt buộc phải có tiền tố 'ggml-' và đuôi '.bin' (ví dụ: ggml-model.bin) để phần mềm nhận dạng được. Nếu tên tệp tải về chưa đúng chuẩn này, hệ thống sẽ tự động thêm tiền tố 'ggml-'."
            )
            self.lbl_custom_info.setWordWrap(True)
            self.lbl_custom_info.setStyleSheet("color: #8a8d9a; font-size: 10px; font-style: italic; border: none; background: transparent;")
            self.custom_model_layout.addWidget(self.lbl_custom_info)
            
            layout.addLayout(self.custom_model_layout)
            self.chk_custom_model.toggled.connect(self.toggle_custom_model_input)
            
        self.lbl_status = QtWidgets.QLabel("Sẵn sàng tải xuống...")
        self.lbl_status.setStyleSheet("color: #ffffff;")
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.lbl_status)
        
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_download = QtWidgets.QPushButton("Bắt đầu Tải")
        self.btn_download.setObjectName("StartBtn")
        self.btn_download.setStyleSheet("min-width: 120px; min-height: 36px; background-color: #7c4dff; color: white; border-radius: 18px; font-weight: bold;")
        
        self.btn_cancel = QtWidgets.QPushButton("Hủy bỏ")
        self.btn_cancel.setObjectName("SuccessCloseBtn")
        self.btn_cancel.setStyleSheet("min-width: 100px; min-height: 36px; background-color: #2c2c35; color: white; border-radius: 18px;")
        
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.btn_download.clicked.connect(self.start_download)
        self.btn_cancel.clicked.connect(self.cancel_download)
        
    def toggle_custom_model_input(self, checked):
        self.model_combo.setEnabled(not checked)
        self.edit_custom_url.setEnabled(checked)

    def start_download(self):
        custom_url = None
        if "Whisper Model" in self.missing_items and self.chk_custom_model.isChecked():
            url_text = self.edit_custom_url.text().strip()
            if not url_text or not (url_text.startswith("http://") or url_text.startswith("https://")):
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng nhập link tải http:// hoặc https:// hợp lệ!")
                return
            custom_url = url_text

        self.btn_download.setEnabled(False)
        self.model_combo.setEnabled(False)
        if hasattr(self, "chk_custom_model"):
            self.chk_custom_model.setEnabled(False)
            self.edit_custom_url.setEnabled(False)
        
        self.thread = QtCore.QThread()
        self.worker = DownloadWorker(self.missing_items, self.model_combo.currentText(), custom_url)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.download_finished)
        
        self.thread.start()
        
    def cancel_download(self):
        if self.worker:
            self.worker.cancel()
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.reject()
        
    def update_progress(self, status_text, percent):
        self.lbl_status.setText(status_text)
        self.progress_bar.setValue(percent)
        
    def download_finished(self, success, error_msg):
        self.thread.quit()
        self.thread.wait()
        
        if success:
            QtWidgets.QMessageBox.information(self, "Hoàn tất", "Tất cả tài nguyên đã được tải thành công!")
            self.accept()
        else:
            if self.worker and self.worker.cancelled:
                self.reject()
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi", f"Tải xuống thất bại:\n{error_msg}")
                self.btn_download.setEnabled(True)
                if hasattr(self, "chk_custom_model"):
                    self.chk_custom_model.setEnabled(True)
                    if self.chk_custom_model.isChecked():
                        self.edit_custom_url.setEnabled(True)
                        self.model_combo.setEnabled(False)
                    else:
                        self.model_combo.setEnabled(True)
                        self.edit_custom_url.setEnabled(False)
                else:
                    self.model_combo.setEnabled(True)
