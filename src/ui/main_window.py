import os
from PySide6 import QtWidgets, QtCore, QtGui
from src.core.config import MODELS_DIR
from src.core.utils import load_stylesheet, HAS_CUDA, CUDA_VERSION, open_directory
from src.ui.components import CardFrame, DropZoneFrame, SuccessPopup
from src.ui.downloader import DownloaderDialog
from src.workers.transcribe_worker import TranscribeWorker

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self._running = False
        self._worker_thread = None
        self._worker = None
        self._input_files_list = []

        self._setup_theme()
        self._build_ui()
        self._load_settings()
        self._refresh_models()

    def _setup_theme(self):
        QtWidgets.QApplication.setStyle("Fusion")
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#000000"))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#0A0A0A"))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#000000"))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor("#0A0A0A"))
        palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#171717"))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#E5E5E5"))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#404040"))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#FFFFFF"))
        QtWidgets.QApplication.setPalette(palette)
        
        style = load_stylesheet()
        if style:
            QtWidgets.QApplication.instance().setStyleSheet(style)

    def _build_ui(self):
        self.setWindowTitle("AutoCaption - Whisper Offline Subtitler")
        self.resize(600, 930)
        self.setMinimumSize(550, 880)

        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Top bar
        top = QtWidgets.QFrame(self)
        top.setObjectName("TopBar")
        top_layout = QtWidgets.QHBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 12)
        
        title = QtWidgets.QLabel("AutoCaption")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f8fafc;")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self._btn_toggle_log = QtWidgets.QPushButton("Show Log")
        self._btn_toggle_log.setObjectName("ToggleLogBtn")
        self._btn_toggle_log.clicked.connect(self._toggle_log_panel)
        top_layout.addWidget(self._btn_toggle_log)
        main_layout.addWidget(top)

        # Content layout
        content = QtWidgets.QHBoxLayout()
        content.setSpacing(16)

        # Left panel (Form)
        left_card = QtWidgets.QFrame(self)
        left_card.setObjectName("LeftCard")
        left_layout = QtWidgets.QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        self._build_form(left_layout)
        content.addWidget(left_card, 1)

        # Right panel (Log)
        self._log_panel = QtWidgets.QFrame(self)
        self._log_panel.setObjectName("LogPanel")
        right_layout = QtWidgets.QVBoxLayout(self._log_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)

        self._build_log(right_layout)
        content.addWidget(self._log_panel, 1)

        main_layout.addLayout(content, 1)

        # Status bar
        status = QtWidgets.QFrame(self)
        status.setObjectName("StatusFrame")
        status_layout = QtWidgets.QHBoxLayout(status)
        status_layout.setContentsMargins(12, 8, 12, 8)
        self._status_label = QtWidgets.QLabel("Sẵn sàng")
        self._status_label.setStyleSheet("color: #cbd5e1;")
        status_layout.addWidget(self._status_label)
        main_layout.addWidget(status)

    def _build_form(self, parent_layout):
        title_style = """
            color: #A3A3A3;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
        """
        
        def add_glow(widget, color="#FFFFFF", radius=15):
            effect = QtWidgets.QGraphicsDropShadowEffect()
            effect.setBlurRadius(radius)
            effect.setColor(QtGui.QColor(color))
            effect.setOffset(0, 0)
            widget.setGraphicsEffect(effect)

        # 1. Input Media Group
        input_group = QtWidgets.QFrame()
        input_group.setProperty("class", "GroupFrame")
        input_layout = QtWidgets.QVBoxLayout(input_group)
        input_layout.setContentsMargins(20, 20, 20, 20)
        input_layout.setSpacing(12)

        input_header_layout = QtWidgets.QHBoxLayout()
        lbl_input_title = QtWidgets.QLabel("1. Đầu vào (Media Files)")
        lbl_input_title.setStyleSheet(title_style)
        input_header_layout.addWidget(lbl_input_title)
        input_header_layout.addStretch()
        
        self._btn_browse_input = QtWidgets.QPushButton("Chọn tệp")
        self._btn_browse_input.setProperty("class", "NormalBtn")
        self._btn_clear_input = QtWidgets.QPushButton("Xóa hết")
        self._btn_clear_input.setProperty("class", "NormalBtn")
        input_header_layout.addWidget(self._btn_browse_input)
        input_header_layout.addWidget(self._btn_clear_input)
        input_layout.addLayout(input_header_layout)

        # Drop Zone Frame
        self._drop_zone = DropZoneFrame()
        self._drop_zone.setObjectName("DropZone")
        self._drop_zone.setMinimumHeight(150)
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        
        drop_layout = QtWidgets.QVBoxLayout(self._drop_zone)
        drop_layout.setContentsMargins(10, 10, 10, 10)
        self._lbl_drop = QtWidgets.QLabel("Kéo & Thả tệp âm thanh/video vào đây\n(hoặc nhấn Chọn tệp ở trên)")
        self._lbl_drop.setAlignment(QtCore.Qt.AlignCenter)
        self._lbl_drop.setStyleSheet("font-size: 13px; font-weight: 500; color: #737373; border: none; background: transparent;")
        drop_layout.addWidget(self._lbl_drop)

        # Scroll Area for files
        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFixedHeight(130)
        self._scroll_area.hide()
        
        scroll_content = QtWidgets.QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._files_layout = QtWidgets.QHBoxLayout(scroll_content)
        self._files_layout.setContentsMargins(4, 4, 4, 4)
        self._files_layout.setSpacing(8)
        self._files_layout.setAlignment(QtCore.Qt.AlignLeft)
        
        self._scroll_area.setWidget(scroll_content)
        drop_layout.addWidget(self._scroll_area)
        input_layout.addWidget(self._drop_zone)
        parent_layout.addWidget(input_group)

        # 2. Settings Group
        settings_group = QtWidgets.QFrame()
        settings_group.setProperty("class", "GroupFrame")
        settings_group.setMinimumHeight(400)
        settings_layout = QtWidgets.QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(20, 20, 20, 20)
        settings_layout.setSpacing(14)

        lbl_settings_title = QtWidgets.QLabel("2. Cấu hình")
        lbl_settings_title.setStyleSheet(title_style)
        settings_layout.addWidget(lbl_settings_title)

        self._chk_same_folder = QtWidgets.QCheckBox("Lưu SRT cùng thư mục với tệp gốc")
        self._chk_same_folder.setStyleSheet("color: #E5E5E5; font-weight: 500; background: transparent; border: none;")
        self._chk_same_folder.setChecked(True)
        self._chk_same_folder.toggled.connect(self._toggle_output_folder)
        settings_layout.addWidget(self._chk_same_folder)
        
        self._chk_demucs = QtWidgets.QCheckBox("Tách giọng nói (vocal) bằng Demucs trước khi dịch")
        self._chk_demucs.setStyleSheet("color: #E5E5E5; font-weight: 500; background: transparent; border: none;")
        self._chk_demucs.setChecked(False)
        self._chk_demucs.toggled.connect(self._on_demucs_toggled)
        settings_layout.addWidget(self._chk_demucs)
        
        # Spacer between checkbox and form
        settings_layout.addSpacing(6)

        # Form Layout for perfect alignment and spacing
        settings_form = QtWidgets.QFormLayout()
        settings_form.setVerticalSpacing(18)  # Spaced out vertical rows (18px)
        settings_form.setHorizontalSpacing(15)
        settings_form.setContentsMargins(0, 5, 0, 5)

        # Output row
        output_row = QtWidgets.QHBoxLayout()
        self._lbl_output = QtWidgets.QLabel("Thư mục lưu:")
        self._lbl_output.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._output_edit = QtWidgets.QLineEdit()
        self._btn_browse_output = QtWidgets.QPushButton("Chọn...")
        self._btn_browse_output.setProperty("class", "NormalBtn")
        output_row.addWidget(self._output_edit, 1)
        output_row.addWidget(self._btn_browse_output, 0)
        settings_form.addRow(self._lbl_output, output_row)

        # Model row with refresh and download options
        model_row = QtWidgets.QHBoxLayout()
        self._lbl_model = QtWidgets.QLabel("Mô hình:")
        self._lbl_model.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_model = QtWidgets.QComboBox()
        self._btn_refresh_models = QtWidgets.QPushButton("Tải lại")
        self._btn_refresh_models.setProperty("class", "NormalBtn")
        self._btn_dl_more = QtWidgets.QPushButton("Tải thêm...")
        self._btn_dl_more.setProperty("class", "NormalBtn")
        self._btn_dl_more.setStyleSheet("color: #7c4dff;")
        
        model_row.addWidget(self._cmb_model, 1)
        model_row.addWidget(self._btn_refresh_models, 0)
        model_row.addWidget(self._btn_dl_more, 0)
        settings_form.addRow(self._lbl_model, model_row)

        # Language row
        self._lbl_lang = QtWidgets.QLabel("Ngôn ngữ:")
        self._lbl_lang.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_lang = QtWidgets.QComboBox()
        self._cmb_lang.addItems(["Tự động phát hiện (Auto)", "Tiếng Việt (vi)", "Tiếng Anh (en)", "Tiếng Trung (zh)", "Tiếng Nhật (ja)", "Tiếng Pháp (fr)"])
        settings_form.addRow(self._lbl_lang, self._cmb_lang)

        # Device selection row
        self._lbl_device = QtWidgets.QLabel("Phần cứng:")
        self._lbl_device.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_device = QtWidgets.QComboBox()
        self._cmb_device.addItems(["CPU", "GPU (CUDA)"])
        settings_form.addRow(self._lbl_device, self._cmb_device)

        # Thread count row
        self._lbl_threads = QtWidgets.QLabel("Số luồng CPU:")
        self._lbl_threads.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        cpu_cores = os.cpu_count() or 4
        self._cmb_threads = QtWidgets.QComboBox()
        self._cmb_threads.addItems([str(i) for i in range(1, cpu_cores + 1)])
        self._cmb_threads.setCurrentText(str(min(4, cpu_cores)))
        settings_form.addRow(self._lbl_threads, self._cmb_threads)

        # Demucs model row
        self._lbl_demucs_model = QtWidgets.QLabel("Mức tách Demucs:")
        self._lbl_demucs_model.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_demucs_model = QtWidgets.QComboBox()
        self._cmb_demucs_model.addItems([
            "htdemucs (Tiêu chuẩn - Khuyên dùng)",
            "htdemucs_ft (Chất lượng cao - Chậm)",
            "mdx_extra_q (Nhanh - Tiết kiệm RAM)"
        ])
        settings_form.addRow(self._lbl_demucs_model, self._cmb_demucs_model)

        settings_layout.addLayout(settings_form)

        parent_layout.addWidget(settings_group)
        parent_layout.addSpacing(16)

        # 3. Actions
        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(24)
        parent_layout.addWidget(self._progress)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(12)
        self._btn_start = QtWidgets.QPushButton("BẮT ĐẦU TẠO PHỤ ĐỀ")
        self._btn_start.setObjectName("StartBtn")
        self._btn_start.setMinimumHeight(48)
        add_glow(self._btn_start, color="#7c4dff", radius=20)
        
        self._btn_cancel = QtWidgets.QPushButton("Hủy bỏ")
        self._btn_cancel.setObjectName("CancelBtn")
        self._btn_cancel.setProperty("class", "NormalBtn")
        self._btn_cancel.setMinimumHeight(48)
        self._btn_cancel.setEnabled(False)
        
        self._btn_open = QtWidgets.QPushButton("Mở thư mục")
        self._btn_open.setObjectName("OpenFolderBtn")
        self._btn_open.setProperty("class", "NormalBtn")
        self._btn_open.setMinimumHeight(48)
        
        btn_layout.addWidget(self._btn_start, 2)
        btn_layout.addWidget(self._btn_cancel, 1)
        btn_layout.addWidget(self._btn_open, 1)
        parent_layout.addLayout(btn_layout)
        parent_layout.addStretch()

        # Connect actions
        self._btn_browse_input.clicked.connect(self._browse_input)
        self._btn_clear_input.clicked.connect(self._clear_input_list)
        self._btn_browse_output.clicked.connect(self._browse_output)
        self._btn_refresh_models.clicked.connect(self._refresh_models)
        self._btn_dl_more.clicked.connect(self._open_downloader_for_models)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_open.clicked.connect(self._open_output_folder)
        
        self._toggle_output_folder()

    def _toggle_output_folder(self):
        is_same = self._chk_same_folder.isChecked()
        self._output_edit.setEnabled(not is_same)
        self._btn_browse_output.setEnabled(not is_same)

    def _on_demucs_toggled(self, checked):
        self._lbl_demucs_model.setEnabled(checked)
        self._cmb_demucs_model.setEnabled(checked)

    def _build_log(self, parent_layout):
        label = QtWidgets.QLabel("Nhật ký & Tiến độ chạy")
        label.setStyleSheet("font-weight: bold; color: #A3A3A3;")
        parent_layout.addWidget(label)
        
        self._log_text = QtWidgets.QTextEdit()
        self._log_text.setObjectName("LogText")
        self._log_text.setReadOnly(True)
        self._log_text.setFont(QtGui.QFont("Consolas", 10))
        self._log_text.setPlainText("Nhật ký và tiến độ chi tiết sẽ hiển thị ở đây...")
        parent_layout.addWidget(self._log_text, 1)

    def _add_input_file(self, path):
        if path in self._input_files_list:
            return
        self._input_files_list.append(path)

    def _update_drop_zone_visuals(self):
        while self._files_layout.count():
            item = self._files_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        count = len(self._input_files_list)
        if count == 0:
            self._lbl_drop.show()
            self._scroll_area.hide()
        else:
            self._lbl_drop.hide()
            self._scroll_area.show()
            
            for path in self._input_files_list:
                card = CardFrame(path)
                card.double_clicked.connect(self._remove_file_by_path)
                self._files_layout.addWidget(card)

    def _remove_file_by_path(self, path):
        if path in self._input_files_list:
            self._input_files_list.remove(path)
            self._update_drop_zone_visuals()
            self._save_settings()

    def _clear_input_list(self):
        self._input_files_list.clear()
        self._update_drop_zone_visuals()
        self._save_settings()

    def _load_settings(self):
        settings = QtCore.QSettings("WhisperSubtitler", "Settings")
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(default_dir):
            default_dir = os.path.expanduser("~")
            
        self._last_input_dir = settings.value("last_input_dir", default_dir)
        self._last_output_dir = settings.value("last_output_dir", default_dir)
        
        self._output_edit.setText(settings.value("output_folder", ""))
        self._chk_same_folder.setChecked(settings.value("save_same_folder", True, type=bool))
        self._chk_demucs.setChecked(settings.value("demucs_enabled", False, type=bool))
        
        lang = settings.value("language", "Tự động phát hiện (Auto)")
        self._cmb_lang.setCurrentText(lang)
        
        # Load saved device setting, fallback/force to CPU if no CUDA is available
        default_idx = 1 if HAS_CUDA else 0
        device_idx = int(settings.value("device_index", default_idx))
        if not HAS_CUDA:
            device_idx = 0
            
        self._cmb_device.setCurrentIndex(device_idx)
        if HAS_CUDA:
            self._cmb_device.setItemText(1, f"GPU (CUDA {CUDA_VERSION}.x)")
        else:
            self._cmb_device.setItemText(1, "GPU (CUDA) - Not Available")
            self._cmb_device.model().item(1).setEnabled(False)
        
        threads = int(settings.value("threads", min(4, os.cpu_count() or 4)))
        self._cmb_threads.setCurrentText(str(threads))

        demucs_model = settings.value("demucs_model", "htdemucs (Tiêu chuẩn - Khuyên dùng)")
        self._cmb_demucs_model.setCurrentText(str(demucs_model))
        self._on_demucs_toggled(self._chk_demucs.isChecked())

        self._input_files_list.clear()
        input_files = settings.value("input_files_list", [])
        if isinstance(input_files, str):
            if input_files and os.path.exists(input_files):
                self._add_input_file(input_files)
        elif isinstance(input_files, list):
            for path in input_files:
                if os.path.exists(path):
                    self._add_input_file(path)
        self._update_drop_zone_visuals()

        self._log_panel.setVisible(False)
        self.setMinimumWidth(550)
        self.resize(600, 930)
        self._toggle_output_folder()

    def _save_settings(self):
        settings = QtCore.QSettings("WhisperSubtitler", "Settings")
        settings.setValue("output_folder", self._output_edit.text())
        settings.setValue("save_same_folder", self._chk_same_folder.isChecked())
        settings.setValue("demucs_enabled", self._chk_demucs.isChecked())
        settings.setValue("demucs_model", self._cmb_demucs_model.currentText())
        settings.setValue("language", self._cmb_lang.currentText())
        settings.setValue("device_index", self._cmb_device.currentIndex())
        settings.setValue("threads", int(self._cmb_threads.currentText()))
        settings.setValue("input_files_list", self._input_files_list)
        
        if self._cmb_model.count() > 0 and not self._cmb_model.currentText().startswith("Chưa có model"):
            settings.setValue("model_filename", self._cmb_model.currentText())
        
        if self._input_files_list and os.path.exists(os.path.dirname(self._input_files_list[0])):
            self._last_input_dir = os.path.dirname(self._input_files_list[0])
            
        output_text = self._output_edit.text()
        if output_text and os.path.exists(output_text):
            self._last_output_dir = output_text
            
        settings.setValue("last_input_dir", self._last_input_dir)
        settings.setValue("last_output_dir", self._last_output_dir)

    def _toggle_log_panel(self):
        show = not self._log_panel.isVisible()
        self._log_panel.setVisible(show)
        self.setMinimumWidth(950 if show else 550)
        self.resize(1100 if show else 600, self.height())
        self._btn_toggle_log.setText("Hide Log" if show else "Show Log")

    def _add_files_and_update(self, paths):
        for path in paths:
            self._add_input_file(path)
        self._update_drop_zone_visuals()
        if paths:
            self._last_input_dir = os.path.dirname(paths[0])
            if not self._output_edit.text():
                self._output_edit.setText(os.path.dirname(paths[0]))
                self._last_output_dir = os.path.dirname(paths[0])
        self._save_settings()

    def _on_files_dropped(self, file_paths):
        self._add_files_and_update(file_paths)

    def _browse_input(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Chọn tệp video/âm thanh", self._last_input_dir, 
            "Media Files (*.mp4 *.mkv *.avi *.mp3 *.wav *.m4a *.flac *.mov *.ogg *.webm)"
        )
        if paths:
            self._add_files_and_update(paths)

    def _browse_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu phụ đề", self._last_output_dir)
        if path:
            self._output_edit.setText(path)
            self._last_output_dir = path
            self._save_settings()

    def _refresh_models(self):
        models = []
        if os.path.exists(MODELS_DIR):
            for file in os.listdir(MODELS_DIR):
                if file.endswith(".bin") and file.startswith("ggml-"):
                    models.append(file)
        
        self._cmb_model.clear()
        if models:
            self._cmb_model.addItems(models)
            settings = QtCore.QSettings("WhisperSubtitler", "Settings")
            saved = settings.value("model_filename", "")
            if saved in models:
                self._cmb_model.setCurrentText(saved)
            else:
                self._cmb_model.setCurrentIndex(0)
        else:
            self._cmb_model.addItem("Chưa có model! Hãy tải.")

    def _open_downloader_for_models(self):
        dl = DownloaderDialog(["Whisper Model"], self)
        if dl.exec() == QtWidgets.QDialog.Accepted:
            self._refresh_models()

    def _on_start(self):
        if not self._input_files_list:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tệp âm thanh hoặc video đầu vào!")
            return

        if not self._chk_same_folder.isChecked() and not self._output_edit.text():
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục lưu phụ đề đầu ra!")
            return

        model_selected = self._cmb_model.currentText()
        if not model_selected or model_selected.startswith("Chưa có model"):
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn hoặc tải mô hình Whisper trước!")
            return

        self._save_settings()
        self._running = True
        self._btn_start.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._progress.setValue(0)
        
        # Clear log panel
        self._log_text.clear()
        self._log_text.setPlainText("Bắt đầu xử lý...")

        device_val = "CPU" if self._cmb_device.currentIndex() == 0 else "GPU"
        
        demucs_combo_text = self._cmb_demucs_model.currentText()
        if "htdemucs_ft" in demucs_combo_text:
            demucs_model_name = "htdemucs_ft"
        elif "mdx_extra_q" in demucs_combo_text:
            demucs_model_name = "mdx_extra_q"
        else:
            demucs_model_name = "htdemucs"

        self._worker = TranscribeWorker(
            self._input_files_list, 
            self._output_edit.text(), 
            self._chk_same_folder.isChecked(), 
            model_selected, 
            self._cmb_lang.currentText(), 
            int(self._cmb_threads.currentText()),
            device_val,
            self._chk_demucs.isChecked(),
            demucs_model_name
        )
        self._worker.log_signal.connect(self._on_log)
        self._worker.status_signal.connect(self._on_status)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_finished)

        self._status_label.setText("Đang khởi tạo tiến trình dịch...")
        self._worker.start()

    def _on_cancel(self):
        self._status_label.setText("Đang dừng...")
        if self._worker:
            self._worker.cancel()
        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_cancel.setEnabled(False)

    def _on_log(self, msg):
        self._log_text.append(msg)
        self._log_text.moveCursor(QtGui.QTextCursor.End)

    def _on_status(self, msg):
        self._status_label.setText(msg)

    def _on_progress(self, percent):
        self._progress.setValue(percent)

    def _on_finished(self, success, saved_paths, failed_files):
        if self._worker:
            self._worker.quit()
            self._worker.wait()

        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_cancel.setEnabled(False)

        self._worker = None
        self._worker_thread = None

        if success:
            self._status_label.setText("Hoàn tất tạo phụ đề!")
            popup = SuccessPopup(saved_paths, failed_files, self)
            popup.exec()
        else:
            self._status_label.setText("Đã hủy hoặc xảy ra lỗi.")
            QtWidgets.QMessageBox.warning(self, "Thông tin", "Tiến trình đã được dừng hoặc xảy ra lỗi.")

    def _open_output_folder(self):
        if self._chk_same_folder.isChecked() and self._input_files_list:
            open_directory(os.path.dirname(self._input_files_list[0]))
        else:
            open_directory(self._output_edit.text())

    def closeEvent(self, event):
        self._save_settings()
        if self._running:
            self._on_cancel()
        event.accept()
