"""
Synapse Demo GIF Generator
--------------------------
Genera el GIF de demostración usando SÓLO stdlib de Python (sin dependencias externas).
Implementa el encoder GIF87a/89a completo: LZW compression, color table, animation frames.

Escenas:
  0-4   → Pantalla inicial  "SYNAPSE OS"  fondo negro + titulo
  5-9   → "EVENT DETECTED"  auth.py modificado
  10-14 → Dev Agent analiza
  15-19 → Security Agent verifica
  20-24 → Orquestador coordina
  25-29 → Notificacion final  "ZERO CLOUD · 100% LOCAL"
"""

from __future__ import annotations
import struct
import os

# ---------------------------------------------------------------------------
# Paleta de 256 colores (RGB flat list, 256*3 bytes)
# ---------------------------------------------------------------------------
# Indices que usamos:
#   0  → BG negro         (0,0,0) → #000000
#   1  → Blanco           (255,255,255)
#   2  → Verde neón       (0,255,128)
#   3  → Azul             (0,150,255)
#   4  → Violeta          (180,0,255)
#   5  → Naranja          (255,140,0)
#   6  → Rojo alerta      (255,50,50)
#   7  → Gris suave       (80,80,80)
#   8  → Gris claro       (140,140,140)
#   9  → Verde oscuro     (0,120,60)
#   10 → Azul oscuro      (0,60,120)
#   11 → Fondo panel      (15,15,25)
#   12 → Borde panel      (40,40,60)
#   13 → Amarillo         (255,220,0)
#   rest → negro

_NAMED = [
    (0,   0,   0),    # 0  BG
    (255,255,255),    # 1  White
    (0,  255,128),    # 2  Green neon
    (0,  150,255),    # 3  Blue
    (180,  0,255),    # 4  Violet
    (255,140,  0),    # 5  Orange
    (255, 50, 50),    # 6  Red alert
    (80,  80, 80),    # 7  Gray soft
    (140,140,140),    # 8  Gray light
    (0,  120, 60),    # 9  Dark green
    (0,   60,120),    # 10 Dark blue
    (15,  15, 25),    # 11 Panel BG
    (40,  40, 60),    # 12 Panel border
    (255,220,  0),    # 13 Yellow
]
_PALETTE: list[tuple[int,int,int]] = _NAMED + [(0,0,0)] * (256 - len(_NAMED))
_PALETTE_BYTES = bytes(c for rgb in _PALETTE for c in rgb)

# Canvas size
W, H = 600, 340

# ---------------------------------------------------------------------------
# Tiny pixel-font 5x7 (only ASCII 32-126 stored as bits)
# ---------------------------------------------------------------------------
# Using a minimal hardcoded bitmap font (5 wide x 7 tall per glyph)
# Each character = 7 bytes; bit 4 = leftmost pixel

_FONT_5X7: dict[str, list[int]] = {
    ' ': [0x00,0x00,0x00,0x00,0x00,0x00,0x00],
    'A': [0x0E,0x11,0x11,0x1F,0x11,0x11,0x11],
    'B': [0x1E,0x11,0x11,0x1E,0x11,0x11,0x1E],
    'C': [0x0E,0x11,0x10,0x10,0x10,0x11,0x0E],
    'D': [0x1E,0x11,0x11,0x11,0x11,0x11,0x1E],
    'E': [0x1F,0x10,0x10,0x1E,0x10,0x10,0x1F],
    'F': [0x1F,0x10,0x10,0x1E,0x10,0x10,0x10],
    'G': [0x0E,0x11,0x10,0x17,0x11,0x11,0x0F],
    'H': [0x11,0x11,0x11,0x1F,0x11,0x11,0x11],
    'I': [0x0E,0x04,0x04,0x04,0x04,0x04,0x0E],
    'J': [0x07,0x02,0x02,0x02,0x02,0x12,0x0C],
    'K': [0x11,0x12,0x14,0x18,0x14,0x12,0x11],
    'L': [0x10,0x10,0x10,0x10,0x10,0x10,0x1F],
    'M': [0x11,0x1B,0x15,0x15,0x11,0x11,0x11],
    'N': [0x11,0x19,0x15,0x13,0x11,0x11,0x11],
    'O': [0x0E,0x11,0x11,0x11,0x11,0x11,0x0E],
    'P': [0x1E,0x11,0x11,0x1E,0x10,0x10,0x10],
    'Q': [0x0E,0x11,0x11,0x11,0x15,0x12,0x0D],
    'R': [0x1E,0x11,0x11,0x1E,0x14,0x12,0x11],
    'S': [0x0F,0x10,0x10,0x0E,0x01,0x01,0x1E],
    'T': [0x1F,0x04,0x04,0x04,0x04,0x04,0x04],
    'U': [0x11,0x11,0x11,0x11,0x11,0x11,0x0E],
    'V': [0x11,0x11,0x11,0x11,0x11,0x0A,0x04],
    'W': [0x11,0x11,0x15,0x15,0x15,0x1B,0x11],
    'X': [0x11,0x11,0x0A,0x04,0x0A,0x11,0x11],
    'Y': [0x11,0x11,0x0A,0x04,0x04,0x04,0x04],
    'Z': [0x1F,0x01,0x02,0x04,0x08,0x10,0x1F],
    '0': [0x0E,0x11,0x13,0x15,0x19,0x11,0x0E],
    '1': [0x04,0x0C,0x04,0x04,0x04,0x04,0x0E],
    '2': [0x0E,0x11,0x01,0x06,0x08,0x10,0x1F],
    '3': [0x0E,0x11,0x01,0x06,0x01,0x11,0x0E],
    '4': [0x02,0x06,0x0A,0x12,0x1F,0x02,0x02],
    '5': [0x1F,0x10,0x1E,0x01,0x01,0x11,0x0E],
    '6': [0x06,0x08,0x10,0x1E,0x11,0x11,0x0E],
    '7': [0x1F,0x01,0x02,0x04,0x08,0x08,0x08],
    '8': [0x0E,0x11,0x11,0x0E,0x11,0x11,0x0E],
    '9': [0x0E,0x11,0x11,0x0F,0x01,0x02,0x0C],
    ':': [0x00,0x04,0x00,0x00,0x04,0x00,0x00],
    '.': [0x00,0x00,0x00,0x00,0x00,0x06,0x06],
    '-': [0x00,0x00,0x00,0x1F,0x00,0x00,0x00],
    '_': [0x00,0x00,0x00,0x00,0x00,0x00,0x1F],
    '/': [0x01,0x01,0x02,0x04,0x08,0x10,0x10],
    '→': [0x00,0x04,0x02,0x1F,0x02,0x04,0x00],
    '·': [0x00,0x00,0x00,0x04,0x00,0x00,0x00],
    '✓': [0x00,0x01,0x02,0x14,0x08,0x00,0x00],
    '⚡': [0x06,0x0C,0x1F,0x06,0x0C,0x18,0x00],
    '%': [0x19,0x1A,0x02,0x04,0x0B,0x13,0x00],
    '!': [0x04,0x04,0x04,0x04,0x00,0x06,0x06],
    '[': [0x0E,0x08,0x08,0x08,0x08,0x08,0x0E],
    ']': [0x0E,0x02,0x02,0x02,0x02,0x02,0x0E],
    '(': [0x02,0x04,0x08,0x08,0x08,0x04,0x02],
    ')': [0x08,0x04,0x02,0x02,0x02,0x04,0x08],
    '>': [0x00,0x08,0x04,0x02,0x04,0x08,0x00],
    '<': [0x00,0x02,0x04,0x08,0x04,0x02,0x00],
    '#': [0x0A,0x0A,0x1F,0x0A,0x1F,0x0A,0x0A],
    '@': [0x0E,0x11,0x17,0x15,0x17,0x10,0x0F],
    '+': [0x00,0x04,0x04,0x1F,0x04,0x04,0x00],
    '=': [0x00,0x00,0x1F,0x00,0x1F,0x00,0x00],
    '"': [0x0A,0x0A,0x00,0x00,0x00,0x00,0x00],
    "'": [0x04,0x04,0x08,0x00,0x00,0x00,0x00],
    'a': [0x00,0x00,0x0E,0x01,0x0F,0x11,0x0F],
    'b': [0x10,0x10,0x1E,0x11,0x11,0x11,0x1E],
    'c': [0x00,0x00,0x0E,0x10,0x10,0x11,0x0E],
    'd': [0x01,0x01,0x0F,0x11,0x11,0x11,0x0F],
    'e': [0x00,0x00,0x0E,0x11,0x1F,0x10,0x0E],
    'f': [0x06,0x09,0x08,0x1E,0x08,0x08,0x08],
    'g': [0x00,0x00,0x0F,0x11,0x0F,0x01,0x0E],
    'h': [0x10,0x10,0x1E,0x11,0x11,0x11,0x11],
    'i': [0x04,0x00,0x0C,0x04,0x04,0x04,0x0E],
    'j': [0x02,0x00,0x06,0x02,0x02,0x12,0x0C],
    'k': [0x10,0x10,0x11,0x12,0x1C,0x12,0x11],
    'l': [0x0C,0x04,0x04,0x04,0x04,0x04,0x0E],
    'm': [0x00,0x00,0x1A,0x15,0x15,0x11,0x11],
    'n': [0x00,0x00,0x1E,0x11,0x11,0x11,0x11],
    'o': [0x00,0x00,0x0E,0x11,0x11,0x11,0x0E],
    'p': [0x00,0x00,0x1E,0x11,0x1E,0x10,0x10],
    'q': [0x00,0x00,0x0F,0x11,0x0F,0x01,0x01],
    'r': [0x00,0x00,0x16,0x19,0x10,0x10,0x10],
    's': [0x00,0x00,0x0E,0x10,0x0E,0x01,0x1E],
    't': [0x08,0x08,0x1E,0x08,0x08,0x09,0x06],
    'u': [0x00,0x00,0x11,0x11,0x11,0x13,0x0D],
    'v': [0x00,0x00,0x11,0x11,0x11,0x0A,0x04],
    'w': [0x00,0x00,0x11,0x15,0x15,0x1B,0x11],
    'x': [0x00,0x00,0x11,0x0A,0x04,0x0A,0x11],
    'y': [0x00,0x00,0x11,0x11,0x0F,0x01,0x0E],
    'z': [0x00,0x00,0x1F,0x02,0x04,0x08,0x1F],
    '|': [0x04,0x04,0x04,0x04,0x04,0x04,0x04],
}


def _get_glyph(ch: str) -> list[int]:
    return _FONT_5X7.get(ch, _FONT_5X7.get(' ', [0]*7))


# ---------------------------------------------------------------------------
# Canvas — indexed color buffer
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, w: int, h: int, bg: int = 0):
        self.w = w
        self.h = h
        self.pixels = bytearray([bg] * (w * h))

    def fill(self, color: int) -> None:
        self.pixels[:] = bytearray([color] * (self.w * self.h))

    def put_pixel(self, x: int, y: int, color: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.pixels[y * self.w + x] = color

    def rect(self, x: int, y: int, w: int, h: int, color: int, fill: bool = True) -> None:
        for row in range(h):
            for col in range(w):
                if fill or row == 0 or row == h-1 or col == 0 or col == w-1:
                    self.put_pixel(x+col, y+row, color)

    def hline(self, x: int, y: int, length: int, color: int) -> None:
        for i in range(length):
            self.put_pixel(x+i, y, color)

    def text(self, text: str, x: int, y: int, color: int, scale: int = 1) -> int:
        """Draw text, return x after last char."""
        cx = x
        for ch in text:
            glyph = _get_glyph(ch)
            for row_idx, row_bits in enumerate(glyph):
                for col_idx in range(5):
                    if row_bits & (1 << (4 - col_idx)):
                        for sy in range(scale):
                            for sx in range(scale):
                                self.put_pixel(cx + col_idx*scale + sx,
                                               y + row_idx*scale + sy, color)
            cx += (5 + 1) * scale
        return cx

    def text_centered(self, text: str, y: int, color: int, scale: int = 1) -> None:
        char_w = (5 + 1) * scale
        total_w = len(text) * char_w - scale
        x = (self.w - total_w) // 2
        self.text(text, x, y, color, scale)

    def copy(self) -> 'Canvas':
        c = Canvas(self.w, self.h)
        c.pixels[:] = self.pixels
        return c


# ---------------------------------------------------------------------------
# GIF encoder (pure Python)
# ---------------------------------------------------------------------------

def _lzw_compress(data: bytes, min_code_size: int) -> bytes:
    """LZW compression for GIF."""
    output_bits: list[int] = []
    clear_code = 1 << min_code_size
    eoi_code = clear_code + 1
    code_size = min_code_size + 1
    table: dict[bytes, int] = {bytes([i]): i for i in range(clear_code)}
    next_code = eoi_code + 1
    max_code = (1 << code_size)

    def emit(code: int) -> None:
        b = code
        for _ in range(code_size):
            output_bits.append(b & 1)
            b >>= 1

    emit(clear_code)
    buffer = bytes()
    for byte in data:
        candidate = buffer + bytes([byte])
        if candidate in table:
            buffer = candidate
        else:
            emit(table[buffer])
            if next_code < 4096:
                table[candidate] = next_code
                next_code += 1
                if next_code > max_code and code_size < 12:
                    code_size += 1
                    max_code = (1 << code_size)
            elif next_code >= 4096:
                emit(clear_code)
                code_size = min_code_size + 1
                max_code = (1 << code_size)
                table = {bytes([i]): i for i in range(clear_code)}
                next_code = eoi_code + 1
            buffer = bytes([byte])
    if buffer:
        emit(table[buffer])
    emit(eoi_code)

    # Pack bits into bytes (little-endian)
    result = bytearray()
    for i in range(0, len(output_bits), 8):
        byte_bits = output_bits[i:i+8]
        while len(byte_bits) < 8:
            byte_bits.append(0)
        val = sum(b << j for j, b in enumerate(byte_bits))
        result.append(val)
    return bytes(result)


def _gif_sub_blocks(data: bytes) -> bytes:
    """Wrap data in GIF sub-blocks (max 255 bytes each)."""
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i+255]
        out.append(len(chunk))
        out.extend(chunk)
    out.append(0)  # block terminator
    return bytes(out)


def encode_gif(frames: list[bytes], delay_cs: list[int], w: int, h: int,
               palette: bytes) -> bytes:
    """Encode animated GIF89a.

    Args:
        frames:   list of raw indexed pixel data (w*h bytes each)
        delay_cs: centiseconds per frame
        w, h:     canvas dimensions
        palette:  768 bytes (256 RGB triplets)
    """
    out = bytearray()

    # Header
    out.extend(b'GIF89a')
    # Logical screen descriptor
    out.extend(struct.pack('<HH', w, h))
    # Global color table flag=1, color resolution=7, sort=0, size=7 (256 colors)
    out.append(0b11110111)  # packed
    out.append(0)           # background color index
    out.append(0)           # pixel aspect ratio
    out.extend(palette)     # 768 bytes

    # Netscape loop extension (loop forever)
    out.extend(b'\x21\xFF\x0B')
    out.extend(b'NETSCAPE2.0')
    out.extend(b'\x03\x01\x00\x00\x00')  # 3 bytes, sub-block id=1, loop=0

    for idx, frame_data in enumerate(frames):
        delay = delay_cs[idx] if idx < len(delay_cs) else 10

        # Graphic Control Extension
        out.extend(b'\x21\xF9\x04')
        out.append(0x00)  # disposal=0, no user input, no transparent
        out.extend(struct.pack('<H', delay))  # delay in centiseconds
        out.append(0)     # transparent color index (unused)
        out.append(0)     # block terminator

        # Image descriptor
        out.append(0x2C)
        out.extend(struct.pack('<HHHHB', 0, 0, w, h, 0))  # no local color table

        min_code_size = 8  # always 8 for 256-color
        out.append(min_code_size)
        compressed = _lzw_compress(frame_data, min_code_size)
        out.extend(_gif_sub_blocks(compressed))

    out.append(0x3B)  # GIF trailer
    return bytes(out)


# ---------------------------------------------------------------------------
# Scene builders
# ---------------------------------------------------------------------------

def _draw_scanlines(c: Canvas, alpha: int = 7) -> None:
    """Subtle horizontal scanlines for CRT effect."""
    for y in range(0, c.h, 3):
        c.hline(0, y, c.w, 7)  # gray soft


def _draw_top_bar(c: Canvas, title: str) -> None:
    c.rect(0, 0, c.w, 20, 12, fill=True)
    c.hline(0, 20, c.w, 2)
    c.text("SYNAPSE", 8, 6, 2, scale=1)
    c.text("v0.1", 74, 6, 7, scale=1)
    c.text(title, c.w - len(title)*6 - 8, 6, 8, scale=1)


def _draw_bottom_bar(c: Canvas, msg: str, color: int = 7) -> None:
    c.rect(0, c.h-18, c.w, 18, 11, fill=True)
    c.hline(0, c.h-18, c.w, 12)
    c.text_centered(msg, c.h-12, color, scale=1)


def _blink_cursor(c: Canvas, x: int, y: int, tick: int) -> None:
    if tick % 2 == 0:
        c.rect(x, y, 6, 9, 2, fill=True)


def make_intro_frames() -> list[Canvas]:
    frames = []
    # Frame 0-3: spinning build-up  (4 frames)
    bar_chars = ['|', '/', '-', '\\']
    for i in range(4):
        c = Canvas(W, H, 0)
        c.text_centered("SYNAPSE OS", H//2 - 30, 2, scale=3)
        c.text_centered("Tu sistema operativo de IA", H//2 + 12, 8, scale=1)
        c.text_centered(f"Iniciando {bar_chars[i]}", H//2 + 30, 7, scale=1)
        c.text_centered("100% LOCAL  |  ZERO CLOUD  |  SIEMPRE ACTIVO", H - 30, 3, scale=1)
        frames.append(c)
    return frames


def make_event_frames() -> list[Canvas]:
    frames = []
    msgs = [
        "Monitorizando...",
        "Cambio detectado en filesystem",
        "auth.py  +47 lineas modificadas",
        "Activando agentes...",
        "Pipeline iniciado",
    ]
    for i, msg in enumerate(msgs):
        c = Canvas(W, H, 11)
        _draw_top_bar(c, "PERCEPTION")
        # Event box
        c.rect(20, 35, W-40, 60, 12)
        c.rect(21, 36, W-42, 58, 11, fill=True)
        c.text("EVENT BUS", 30, 42, 3, scale=1)
        c.hline(30, 52, W-60, 12)
        c.text(f">>> {msg}", 30, 57, 2, scale=1)
        # File info (visible from frame 2+)
        if i >= 2:
            c.rect(20, 105, W-40, 50, 12)
            c.rect(21, 106, W-42, 48, 11, fill=True)
            c.text("FILE WATCHER", 30, 112, 5, scale=1)
            c.hline(30, 122, W-60, 12)
            c.text("synapse/agents/auth.py", 30, 128, 1, scale=1)
            c.text("+47 lines  |  JWT validation  |  token expiry", 30, 140, 8, scale=1)
        _draw_bottom_bar(c, f"SYNAPSE PERCEPTION ENGINE  [{i+1}/5]", 7)
        frames.append(c)
    return frames


def make_dev_agent_frames() -> list[Canvas]:
    frames = []
    lines = [
        ("DEV AGENT", "Analizando cambios en auth.py...", 3, 2),
        ("DEV AGENT", "JWT token: expiry no configurado", 3, 13),
        ("DEV AGENT", "Patron detectado: auth flow", 3, 5),
        ("DEV AGENT", "Recomendacion: revisar exp claim", 3, 2),
        ("DEV AGENT", "Analisis completado ✓", 2, 2),
    ]
    for i, (agent, msg, ac, mc) in enumerate(lines):
        c = Canvas(W, H, 11)
        _draw_top_bar(c, "DEV AGENT")
        # Agent panel
        c.rect(20, 35, W-40, 90, 12)
        c.rect(21, 36, W-42, 88, 11, fill=True)
        # Agent icon area
        c.rect(25, 40, 24, 24, 3)
        c.text("DEV", 28, 47, 2, scale=1)
        c.text(agent, 56, 42, ac, scale=1)
        c.hline(25, 66, W-50, 12)
        # Show cumulative log lines
        for j in range(i+1):
            _, lmsg, _, lc = lines[j]
            c.text(f"  {lmsg}", 25, 72 + j*11, lc if j == i else 8, scale=1)
        # Progress bar
        progress = int((i+1) / len(lines) * (W-80))
        c.rect(40, 135, W-80, 8, 7)
        c.rect(40, 135, progress, 8, 3, fill=True)
        _draw_bottom_bar(c, f"DEV AGENT RUNNING  [{i+1}/{len(lines)}]", 3)
        frames.append(c)
    return frames


def make_security_agent_frames() -> list[Canvas]:
    frames = []
    checks = [
        ("Escaneando credenciales...",         13, False),
        ("API keys:         NO encontradas",   2,  True),
        ("Passwords:        NO encontradas",   2,  True),
        ("Tokens hardcoded: NO encontrados",   2,  True),
        ("SEGURIDAD VERIFICADA  ✓",            2,  True),
    ]
    for i, (msg, mc, ok) in enumerate(checks):
        c = Canvas(W, H, 11)
        _draw_top_bar(c, "SECURITY")
        c.rect(20, 35, W-40, 100, 12)
        c.rect(21, 36, W-42, 98, 11, fill=True)
        # Shield icon
        c.rect(25, 40, 22, 26, 6 if not ok else 2)
        c.text("SEC", 27, 49, 6 if not ok else 2, scale=1)
        c.text("SECURITY AGENT", 56, 42, 6 if not ok else 2, scale=1)
        c.hline(25, 68, W-50, 12)
        # Show previous checks
        for j in range(i+1):
            _, lc, lok = checks[j]
            prefix = "[OK]" if lok else "[..]"
            c.text(f"  {prefix}  {checks[j][0]}", 25, 74 + j*11, 2 if lok else 13, scale=1)
        _draw_bottom_bar(c, "SECURITY AGENT SCANNING", 6 if i < 4 else 2)
        frames.append(c)
    return frames


def make_orchestrator_frames() -> list[Canvas]:
    frames = []
    agents_status = [
        [("DEV",      3, "DONE ✓"),
         ("SECURITY", 13, "RUNNING"),
         ("OPS",      7, "IDLE"),
         ("LIFE",     7, "IDLE")],
        [("DEV",      2, "DONE ✓"),
         ("SECURITY", 2, "DONE ✓"),
         ("OPS",      13, "RUNNING"),
         ("LIFE",     7, "IDLE")],
        [("DEV",      2, "DONE ✓"),
         ("SECURITY", 2, "DONE ✓"),
         ("OPS",      2, "DONE ✓"),
         ("LIFE",     13, "RUNNING")],
        [("DEV",      2, "DONE ✓"),
         ("SECURITY", 2, "DONE ✓"),
         ("OPS",      2, "DONE ✓"),
         ("LIFE",     2, "DONE ✓")],
    ]
    for i, statuses in enumerate(agents_status):
        c = Canvas(W, H, 11)
        _draw_top_bar(c, "ORCHESTRATOR")
        c.text_centered("LANGGRAPH ORCHESTRATOR", 35, 3, scale=1)
        c.hline(20, 48, W-40, 12)
        # Agent boxes
        box_w = (W - 60) // 4
        for j, (name, color, status) in enumerate(statuses):
            bx = 20 + j * (box_w + 5)
            by = 55
            bh = 70
            c.rect(bx, by, box_w, bh, color)
            c.rect(bx+1, by+1, box_w-2, bh-2, 11, fill=True)
            c.text_centered_in(name, bx, box_w, by+10, color, c)
            c.text_centered_in(status, bx, box_w, by+30, color, c)
        # Arrow flow
        c.text_centered("EVENT  >  AGENTS  >  MEMORY  >  NOTIFY", 145, 8, scale=1)
        all_done = all(s[1] == 2 for s in statuses)
        _draw_bottom_bar(c, "TODOS LOS AGENTES COORDINADOS ✓" if all_done else f"COORDINANDO AGENTES [{i+1}/4]",
                         2 if all_done else 3)
        frames.append(c)
    return frames


def make_notify_frames() -> list[Canvas]:
    frames = []
    msgs = [
        "Insights listos — preparando notificacion",
        "SYNAPSE > auth.py analizado correctamente",
        "Sin riesgos de seguridad detectados ✓",
        "Memoria actualizada con nuevo contexto",
        "ZERO CLOUD  ·  100% LOCAL  ·  ALWAYS ON",
    ]
    colors = [3, 2, 2, 4, 13]
    for i, (msg, color) in enumerate(zip(msgs, colors)):
        c = Canvas(W, H, 0)
        # Big notification card
        c.rect(30, 50, W-60, H-100, 12)
        c.rect(31, 51, W-62, H-102, 11, fill=True)
        c.rect(31, 51, W-62, 20, color, fill=True)
        c.text("SYNAPSE NOTIFICATION", 40, 57, 0, scale=1)
        c.hline(31, 71, W-62, 12)
        # Show all msgs revealed so far
        for j in range(i+1):
            c.text(msgs[j], 40, 80 + j*18, colors[j] if j == i else 8, scale=1)
        # Bottom brand
        c.text_centered("Tu IA. Tu maquina. Sin limites.", H-35, 7, scale=1)
        c.text_centered("SYNAPSE OS  v0.1", H-22, 2, scale=1)
        frames.append(c)
    return frames


# Monkey-patch Canvas to add centered text within a box
def _text_centered_in(self, text: str, box_x: int, box_w: int,
                       y: int, color: int, canvas: Canvas) -> None:
    char_w = 6  # 5+1 px per char at scale 1
    total_w = len(text) * char_w - 1
    x = box_x + (box_w - total_w) // 2
    canvas.text(text, x, y, color, scale=1)

Canvas.text_centered_in = _text_centered_in  # type: ignore


# ---------------------------------------------------------------------------
# Compose all scenes
# ---------------------------------------------------------------------------

def build_all_frames() -> tuple[list[bytes], list[int]]:
    scenes: list[list[Canvas]] = [
        make_intro_frames(),
        make_event_frames(),
        make_dev_agent_frames(),
        make_security_agent_frames(),
        make_orchestrator_frames(),
        make_notify_frames(),
    ]
    # Delays in centiseconds
    delays: list[list[int]] = [
        [80, 80, 80, 120],   # intro
        [70, 70, 90, 90, 120],  # event
        [70, 70, 70, 70, 100],  # dev
        [70, 70, 70, 70, 120],  # security
        [80, 80, 80, 120],      # orchestrator
        [80, 80, 80, 80, 200],  # notify
    ]

    raw_frames: list[bytes] = []
    raw_delays: list[int] = []
    for scene_frames, scene_delays in zip(scenes, delays):
        for frame, delay in zip(scene_frames, scene_delays):
            raw_frames.append(bytes(frame.pixels))
            raw_delays.append(delay)

    return raw_frames, raw_delays


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'synapse_demo.gif')

    print("Building frames...")
    frames, delays = build_all_frames()
    print(f"  {len(frames)} frames ready ({W}x{H})")

    print("Encoding GIF...")
    gif_data = encode_gif(frames, delays, W, H, _PALETTE_BYTES)
    print(f"  GIF size: {len(gif_data)//1024} KB")

    with open(out_path, 'wb') as f:
        f.write(gif_data)
    print(f"Done → {os.path.abspath(out_path)}")


if __name__ == '__main__':
    main()
