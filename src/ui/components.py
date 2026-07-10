import os
from PySide6 import QtWidgets, QtCore, QtGui
from src.core.config import SUPPORTED_EXTS
from src.core.utils import open_directory

class CardFrame(QtWidgets.QFrame):
    double_clicked = QtCore.Signal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setFixedSize(90, 100)
        self.setProperty("class", "CardFrame")
        
        card_layout = QtWidgets.QVBoxLayout(self)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(4)
        card_layout.setAlignment(QtCore.Qt.AlignCenter)
        
        icon_lbl = QtWidgets.QLabel()
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        icon_provider = QtWidgets.QFileIconProvider()
        file_info = QtCore.QFileInfo(path)
        icon = icon_provider.icon(file_info)
        icon_lbl.setPixmap(icon.pixmap(40, 40))
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        
        text_lbl = QtWidgets.QLabel()
        text_lbl.setStyleSheet("font-size: 10px; color: #cbd5e1; border: none; background: transparent;")
        text_lbl.setAlignment(QtCore.Qt.AlignCenter)
        
        filename = os.path.basename(path)
        metrics = QtGui.QFontMetrics(text_lbl.font())
        elided = metrics.elidedText(filename, QtCore.Qt.ElideRight, 78)
        text_lbl.setText(elided)
        
        card_layout.addWidget(icon_lbl)
        card_layout.addWidget(text_lbl)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.path)


class DropZoneFrame(QtWidgets.QFrame):
    files_dropped = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if os.path.splitext(url.toLocalFile())[1].lower() in SUPPORTED_EXTS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        dropped_files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and os.path.splitext(file_path)[1].lower() in SUPPORTED_EXTS:
                dropped_files.append(file_path)
        if dropped_files:
            self.files_dropped.emit(dropped_files)


class SuccessPopup(QtWidgets.QDialog):
    def __init__(self, saved_paths, failed_files, parent=None):
        super().__init__(parent)
        self.saved_paths = saved_paths
        
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.resize(480, 280)
        
        frame = QtWidgets.QFrame(self)
        frame.setObjectName("SuccessPopupFrame")
        
        effect = QtWidgets.QGraphicsDropShadowEffect()
        effect.setBlurRadius(30)
        effect.setColor(QtGui.QColor("#404040"))
        effect.setOffset(0, 0)
        frame.setGraphicsEffect(effect)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        
        if len(saved_paths) > 0 and len(failed_files) == 0:
            title_text = "Thành công"
            body_text = "Tạo phụ đề hoàn tất thành công!"
        elif len(saved_paths) > 0 and len(failed_files) > 0:
            title_text = "Cảnh báo"
            body_text = "Đã tạo một số phụ đề, nhưng có tệp bị lỗi.\nVui lòng kiểm tra lại định dạng âm thanh tệp lỗi."
        else:
            title_text = "Thất bại"
            body_text = "Không thể tạo phụ đề cho tệp nào.\nVui lòng kiểm tra lại định dạng tệp."

        header_layout = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel(title_text)
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF; border: none; background: transparent;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setObjectName("SuccessCloseBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.reject)
        header_layout.addWidget(close_btn)
        layout.addLayout(header_layout)
        
        body_lbl = QtWidgets.QLabel(body_text)
        body_lbl.setStyleSheet("font-size: 14px; color: #D4D4D4; border: none; background: transparent;")
        layout.addWidget(body_lbl)
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setObjectName("SuccessList")
        self.list_widget.setFixedHeight(90)
        
        for p in saved_paths:
            item = QtWidgets.QListWidgetItem(f"✓ {os.path.basename(p)}")
            item.setForeground(QtGui.QColor("#22c55e"))
            item.setToolTip(p)
            self.list_widget.addItem(item)
            
        for p, reason in failed_files:
            item = QtWidgets.QListWidgetItem(f"✗ {os.path.basename(p)} ({reason})")
            item.setForeground(QtGui.QColor("#ef4444"))
            item.setToolTip(f"Thất bại: {p}\nLý do: {reason}")
            self.list_widget.addItem(item)
            
        layout.addWidget(self.list_widget)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(12)
        
        open_folder_btn = QtWidgets.QPushButton("Mở thư mục")
        open_folder_btn.setObjectName("SuccessOpenFolderBtn")
        open_folder_btn.clicked.connect(self.on_open_folder)
        open_folder_btn.setEnabled(len(saved_paths) > 0)
        
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setObjectName("SuccessOkBtn")
        ok_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(open_folder_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(frame)
        
    def on_open_folder(self):
        if self.saved_paths:
            open_directory(os.path.dirname(self.saved_paths[0]))
        self.accept()
