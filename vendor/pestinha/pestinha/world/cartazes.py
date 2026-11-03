"""
CARTAZES - os cartazes e a bandeira que o pet levanta. Só desenho.

A escolha do texto e do estilo fica em core/protesto.py (Protesto.escolher_cartaz).
"""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen

from .objetos import Thing

STICK = 34                  # px do cabo até o corpo dele



STICK = 34                  # px do cabo até o corpo dele


class SignThing(Thing):
    """Cartaz num cabo, preso em cima do pet."""

    def __init__(self, text, style, scale=1.0):
        """Cartaz num cabo: o tamanho depende do estilo (pequeno, de marcha, de greve, castigo...)."""
        self.text, self.style, self.scale = text, style, scale
        w = int({"small": 116, "march": 150, "strike": 132, "end": 150, "sad": 116, "castigo": 190}[style] * scale)
        h = int({"small": 48, "march": 58, "strike": 54, "end": 54, "sad": 48, "castigo": 86}[style] * scale)
        self.board_w, self.board_h = w, h
        super().__init__(w + 16, h + STICK + 8)
        self.tilt = 0.0
        self.setToolTip("")

    def paintEvent(self, _event):
        """Desenha a placa e o texto (diminuindo a letra até caber)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx = self.width() / 2
        p.translate(cx, 4)
        p.rotate(self.tilt)
        p.setPen(QPen(QColor("#6b4a2b"), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(0, self.board_h - 4), QPointF(0, self.board_h + STICK))
        board = QRectF(-self.board_w / 2, 0, self.board_w, self.board_h)
        fill, ink = {"strike": ("#c9302c", "#ffffff"), "end": ("#e8f7ea", "#1f7a36"),
                     "sad": ("#d9e8ff", "#1d3a66"), "castigo": ("#fff4d6", "#222222")}.get(
            self.style, ("#f7f1df", "#222222"))
        p.setPen(QPen(QColor("#3a2f1f"), 2))
        p.setBrush(QColor(fill))
        p.drawRoundedRect(board, 4, 4)
        p.setPen(QColor(ink))
        area = board.adjusted(6, 4, -6, -4)
        size = 13 if self.style == "castigo" else int((10 if self.style == "small" else 12) * self.scale)
        while size > 6 and QFontMetrics(QFont("Arial Black", size)).boundingRect(
                area.toRect(), Qt.AlignCenter | Qt.TextWordWrap, self.text).height() > area.height():
            size -= 1                                    # diminui a letra até o texto caber na placa
        p.setFont(QFont("Arial Black", max(7, size)))
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, self.text)
        p.end()


class FlagThing(Thing):
    """Bandeira tremulando num mastro: a revolução."""

    def __init__(self, text, scale=1.0):
        """Bandeira da revolução num mastro; o tamanho cresce com `scale`."""
        self.text, self.scale = text, scale
        self.flag_w, self.flag_h = int(190 * scale), int(110 * scale)
        self.pole = int(self.flag_h + 70 * scale)
        super().__init__(self.flag_w + 30, self.pole + 10)
        self.tilt = 0.0
        self.setToolTip("")

    def paintEvent(self, _event):
        """Desenha a bandeira tremulando e o texto."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        now = time.monotonic()
        x0, y0 = 10, 6
        p.setPen(QPen(QColor("#6b4a2b"), max(4, int(5 * self.scale)), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x0, y0), QPointF(x0, y0 + self.pole))
        # pano com onda: a borda de cima e a de baixo ondulam no tempo
        path = QPainterPath()
        steps = 24
        wave = 7 * self.scale
        top = [(x0 + self.flag_w * i / steps,
                y0 + wave * math.sin(now * 5 - i / steps * 6) * (i / steps)) for i in range(steps + 1)]
        path.moveTo(*top[0])
        for x, y in top[1:]:
            path.lineTo(x, y)
        for x, y in reversed(top):
            path.lineTo(x, y + self.flag_h)
        path.closeSubpath()
        p.setPen(QPen(QColor("#7a1418"), 2))
        p.setBrush(QColor("#d32f34"))
        p.drawPath(path)
        p.setPen(QColor("#ffffff"))
        box = QRectF(x0 + 8, y0 + 6, self.flag_w - 16, self.flag_h - 12)
        flags = Qt.AlignCenter | Qt.TextWordWrap
        size = max(8, int(13 * self.scale))
        while size > 6:                                # diminui a letra até o texto inteiro caber no pano
            font = QFont("Arial Black", size)
            if QFontMetrics(font).boundingRect(box.toRect(), flags, self.text).height() <= box.height():
                break
            size -= 1
        p.setFont(QFont("Arial Black", size))
        p.drawText(box, flags, self.text)
        p.end()


# ESTADO




def criar_cartaz(info):
    """Monta o widget do cartaz (ou da bandeira) a partir do que o Protesto escolheu."""
    if info["bandeira"]:
        return FlagThing(info["texto"], info["escala"])
    return SignThing(info["texto"], info["estilo"], info["escala"])
