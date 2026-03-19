"""Slide-in notification card widget."""

from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from synapse.hud import theme


class NotificationCard(QFrame):
    dismissed = pyqtSignal()

    STATUS_ICONS = {
        "insight": "◈",
        "alert": "⚠",
        "action": "✓",
        "idle": "·",
    }

    def __init__(self, parent: QWidget, agent: str, status: str, summary: str) -> None:
        super().__init__(parent)
        color = theme.STATUS_COLORS.get(status, theme.TEXT_SECONDARY)
        icon = self.STATUS_ICONS.get(status, "·")

        self.setStyleSheet(
            theme.NOTIFICATION_STYLE.format(border_color=color, text_color=theme.TEXT_PRIMARY)
        )
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        header = QLabel(f'<span style="color:{color}">{icon} [{agent.upper()}]</span>')
        header.setFont(QFont(theme.FONT_FAMILY, theme.FONT_SIZE - 1))
        header.setTextFormat(Qt.TextFormat.RichText)

        body = QLabel(summary[:120])
        body.setFont(QFont(theme.FONT_FAMILY, theme.FONT_SIZE))
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")

        layout.addWidget(header)
        layout.addWidget(body)

        # Auto-dismiss after 8 seconds
        QTimer.singleShot(8000, self._dismiss)

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()


class NotificationStack(QWidget):
    """Manages a stack of notifications in a corner."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._cards: list[NotificationCard] = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def push(self, agent: str, status: str, summary: str) -> None:
        card = NotificationCard(self, agent, status, summary)
        card.dismissed.connect(lambda: self._remove(card))
        self._cards.append(card)
        self._reposition()
        card.show()

    def _remove(self, card: NotificationCard) -> None:
        if card in self._cards:
            self._cards.remove(card)
            card.deleteLater()
        self._reposition()

    def _reposition(self) -> None:
        y = 0
        for card in self._cards:
            card.adjustSize()
            card.move(0, y)
            y += card.height() + 6
        self.setFixedHeight(max(y, 1))
        self.setFixedWidth(390)
