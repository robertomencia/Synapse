"""Dark glassmorphism theme constants."""

OVERLAY_BG = "rgba(10, 10, 20, 200)"
ACCENT_BLUE = "#4FC3F7"
ACCENT_GREEN = "#69F0AE"
ACCENT_ORANGE = "#FFB74D"
ACCENT_RED = "#EF5350"
TEXT_PRIMARY = "#E0E0E0"
TEXT_SECONDARY = "#9E9E9E"
FONT_FAMILY = "JetBrains Mono, Consolas, Monospace"
FONT_SIZE = 12

STATUS_BAR_STYLE = f"""
    QWidget {{
        background-color: rgba(10, 10, 20, 220);
        border-bottom: 1px solid rgba(79, 195, 247, 80);
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE}px;
        padding: 2px 8px;
    }}
"""

NOTIFICATION_STYLE = """
    QFrame {{
        background-color: rgba(15, 15, 30, 230);
        border: 1px solid {border_color};
        border-radius: 6px;
    }}
    QLabel {{
        color: {text_color};
        font-family: JetBrains Mono, Consolas, Monospace;
        font-size: 12px;
    }}
"""

STATUS_COLORS = {
    "insight": ACCENT_BLUE,
    "alert": ACCENT_RED,
    "action": ACCENT_GREEN,
    "idle": TEXT_SECONDARY,
}
