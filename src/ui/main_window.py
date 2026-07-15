import os
from PySide6 import QtWidgets, QtCore, QtGui
from src.core.config import MODELS_DIR, SUPPORTED_EXTS
from src.core.utils import load_stylesheet, HAS_CUDA, CUDA_VERSION, open_directory
from src.ui.components import CardFrame, DropZoneFrame, SuccessPopup
from src.ui.downloader import DownloaderDialog
from src.workers.transcribe_worker import TranscribeWorker
from src.workers.tts_worker import TTSWorker

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self._running = False
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

        # Left panel (Form Card with QTabWidget)
        left_card = QtWidgets.QFrame(self)
        left_card.setObjectName("LeftCard")
        left_layout = QtWidgets.QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        # QTabWidget for Transcribe and TTS forms
        self._tab_widget = QtWidgets.QTabWidget()
        self._tab_widget.setObjectName("MainTabWidget")
        
        # Tab 1: Transcribe Widget
        self._tab_transcribe = QtWidgets.QWidget()
        tab_transcribe_layout = QtWidgets.QVBoxLayout(self._tab_transcribe)
        tab_transcribe_layout.setContentsMargins(0, 4, 0, 0)
        tab_transcribe_layout.setSpacing(12)
        self._build_transcribe_form(tab_transcribe_layout)
        self._tab_widget.addTab(self._tab_transcribe, "Tạo phụ đề")

        # Tab 2: TTS Widget
        self._tab_tts = QtWidgets.QWidget()
        tab_tts_layout = QtWidgets.QVBoxLayout(self._tab_tts)
        tab_tts_layout.setContentsMargins(0, 4, 0, 0)
        tab_tts_layout.setSpacing(12)
        self._build_tts_form(tab_tts_layout)
        self._tab_widget.addTab(self._tab_tts, "SRT -> Giọng nói (TTS)")

        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        left_layout.addWidget(self._tab_widget, 1)

        # Common Actions below Tab widget
        self._progress = QtWidgets.QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(24)
        left_layout.addWidget(self._progress)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self._btn_start = QtWidgets.QPushButton("BẮT ĐẦU TẠO PHỤ ĐỀ")
        self._btn_start.setObjectName("StartBtn")
        self._btn_start.setMinimumHeight(48)
        self._add_glow(self._btn_start, color="#7c4dff", radius=20)
        
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
        left_layout.addLayout(btn_layout)

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

        # Connect actions
        self._btn_start.clicked.connect(self._on_start)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_open.clicked.connect(self._open_output_folder)

    def _add_glow(self, widget, color="#FFFFFF", radius=15):
        effect = QtWidgets.QGraphicsDropShadowEffect()
        effect.setBlurRadius(radius)
        effect.setColor(QtGui.QColor(color))
        effect.setOffset(0, 0)
        widget.setGraphicsEffect(effect)

    def _build_transcribe_form(self, parent_layout):
        title_style = """
            color: #A3A3A3;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
        """

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

        lbl_settings_title = QtWidgets.QLabel("2. Cấu hình tạo phụ đề")
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
        
        settings_layout.addSpacing(6)

        # Form Layout
        settings_form = QtWidgets.QFormLayout()
        settings_form.setVerticalSpacing(18)
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

        # Model row
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

        # Connect tab-specific actions
        self._btn_browse_input.clicked.connect(self._browse_input)
        self._btn_clear_input.clicked.connect(self._clear_input_list)
        self._btn_browse_output.clicked.connect(self._browse_output)
        self._btn_refresh_models.clicked.connect(self._refresh_models)
        self._btn_dl_more.clicked.connect(self._open_downloader_for_models)
        
        self._toggle_output_folder()
        self._on_demucs_toggled(self._chk_demucs.isChecked())

    def _build_tts_form(self, parent_layout):
        title_style = """
            color: #A3A3A3;
            font-weight: bold;
            font-size: 14px;
            border: none;
            background: transparent;
        """

        # 1. Inputs Group
        inputs_group = QtWidgets.QFrame()
        inputs_group.setProperty("class", "GroupFrame")
        inputs_layout = QtWidgets.QVBoxLayout(inputs_group)
        inputs_layout.setContentsMargins(20, 20, 20, 20)
        inputs_layout.setSpacing(12)

        lbl_inputs_title = QtWidgets.QLabel("1. Đầu vào (SRT & Giọng mẫu)")
        lbl_inputs_title.setStyleSheet(title_style)
        inputs_layout.addWidget(lbl_inputs_title)

        # SRT File Selector
        srt_label = QtWidgets.QLabel("Tệp phụ đề SRT gốc:")
        srt_label.setStyleSheet("color: #E5E5E5; font-weight: 500;")
        inputs_layout.addWidget(srt_label)
        
        srt_row = QtWidgets.QHBoxLayout()
        self._tts_srt_edit = QtWidgets.QLineEdit()
        self._tts_srt_edit.setPlaceholderText("Kéo & thả hoặc Chọn tệp .srt...")
        self._btn_browse_srt = QtWidgets.QPushButton("Chọn...")
        self._btn_browse_srt.setProperty("class", "NormalBtn")
        srt_row.addWidget(self._tts_srt_edit, 1)
        srt_row.addWidget(self._btn_browse_srt, 0)
        inputs_layout.addLayout(srt_row)

        # Voice Ref Selector
        ref_label = QtWidgets.QLabel("Tệp âm thanh giọng mẫu để clone (6-10 giây):")
        ref_label.setStyleSheet("color: #E5E5E5; font-weight: 500;")
        inputs_layout.addWidget(ref_label)
        
        ref_row = QtWidgets.QHBoxLayout()
        self._tts_ref_edit = QtWidgets.QLineEdit()
        self._tts_ref_edit.setPlaceholderText("Kéo & thả hoặc Chọn file âm thanh giọng mẫu...")
        self._btn_browse_ref = QtWidgets.QPushButton("Chọn...")
        self._btn_browse_ref.setProperty("class", "NormalBtn")
        ref_row.addWidget(self._tts_ref_edit, 1)
        ref_row.addWidget(self._btn_browse_ref, 0)
        inputs_layout.addLayout(ref_row)

        parent_layout.addWidget(inputs_group)

        # 2. Config Group
        config_group = QtWidgets.QFrame()
        config_group.setProperty("class", "GroupFrame")
        config_layout = QtWidgets.QVBoxLayout(config_group)
        config_layout.setContentsMargins(20, 20, 20, 20)
        config_layout.setSpacing(14)

        lbl_config_title = QtWidgets.QLabel("2. Cấu hình thuyết minh")
        lbl_config_title.setStyleSheet(title_style)
        config_layout.addWidget(lbl_config_title)

        self._chk_tts_auto_speed = QtWidgets.QCheckBox("Tự động tăng tốc độ thuyết minh để khớp với phụ đề")
        self._chk_tts_auto_speed.setStyleSheet("color: #E5E5E5; font-weight: 500; background: transparent; border: none;")
        self._chk_tts_auto_speed.setChecked(True)
        config_layout.addWidget(self._chk_tts_auto_speed)

        config_form = QtWidgets.QFormLayout()
        config_form.setVerticalSpacing(18)
        config_form.setHorizontalSpacing(15)
        config_form.setContentsMargins(0, 5, 0, 5)

        # Hardware choice
        self._lbl_tts_device = QtWidgets.QLabel("Phần cứng chạy:")
        self._lbl_tts_device.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._cmb_tts_device = QtWidgets.QComboBox()
        self._cmb_tts_device.addItems(["CPU (Chạy an toàn nhưng chậm)", "GPU (CUDA - Chạy nhanh)"])
        config_form.addRow(self._lbl_tts_device, self._cmb_tts_device)

        # Output folder row
        output_row = QtWidgets.QHBoxLayout()
        self._lbl_tts_output = QtWidgets.QLabel("Thư mục lưu thuyết minh:")
        self._lbl_tts_output.setStyleSheet("background: transparent; border: none; color: #A3A3A3;")
        self._tts_output_edit = QtWidgets.QLineEdit()
        self._btn_browse_tts_output = QtWidgets.QPushButton("Chọn...")
        self._btn_browse_tts_output.setProperty("class", "NormalBtn")
        output_row.addWidget(self._tts_output_edit, 1)
        output_row.addWidget(self._btn_browse_tts_output, 0)
        config_form.addRow(self._lbl_tts_output, output_row)

        config_layout.addLayout(config_form)
        parent_layout.addWidget(config_group)

        # Connect TTS signals
        self._btn_browse_srt.clicked.connect(self._browse_srt)
        self._btn_browse_ref.clicked.connect(self._browse_ref)
        self._btn_browse_tts_output.clicked.connect(self._browse_tts_output)

    def _on_tab_changed(self, index):
        if index == 0:
            self._btn_start.setText("BẮT ĐẦU TẠO PHỤ ĐỀ")
        else:
            self._btn_start.setText("BẮT ĐẦU THUYẾT MINH")

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

        # TTS settings load
        self._tts_srt_edit.setText(settings.value("tts_srt_path", ""))
        self._tts_ref_edit.setText(settings.value("tts_ref_path", ""))
        self._chk_tts_auto_speed.setChecked(settings.value("tts_auto_speed", True, type=bool))
        self._tts_output_edit.setText(settings.value("tts_output_dir", default_dir))
        
        default_tts_idx = 1 if HAS_CUDA else 0
        tts_device_idx = int(settings.value("tts_device_index", default_tts_idx))
        if not HAS_CUDA:
            tts_device_idx = 0
        self._cmb_tts_device.setCurrentIndex(tts_device_idx)
        if HAS_CUDA:
            self._cmb_tts_device.setItemText(1, f"GPU (CUDA {CUDA_VERSION}.x)")
        else:
            self._cmb_tts_device.setItemText(1, "GPU (CUDA) - Not Available")
            self._cmb_tts_device.model().item(1).setEnabled(False)

        self._log_panel.setVisible(False)
        self.setMinimumWidth(550)
        self.resize(600, 930)
        self._toggle_output_folder()
        self._on_demucs_toggled(self._chk_demucs.isChecked())

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

        # TTS settings save
        settings.setValue("tts_srt_path", self._tts_srt_edit.text())
        settings.setValue("tts_ref_path", self._tts_ref_edit.text())
        settings.setValue("tts_auto_speed", self._chk_tts_auto_speed.isChecked())
        settings.setValue("tts_device_index", self._cmb_tts_device.currentIndex())
        settings.setValue("tts_output_dir", self._tts_output_edit.text())

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
        if self._tab_widget.currentIndex() == 0:
            self._add_files_and_update(file_paths)
        else:
            # Handle drops for Tab 2
            for path in file_paths:
                ext = os.path.splitext(path)[1].lower()
                if ext == ".srt":
                    self._tts_srt_edit.setText(path)
                    if not self._tts_output_edit.text():
                        self._tts_output_edit.setText(os.path.dirname(path))
                elif ext in [".wav", ".mp3", ".m4a", ".flac", ".ogg"]:
                    self._tts_ref_edit.setText(path)

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

    def _browse_srt(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn tệp phụ đề SRT", self._last_input_dir, 
            "Subtitle Files (*.srt)"
        )
        if path:
            self._tts_srt_edit.setText(path)
            if not self._tts_output_edit.text():
                self._tts_output_edit.setText(os.path.dirname(path))
            self._save_settings()

    def _browse_ref(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn tệp âm thanh giọng mẫu", self._last_input_dir, 
            "Audio Files (*.wav *.mp3 *.m4a *.flac *.ogg)"
        )
        if path:
            self._tts_ref_edit.setText(path)
            self._save_settings()

    def _browse_tts_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu thuyết minh", self._last_output_dir)
        if path:
            self._tts_output_edit.setText(path)
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
        self._save_settings()
        
        if self._tab_widget.currentIndex() == 0:
            # 1. Transcribe Mode
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

            self._running = True
            self._btn_start.setEnabled(False)
            self._btn_cancel.setEnabled(True)
            self._progress.setValue(0)
            
            self._log_text.clear()
            self._log_text.setPlainText("Bắt đầu xử lý dịch...")

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

        else:
            # 2. TTS Thuyết Minh Mode
            srt_path = self._tts_srt_edit.text()
            ref_path = self._tts_ref_edit.text()
            output_dir = self._tts_output_edit.text()

            if not srt_path or not os.path.exists(srt_path):
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tệp phụ đề SRT hợp lệ!")
                return

            if not ref_path or not os.path.exists(ref_path):
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn tệp ghi âm giọng mẫu hợp lệ để clone!")
                return

            if not output_dir or not os.path.exists(output_dir):
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục lưu thuyết minh hợp lệ!")
                return

            self._running = True
            self._btn_start.setEnabled(False)
            self._btn_cancel.setEnabled(True)
            self._progress.setValue(0)
            
            self._log_text.clear()
            self._log_text.setPlainText("Bắt đầu xử lý thuyết minh...")

            device_val = "CPU" if self._cmb_tts_device.currentIndex() == 0 else "GPU"

            self._worker = TTSWorker(
                srt_path,
                ref_path,
                output_dir,
                device=device_val,
                auto_speed=self._chk_tts_auto_speed.isChecked()
            )
            self._worker.log_signal.connect(self._on_log)
            self._worker.status_signal.connect(self._on_status)
            self._worker.progress_signal.connect(self._on_progress)
            self._worker.finished_signal.connect(self._on_finished)

            self._status_label.setText("Đang khởi tạo tiến trình thuyết minh...")
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

    def _on_finished(self, success, saved_paths, failed_files=None):
        if self._worker:
            self._worker.quit()
            self._worker.wait()

        self._running = False
        self._btn_start.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._worker = None

        if success:
            self._status_label.setText("Hoàn tất xử lý!")
            if self._tab_widget.currentIndex() == 0:
                popup = SuccessPopup(saved_paths, failed_files or [], self)
                popup.exec()
            else:
                # For TTS mode: saved_paths is the generated file string
                popup = SuccessPopup([saved_paths], [], self)
                popup.exec()
        else:
            self._status_label.setText("Đã hủy hoặc xảy ra lỗi.")
            QtWidgets.QMessageBox.warning(self, "Thông tin", "Tiến trình đã được dừng hoặc xảy ra lỗi.")

    def _open_output_folder(self):
        if self._tab_widget.currentIndex() == 0:
            if self._chk_same_folder.isChecked() and self._input_files_list:
                open_directory(os.path.dirname(self._input_files_list[0]))
            else:
                open_directory(self._output_edit.text())
        else:
            open_directory(self._tts_output_edit.text())

    def closeEvent(self, event):
        self._save_settings()
        if self._running:
            self._on_cancel()
        event.accept()
