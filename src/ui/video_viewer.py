from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QImage, QPixmap, QCursor
from PySide6.QtCore import Qt, QRect, QPoint, QSize, Signal

class VideoViewer(QWidget):
    video_dropped = Signal(str)
    selection_changed = Signal(bool)  # Phát tín hiệu khi có hoặc mất vùng chọn

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.video_size = QSize(0, 0)
        
        # Biến quản lý vẽ và chỉnh sửa vùng chọn
        self.selection_rects = []    # Danh sách các vùng chọn (QRect)
        self.current_rect = QRect()   # Vùng đang được vẽ mới
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_drawing = False
        
        # Trạng thái chỉnh sửa
        self.active_rect_idx = -1    # Vùng chọn đang được tương tác (hover hoặc click)
        self.selected_rect_idx = -1  # Vùng chọn đang được chọn (click)
        self.edit_mode = None        # Trạng thái chỉnh sửa: "move", "resize_tl", "resize_tr", etc.
        self.drag_start_pos = QPoint()
        self.drag_start_rect = QRect()
        
        # Định nghĩa bán kính điểm neo hỗ trợ co giãn
        self.handle_size = 8
        self.tolerance = 8
        
        # Cho phép kéo thả file
        self.setAcceptDrops(True)
        # Cho phép nhận sự kiện di chuyển chuột ngay cả khi không nhấn nút
        self.setMouseTracking(True)
        
        # Cấu hình phong cách
        self.setMinimumSize(400, 300)

    def set_image(self, qimage: QImage, original_size: QSize):
        """Thiết lập ảnh frame mới và lưu kích thước video gốc."""
        self.image = qimage
        self.video_size = original_size
        self.update()

    def clear_selection(self):
        """Xóa vùng chọn hiện tại."""
        self.selection_rects.clear()
        self.current_rect = QRect()
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.active_rect_idx = -1
        self.selected_rect_idx = -1
        self.edit_mode = None
        self.selection_changed.emit(False)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def get_render_rect(self) -> QRect:
        """Tính toán hình chữ nhật thực tế mà ảnh chiếm trên Widget (giữ nguyên tỷ lệ)."""
        if self.image.isNull():
            return QRect()
        
        widget_w = self.width()
        widget_h = self.height()
        img_w = self.image.width()
        img_h = self.image.height()
        
        aspect_img = img_w / img_h
        aspect_widget = widget_w / widget_h
        
        if aspect_img > aspect_widget:
            # Bị giới hạn chiều ngang
            render_w = widget_w
            render_h = int(widget_w / aspect_img)
        else:
            # Bị giới hạn chiều dọc
            render_h = widget_h
            render_w = int(widget_h * aspect_img)
            
        render_x = (widget_w - render_w) // 2
        render_y = (widget_h - render_h) // 2
        
        return QRect(render_x, render_y, render_w, render_h)

    def get_handles(self, rect: QRect) -> list[tuple[QPoint, str]]:
        """Trả về danh sách 8 điểm neo (handles) và loại chỉnh kích thước tương ứng."""
        l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
        cx = l + rect.width() // 2
        cy = t + rect.height() // 2
        
        return [
            (QPoint(l, t), "tl"), # Top-Left
            (QPoint(cx, t), "t"),  # Top
            (QPoint(r, t), "tr"), # Top-Right
            (QPoint(r, cy), "r"),  # Right
            (QPoint(r, b), "br"), # Bottom-Right
            (QPoint(cx, b), "b"),  # Bottom
            (QPoint(l, b), "bl"), # Bottom-Left
            (QPoint(l, cy), "l"),  # Left
        ]

    def _get_hit_test(self, pos: QPoint) -> tuple[int, str]:
        """Kiểm tra chuột chạm vào điểm neo hoặc bên trong vùng chọn nào.
        
        Trả về: (chỉ_số_vùng_chọn, hành_vi)
        Hành vi có thể là: "move", "tl", "tr", "bl", "br", "t", "b", "l", "r", hoặc ""
        """
        render_rect = self.get_render_rect()
        if not render_rect.contains(pos):
            return -1, ""
            
        # Ưu tiên kiểm tra điểm neo của tất cả các vùng chọn trước
        for idx, rect in enumerate(self.selection_rects):
            handles = self.get_handles(rect)
            for h_pos, handle_type in handles:
                if (pos - h_pos).manhattanLength() <= self.tolerance:
                    return idx, handle_type
                    
        # Nếu không chạm điểm neo, kiểm tra chuột nằm bên trong vùng chọn nào
        # (Lấy theo thứ tự ngược lại để ưu tiên các hình vẽ đè lên trên)
        for idx in range(len(self.selection_rects) - 1, -1, -1):
            rect = self.selection_rects[idx]
            if rect.contains(pos):
                return idx, "move"
                
        return -1, ""

    def get_video_coords(self) -> list[tuple[int, int, int, int]]:
        """Quy đổi các vùng chọn từ tọa độ hiển thị sang tọa độ gốc của video.
        
        Trả về: list[(x, y, w, h)] của video gốc.
        """
        if (not self.selection_rects and self.current_rect.isEmpty()) or self.video_size.isEmpty():
            return []
            
        render_rect = self.get_render_rect()
        if render_rect.isEmpty():
            return []
            
        video_w = self.video_size.width()
        video_h = self.video_size.height()
        
        scale_x = video_w / render_rect.width()
        scale_y = video_h / render_rect.height()
        
        coords_list = []
        all_rects = self.selection_rects.copy()
        if not self.current_rect.isEmpty():
            all_rects.append(self.current_rect)
            
        for rect in all_rects:
            clipped_rect = rect.intersected(render_rect)
            if clipped_rect.isEmpty():
                continue
                
            rx = clipped_rect.x() - render_rect.x()
            ry = clipped_rect.y() - render_rect.y()
            rw = clipped_rect.width()
            rh = clipped_rect.height()
            
            vx = int(rx * scale_x)
            vy = int(ry * scale_y)
            vw = int(rw * scale_x)
            vh = int(rh * scale_y)
            
            # Giới hạn tọa độ hợp lệ cho ffmpeg
            vx = max(1, min(vx, video_w - 2))
            vy = max(1, min(vy, video_h - 2))
            
            max_w = video_w - vx - 1
            max_h = video_h - vy - 1
            
            vw = max(2, min(vw, max_w))
            vh = max(2, min(vh, max_h))
            
            # Chẵn hóa tọa độ để tránh lỗi dải màu yuv
            vx = (vx + 1) & ~1
            vy = (vy + 1) & ~1
            vw = vw & ~1
            vh = vh & ~1
            
            if vx + vw >= video_w:
                vw = video_w - vx - 1
                vw = vw & ~1
            if vy + vh >= video_h:
                vh = video_h - vy - 1
                vh = vh & ~1
            
            if vw > 0 and vh > 0:
                coords_list.append((vx, vy, vw, vh))
            
        return coords_list

    # --- Sự kiện Chuột ---
    def mousePressEvent(self, event):
        if self.image.isNull():
            return
            
        pos = event.position().toPoint()
        render_rect = self.get_render_rect()
        
        # Nhấp chuột phải: Xóa vùng chọn
        if event.button() == Qt.MouseButton.RightButton:
            idx, _ = self._get_hit_test(pos)
            if idx != -1:
                self.selection_rects.pop(idx)
                self.selected_rect_idx = -1
                self.active_rect_idx = -1
                self.selection_changed.emit(len(self.selection_rects) > 0)
                self.update()
            return
            
        # Nhấp chuột trái: Di chuyển / Co giãn / Vẽ mới
        if event.button() == Qt.MouseButton.LeftButton:
            idx, action = self._get_hit_test(pos)
            
            if idx != -1:
                # Kích hoạt chế độ chỉnh sửa vùng chọn hiện tại
                self.selected_rect_idx = idx
                self.edit_mode = action
                self.drag_start_pos = pos
                self.drag_start_rect = QRect(self.selection_rects[idx])
                self.update()
            else:
                # Bắt đầu vẽ hình mới nếu click trong ảnh
                if render_rect.contains(pos):
                    self.is_drawing = True
                    self.start_point = pos
                    self.end_point = pos
                    self.current_rect = QRect()
                    self.selected_rect_idx = -1
                    self.update()

    def mouseMoveEvent(self, event):
        if self.image.isNull():
            return
            
        pos = event.position().toPoint()
        render_rect = self.get_render_rect()
        
        # 1. Nếu đang co giãn hoặc di chuyển vùng chọn
        if self.selected_rect_idx != -1 and self.edit_mode:
            rect = self.selection_rects[self.selected_rect_idx]
            diff = pos - self.drag_start_pos
            orig = self.drag_start_rect
            
            # Khống chế biên an toàn bên trong render_rect
            px = max(render_rect.left(), min(pos.x(), render_rect.right()))
            py = max(render_rect.top(), min(pos.y(), render_rect.bottom()))
            diff_clamped = QPoint(px, py) - self.drag_start_pos
            
            if self.edit_mode == "move":
                # Di chuyển vị trí của vùng chọn
                new_l = orig.left() + diff_clamped.x()
                new_t = orig.top() + diff_clamped.y()
                # Khống chế không cho nhảy ra ngoài render_rect
                new_l = max(render_rect.left(), min(new_l, render_rect.right() - orig.width()))
                new_t = max(render_rect.top(), min(new_t, render_rect.bottom() - orig.height()))
                
                rect.moveTo(new_l, new_t)
                
            elif "resize" or self.edit_mode in ["tl", "tr", "bl", "br", "t", "b", "l", "r"]:
                # Thay đổi kích thước (Resize) dựa vào điểm neo tương ứng
                l, t, r, b = orig.left(), orig.top(), orig.right(), orig.bottom()
                act = self.edit_mode
                
                # Cập nhật tọa độ của 4 cạnh
                if "l" in act: l = max(render_rect.left(), min(l + diff.x(), r - 10))
                if "r" in act: r = min(render_rect.right(), max(r + diff.x(), l + 10))
                if "t" in act: t = max(render_rect.top(), min(t + diff.y(), b - 10))
                if "b" in act: b = min(render_rect.bottom(), max(b + diff.y(), t + 10))
                
                # Cập nhật lại QRect
                self.selection_rects[self.selected_rect_idx] = QRect(QPoint(l, t), QPoint(r, b)).normalized()
                
            self.update()
            return
            
        # 2. Nếu đang vẽ mới vùng chọn
        if self.is_drawing:
            # Khống chế điểm di chuyển nằm trong ảnh hiển thị
            px = max(render_rect.left(), min(pos.x(), render_rect.right()))
            py = max(render_rect.top(), min(pos.y(), render_rect.bottom()))
            
            self.end_point = QPoint(px, py)
            self.current_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
            return
            
        # 3. Chế độ Hover (không click): Cập nhật hình dạng con trỏ chuột
        idx, action = self._get_hit_test(pos)
        self.active_rect_idx = idx
        
        if idx != -1:
            if action == "move":
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
            elif action in ["tl", "br"]:
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            elif action in ["tr", "bl"]:
                self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
            elif action in ["t", "b"]:
                self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
            elif action in ["l", "r"]:
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            if render_rect.contains(pos):
                self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
                
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_drawing:
                self.is_drawing = False
                if self.current_rect.width() > 5 and self.current_rect.height() > 5:
                    self.selection_rects.append(self.current_rect)
                    self.selected_rect_idx = len(self.selection_rects) - 1
                    self.selection_changed.emit(True)
                self.current_rect = QRect()
            
            self.edit_mode = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.update()

    # --- Sự kiện Vẽ giao diện ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Vẽ nền đen xám
        painter.fillRect(self.rect(), QColor("#121212"))
        
        if not self.image.isNull():
            render_rect = self.get_render_rect()
            # Vẽ ảnh video
            painter.drawImage(render_rect, self.image)
            
            # Vẽ các vùng chọn
            for idx, rect in enumerate(self.selection_rects):
                is_selected = (idx == self.selected_rect_idx)
                is_active = (idx == self.active_rect_idx)
                
                # Thiết lập màu viền: Chọn -> Xanh dương, Hover -> Đỏ tươi, Thường -> Đỏ sậm
                if is_selected:
                    pen = QPen(QColor("#00a8ff"), 2, Qt.PenStyle.SolidLine)
                    painter.setBrush(QColor(0, 168, 255, 30))
                elif is_active:
                    pen = QPen(QColor("#ff5555"), 2, Qt.PenStyle.DashLine)
                    painter.setBrush(QColor(255, 85, 85, 20))
                else:
                    pen = QPen(QColor("#ff3333"), 1.5, Qt.PenStyle.DashLine)
                    painter.setBrush(QColor(255, 51, 51, 15))
                    
                painter.setPen(pen)
                painter.drawRect(rect)
                
                # Vẽ 8 điểm neo co giãn (chỉ vẽ trên vùng chọn đang hoạt động hoặc được chọn)
                if is_selected or is_active:
                    handles = self.get_handles(rect)
                    painter.setPen(QPen(QColor("#00a8ff" if is_selected else "#ff5555"), 1))
                    painter.setBrush(QColor("#ffffff"))
                    
                    for h_pos, _ in handles:
                        painter.drawEllipse(h_pos, self.handle_size // 2, self.handle_size // 2)
            
            # Vẽ vùng đang được tạo mới (nét đứt màu trắng)
            if self.is_drawing and not self.current_rect.isEmpty():
                painter.setPen(QPen(QColor("#ffffff"), 1.5, Qt.PenStyle.DashLine))
                painter.setBrush(QColor(255, 255, 255, 20))
                painter.drawRect(self.current_rect)
        else:
            # Vẽ chữ hướng dẫn kéo thả khi chưa có video
            painter.setPen(QColor("#525252"))
            font = self.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 
                             "Kéo & Thả Video vào đây\nhoặc click chọn một tệp video đầu vào ở trên\nđể hiển thị trình phát và vẽ vùng chọn logo.")

    # --- Sự kiện Kéo thả file ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile().lower()
                # Chấp nhận các định dạng video phổ biến
                if file_path.endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm', '.3gp')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.video_dropped.emit(file_path)
            event.acceptProposedAction()
