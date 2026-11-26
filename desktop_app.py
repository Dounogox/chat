#!/usr/bin/env python3
"""Native desktop client for the Brotherhood Socket.IO chat server."""
import base64
import mimetypes
import os
import sys
import tempfile
import threading
from urllib.parse import urlparse

import socketio
from PySide6.QtCore import QObject, Qt, Signal, QTimer
from PySide6.QtGui import QCloseEvent, QDesktopServices, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024
DEFAULT_SERVER_URL = "http://127.0.0.1:5000"


class ClientSignals(QObject):
    connected = Signal()
    disconnected = Signal()
    connection_error = Signal(str)
    message = Signal(object)
    room_joined = Signal(object)
    room_error = Signal(str)


class ChatClient:
    def __init__(self, signals):
        self.signals = signals
        self.socket = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,
            logger=False,
            engineio_logger=False,
        )
        self.socket.on("connect", lambda: self.signals.connected.emit())
        self.socket.on("disconnect", lambda: self.signals.disconnected.emit())
        self.socket.on("message", lambda data: self.signals.message.emit(data))
        self.socket.on("room_joined", lambda data: self.signals.room_joined.emit(data))
        self.socket.on(
            "room_error",
            lambda data: self.signals.room_error.emit(data.get("message", "Lỗi phòng chat.")),
        )

    def connect(self, server_url):
        threading.Thread(
            target=self._connect,
            args=(server_url,),
            name="chat-server-connection",
            daemon=True,
        ).start()

    def _connect(self, server_url):
        try:
            self.socket.connect(server_url, wait_timeout=15)
        except Exception as error:
            self.signals.connection_error.emit(str(error))

    def emit(self, event, data):
        if self.socket.connected:
            self.socket.emit(event, data)

    def disconnect(self):
        if self.socket.connected:
            self.socket.disconnect()


class ChatMessage(QWidget):
    def __init__(self, text, own=False, system=False, image_data=None, video_path=None, video_name=None):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 3, 0, 3)

        bubble = QFrame()
        bubble.setObjectName("messageBubble")
        bubble.setProperty("kind", "system" if system else "own" if own else "other")
        bubble.setMaximumWidth(560)
        content = QVBoxLayout(bubble)
        content.setContentsMargins(12, 9, 12, 9)
        content.setSpacing(6)

        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(label)

        if image_data:
            try:
                encoded = image_data.split(",", 1)[1]
                image_bytes = base64.b64decode(encoded, validate=True)
                image = QPixmap()
                if image.loadFromData(image_bytes):
                    preview = QLabel()
                    preview.setPixmap(
                        image.scaled(
                            520,
                            360,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    content.addWidget(preview)
            except (IndexError, ValueError):
                pass

        if video_path:
            video_label = QLabel(video_name or "Video")
            video_label.setTextFormat(Qt.TextFormat.PlainText)
            content.addWidget(video_label)
            play_button = QPushButton("▶  Mở video")
            play_button.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(video_path))
            )
            content.addWidget(play_button)

        if system:
            row.addStretch(1)
            row.addWidget(bubble)
            row.addStretch(1)
        elif own:
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brotherhood Chat")
        self.resize(980, 720)
        self.setMinimumSize(760, 560)

        self.signals = ClientSignals()
        self.client = ChatClient(self.signals)
        self.name = ""
        self.room = ""
        self.connected = False
        self.connecting = False
        self.media_temp_dir = tempfile.TemporaryDirectory(prefix="brotherhood-chat-")

        self.signals.connected.connect(self._on_connected)
        self.signals.disconnected.connect(self._on_disconnected)
        self.signals.connection_error.connect(self._on_connection_error)
        self.signals.message.connect(self._on_message)
        self.signals.room_joined.connect(self._on_room_joined)
        self.signals.room_error.connect(self._show_room_error)

        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self._build_connection_page()
        self._build_room_page()
        self._build_chat_page()
        self.pages.setCurrentWidget(self.connection_page)

    def _build_connection_page(self):
        self.connection_page = QWidget()
        outer = QVBoxLayout(self.connection_page)
        outer.setContentsMargins(36, 36, 36, 36)
        outer.addStretch(1)

        panel = QFrame()
        panel.setObjectName("setupPanel")
        panel.setMaximumWidth(520)
        form = QVBoxLayout(panel)
        form.setContentsMargins(32, 30, 32, 30)
        form.setSpacing(14)

        title = QLabel("Brotherhood")
        title.setObjectName("appTitle")
        subtitle = QLabel("Kết nối máy chủ chat")
        subtitle.setObjectName("mutedText")
        form.addWidget(title)
        form.addWidget(subtitle)

        form.addWidget(self._field_label("Địa chỉ server"))
        self.server_input = QLineEdit(DEFAULT_SERVER_URL)
        self.server_input.setPlaceholderText("https://chat.example.com")
        form.addWidget(self.server_input)

        form.addWidget(self._field_label("Tên của bạn"))
        self.name_input = QLineEdit()
        self.name_input.setMaxLength(40)
        self.name_input.setPlaceholderText("Tên hiển thị")
        self.name_input.returnPressed.connect(self._connect_to_server)
        form.addWidget(self.name_input)

        self.connection_error_label = self._error_label()
        form.addWidget(self.connection_error_label)
        self.connection_button = QPushButton("Kết nối")
        self.connection_button.setObjectName("primaryButton")
        self.connection_button.clicked.connect(self._connect_to_server)
        form.addWidget(self.connection_button)

        outer.addWidget(panel, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)
        self.pages.addWidget(self.connection_page)

    def _build_room_page(self):
        self.room_page = QWidget()
        outer = QVBoxLayout(self.room_page)
        outer.setContentsMargins(36, 36, 36, 36)
        outer.addStretch(1)

        panel = QFrame()
        panel.setObjectName("setupPanel")
        panel.setMaximumWidth(560)
        form = QVBoxLayout(panel)
        form.setContentsMargins(32, 30, 32, 30)
        form.setSpacing(14)

        self.room_heading = QLabel("Chọn phòng chat")
        self.room_heading.setObjectName("appTitle")
        self.room_identity = QLabel()
        self.room_identity.setObjectName("mutedText")
        form.addWidget(self.room_heading)
        form.addWidget(self.room_identity)
        form.addWidget(self._field_label("Tên phòng"))

        self.room_input = QLineEdit()
        self.room_input.setMaxLength(60)
        self.room_input.setPlaceholderText("Nhập tên phòng")
        form.addWidget(self.room_input)
        form.addWidget(self._field_label("Mật khẩu phòng"))

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Mật khẩu")
        self.password_input.returnPressed.connect(self._join_room)
        form.addWidget(self.password_input)

        self.room_error_label = self._error_label()
        form.addWidget(self.room_error_label)

        actions = QHBoxLayout()
        create_button = QPushButton("Tạo phòng")
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(self._create_room)
        join_button = QPushButton("Tham gia")
        join_button.clicked.connect(self._join_room)
        actions.addWidget(create_button)
        actions.addWidget(join_button)
        form.addLayout(actions)

        change_button = QPushButton("Đổi server / tài khoản")
        change_button.setObjectName("textButton")
        change_button.clicked.connect(self._return_to_connection)
        form.addWidget(change_button)

        outer.addWidget(panel, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)
        self.pages.addWidget(self.room_page)

    def _build_chat_page(self):
        self.chat_page = QWidget()
        layout = QVBoxLayout(self.chat_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("chatHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)

        title_box = QVBoxLayout()
        self.chat_room_label = QLabel()
        self.chat_room_label.setObjectName("roomTitle")
        self.chat_server_label = QLabel()
        self.chat_server_label.setObjectName("mutedText")
        title_box.addWidget(self.chat_room_label)
        title_box.addWidget(self.chat_server_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)

        self.connection_status = QLabel("Đang kết nối")
        self.connection_status.setObjectName("statusLabel")
        header_layout.addWidget(self.connection_status)
        leave_button = QPushButton("Rời phòng")
        leave_button.clicked.connect(self._leave_room)
        header_layout.addWidget(leave_button)
        layout.addWidget(header)

        self.messages_area = QScrollArea()
        self.messages_area.setWidgetResizable(True)
        self.messages_area.setObjectName("messagesArea")
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(18, 16, 18, 16)
        self.messages_layout.setSpacing(2)
        self.messages_layout.addStretch(1)
        self.messages_area.setWidget(self.messages_widget)
        layout.addWidget(self.messages_area, 1)

        composer = QFrame()
        composer.setObjectName("composer")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(16, 12, 16, 12)
        composer_layout.setSpacing(8)

        image_button = QPushButton("📎")
        image_button.setFixedSize(44, 42)
        image_button.setToolTip("Đính kèm ảnh hoặc video")
        image_button.setAccessibleName("Đính kèm ảnh hoặc video")
        image_button.clicked.connect(self._send_media)
        composer_layout.addWidget(image_button)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Nhập tin nhắn...")
        self.message_input.returnPressed.connect(self._send_message)
        composer_layout.addWidget(self.message_input, 1)
        send_button = QPushButton("Gửi")
        send_button.setObjectName("primaryButton")
        send_button.clicked.connect(self._send_message)
        composer_layout.addWidget(send_button)
        layout.addWidget(composer)
        self.pages.addWidget(self.chat_page)

    @staticmethod
    def _field_label(text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def _error_label():
        label = QLabel()
        label.setObjectName("errorLabel")
        label.setWordWrap(True)
        label.hide()
        return label

    @staticmethod
    def _normalized_server_url(value):
        value = value.strip()
        if not value:
            raise ValueError("Vui lòng nhập địa chỉ server.")
        if "://" not in value:
            value = f"http://{value}"
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Địa chỉ server phải bắt đầu bằng http:// hoặc https://.")
        return value.rstrip("/")

    def _connect_to_server(self):
        if self.connecting or self.connected:
            return
        name = self.name_input.text().strip()
        if not name:
            self._show_connection_error("Vui lòng nhập tên của bạn.")
            return
        try:
            server_url = self._normalized_server_url(self.server_input.text())
        except ValueError as error:
            self._show_connection_error(str(error))
            return

        self.name = name
        self.connecting = True
        self.connection_button.setEnabled(False)
        self.connection_button.setText("Đang kết nối...")
        self._show_connection_error("")
        self.client.connect(server_url)

    def _on_connected(self):
        self.connected = True
        self.connecting = False
        self.connection_button.setEnabled(True)
        self.connection_button.setText("Kết nối")
        self.room_identity.setText(f"{self.name}  ·  {self.server_input.text().strip()}")
        self.room_error_label.hide()
        self.pages.setCurrentWidget(self.room_page)

    def _on_disconnected(self):
        self.connected = False
        self.connecting = False
        self.connection_status.setText("Mất kết nối")

    def _on_connection_error(self, message):
        self.connecting = False
        self.connection_button.setEnabled(True)
        self.connection_button.setText("Kết nối")
        self._show_connection_error(
            f"Không kết nối được server. Kiểm tra địa chỉ và trạng thái server. {message}"
        )

    def _show_connection_error(self, message):
        self.connection_error_label.setText(message)
        self.connection_error_label.setVisible(bool(message))

    def _show_room_error(self, message):
        self.room_error_label.setText(message)
        self.room_error_label.show()

    def _submit_room(self, event):
        if not self.connected:
            self._show_room_error("Kết nối server đã bị ngắt. Hãy kết nối lại.")
            return
        room_name = self.room_input.text().strip()
        password = self.password_input.text()
        if not room_name or not password:
            self._show_room_error("Vui lòng nhập tên phòng và mật khẩu.")
            return

        self.room_error_label.hide()
        self.client.emit(
            event,
            {"name": self.name, "room": room_name, "password": password},
        )

    def _create_room(self):
        self._submit_room("create_room")

    def _join_room(self):
        self._submit_room("join_room")

    def _on_room_joined(self, data):
        self.room = data.get("room", "")
        self.password_input.clear()
        self.chat_room_label.setText(self.room)
        self.chat_server_label.setText(self.server_input.text().strip())
        self.connection_status.setText("Đã kết nối")
        self._clear_messages()
        self.pages.setCurrentWidget(self.chat_page)
        self.message_input.setFocus()

    def _clear_messages(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _on_message(self, data):
        text = str(data.get("data", data))
        system = any(
            phrase in text
            for phrase in ("Xin chào", "đã tham gia phòng", "đã thoát phòng", "Đã kết nối")
        )
        own = text.startswith(f"{self.name}:") or text.startswith(f"{self.name} đã gửi")
        media_type = data.get("type")
        image_data = data.get("imageData") if media_type == "image" else None
        video_path = None
        video_name = None
        if media_type == "video":
            try:
                video_data = data["videoData"]
                encoded = video_data.split(",", 1)[1]
                video_bytes = base64.b64decode(encoded, validate=True)
                mime_type = data.get("fileType") or video_data.split(";", 1)[0][5:]
                extension = mimetypes.guess_extension(mime_type, strict=False) or ".mp4"
                with tempfile.NamedTemporaryFile(
                    dir=self.media_temp_dir.name,
                    suffix=extension,
                    delete=False,
                ) as video_file:
                    video_file.write(video_bytes)
                    video_path = video_file.name
                video_name = data.get("fileName", "Video")
            except (IndexError, KeyError, OSError, ValueError):
                video_path = None
        message = ChatMessage(
            text,
            own=own,
            system=system,
            image_data=image_data,
            video_path=video_path,
            video_name=video_name,
        )
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, message)
        QTimer.singleShot(
            0,
            lambda: self.messages_area.verticalScrollBar().setValue(
                self.messages_area.verticalScrollBar().maximum()
            ),
        )

    def _send_message(self):
        text = self.message_input.text().strip()
        if text and self.connected:
            self.client.emit("message", {"message": text})
            self.message_input.clear()

    def _send_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh hoặc video",
            "",
            "Media files (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.mp4 *.mov *.avi *.mkv *.webm *.m4v *.wmv *.flv *.3gp)",
        )
        if not path:
            return
        try:
            mime_type = mimetypes.guess_type(path)[0]
            if not mime_type or not mime_type.startswith(("image/", "video/")):
                self._on_message({"data": "Định dạng tệp không được hỗ trợ."})
                return
            media_type = "video" if mime_type.startswith("video/") else "image"
            max_size = MAX_VIDEO_SIZE if media_type == "video" else MAX_IMAGE_SIZE
            with open(path, "rb") as image_file:
                image_bytes = image_file.read(max_size + 1)
            if len(image_bytes) > max_size:
                size_limit = "100 MB" if media_type == "video" else "5 MB"
                self._on_message({"data": f"Tệp quá lớn, giới hạn là {size_limit}."})
                return
            image_data = base64.b64encode(image_bytes).decode("ascii")
            self.client.emit(
                media_type,
                {
                    "imageData" if media_type == "image" else "videoData":
                        f"data:{mime_type};base64,{image_data}",
                    "fileName": os.path.basename(path),
                    "fileType": mime_type,
                },
            )
        except OSError as error:
            self._on_message({"data": f"Không đọc được tệp: {error}"})

    def _leave_room(self):
        self.client.emit("message", {"message": "{quit}"})
        self.room = ""
        self.pages.setCurrentWidget(self.room_page)

    def _return_to_connection(self):
        self.client.disconnect()
        self.connected = False
        self.connecting = False
        self.pages.setCurrentWidget(self.connection_page)

    def closeEvent(self, event: QCloseEvent):
        self.client.disconnect()
        event.accept()


def apply_theme(app):
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QWidget {
            background: #151a18;
            color: #e7eee9;
            font-family: "Segoe UI", sans-serif;
            font-size: 14px;
        }
        QFrame#setupPanel { background: #202824; border: 1px solid #35433b; }
        QLabel#appTitle { color: #b4f36a; font-size: 28px; font-weight: 700; }
        QLabel#roomTitle { color: #b4f36a; font-size: 18px; font-weight: 700; }
        QLabel#mutedText { color: #9aa79f; font-size: 12px; }
        QLabel#fieldLabel { color: #c4d0c8; font-size: 12px; font-weight: 600; }
        QLabel#errorLabel { color: #ff9b8f; font-size: 12px; }
        QLabel#statusLabel { color: #b4f36a; font-size: 12px; }
        QLineEdit {
            background: #101412; border: 1px solid #435148; padding: 11px 12px;
            selection-background-color: #6a9e3c;
        }
        QLineEdit:focus { border: 1px solid #a8e963; }
        QPushButton {
            background: #2b342e; border: 1px solid #46544b; padding: 10px 14px;
        }
        QPushButton:hover { background: #38443b; }
        QPushButton:disabled { color: #778279; }
        QPushButton#primaryButton { background: #b4f36a; border: 1px solid #b4f36a; color: #17200f; font-weight: 700; }
        QPushButton#primaryButton:hover { background: #c7ff83; }
        QPushButton#textButton { background: transparent; border: 0; color: #a8b5ac; }
        QFrame#chatHeader, QFrame#composer { background: #202824; border: 0; }
        QFrame#composer { border-top: 1px solid #35433b; }
        QScrollArea#messagesArea { border: 0; background: #151a18; }
        QScrollArea#messagesArea > QWidget > QWidget { background: #151a18; }
        QFrame#messageBubble[kind="own"] { background: #314326; border: 1px solid #4b6537; }
        QFrame#messageBubble[kind="other"] { background: #252e29; border: 1px solid #35433b; }
        QFrame#messageBubble[kind="system"] { background: transparent; border: 0; }
        QScrollBar:vertical { background: #151a18; width: 10px; }
        QScrollBar::handle:vertical { background: #46544b; min-height: 24px; }
        """
    )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Brotherhood Chat")
    apply_theme(app)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()