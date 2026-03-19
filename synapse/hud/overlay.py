"""Main overlay window — frameless, transparent, always on top."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from synapse.hud.widgets.notification import NotificationStack
from synapse.hud.widgets.status_bar import StatusBar


class SynapseOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()

        # Frameless, transparent, always on top, non-interactive by default
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.status_bar = StatusBar()
        self._layout.addWidget(self.status_bar)
        self._layout.addStretch()

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(0, 0, geo.width(), 28)

        # Notification stack (bottom-right corner)
        self._notifications: NotificationStack | None = None

    def _ensure_notifications(self) -> NotificationStack:
        if not self._notifications:
            self._notifications = NotificationStack(self)
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.geometry()
                self._notifications.move(geo.width() - 400, 40)
        return self._notifications

    @pyqtSlot(str, str, str)
    def show_notification(self, agent: str, status: str, summary: str) -> None:
        stack = self._ensure_notifications()
        stack.push(agent, status, summary)
        stack.show()
        self.status_bar.update_agent(agent, status)

    @pyqtSlot(str)
    def update_status(self, text: str) -> None:
        self.status_bar.set_status(text)
