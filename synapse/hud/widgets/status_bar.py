"""Always-visible status bar showing agent states."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from synapse.hud import theme


class AgentDot(QLabel):
    def __init__(self, agent_name: str) -> None:
        super().__init__()
        self.agent_name = agent_name
        self._status = "idle"
        self._update_style()

    def set_status(self, status: str) -> None:
        self._status = status
        self._update_style()

    def _update_style(self) -> None:
        color = theme.STATUS_COLORS.get(self._status, theme.TEXT_SECONDARY)
        self.setText(f'<span style="color:{color}">●</span> {self.agent_name}')
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setFont(QFont(theme.FONT_FAMILY, theme.FONT_SIZE - 1))
        self.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; padding: 0 6px;")


class StatusBar(QWidget):
    AGENTS = ["dev", "security", "ops", "life"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(theme.STATUS_BAR_STYLE)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        logo = QLabel("◈ SYNAPSE")
        logo.setFont(QFont(theme.FONT_FAMILY, theme.FONT_SIZE, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {theme.ACCENT_BLUE}; padding: 0 12px 0 4px;")
        layout.addWidget(logo)

        self._dots: dict[str, AgentDot] = {}
        for agent in self.AGENTS:
            dot = AgentDot(agent)
            self._dots[agent] = dot
            layout.addWidget(dot)

        layout.addStretch()

        self._status_label = QLabel("watching...")
        self._status_label.setFont(QFont(theme.FONT_FAMILY, theme.FONT_SIZE - 1))
        self._status_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; padding: 0 8px;")
        layout.addWidget(self._status_label)

    def update_agent(self, agent_name: str, status: str) -> None:
        if agent_name in self._dots:
            self._dots[agent_name].set_status(status)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)
