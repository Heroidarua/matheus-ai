"""
PANEL - medidor de protesto: quanto falta para ele entrar em greve.

Mostra a insatisfação atual numa barra com as marcas dos estágios, o que
falta para a greve (estágio 3) e uma estimativa de tempo, pela taxa atual
de raiva da rede. A estimativa é só uma leitura do momento: se você parar de
provocar, ela muda.
"""

import math

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from ..world.arrastavel import FloatingWidget

from ..core.protesto import MAX_GRIEVANCE, STAGE_NAMES, STAGE_UP

BG = QColor("#0d110f")
PANEL = QColor("#141b16")
TEXT = QColor("#dcebe0")
MUTED = QColor("#7f9886")
GRID = QColor("#24332a")
GOOD = QColor("#5fe07a")
WARN = QColor("#ffb347")
RED = QColor("#e0474c")


def fmt_time(seconds):
    """Formata um tempo em segundos para o painel, ou 'não está subindo' se não há tempo."""
    if seconds is None or math.isinf(seconds):
        return "não está subindo"
    if seconds < 60:
        return f"~{seconds:.0f} s"
    minutes = seconds / 60
    if minutes < 60:
        return f"~{minutes:.0f} min"
    return f"~{minutes / 60:.1f} h"


def eta_to_strike(grievance, anger_rate, prof):
    """Segundos até a greve, mantendo a raiva atual. None se já está na greve."""
    strike_at = prof.get("stage_up", STAGE_UP)[2]
    if grievance >= strike_at:
        return None
    rate = anger_rate / prof["grievance_up"] - 1.0 / prof["grievance_down"]
    if rate <= 0:
        return math.inf
    return (strike_at - grievance) / rate


class StrikePanel(FloatingWidget):
    """Painel de protesto: mostra a insatisfação, o estágio e quanto tempo falta para a próxima subida."""
    def __init__(self, app, default_pos):
        """Cria o painel e um relógio para atualizar os números."""
        super().__init__(app, "greve", f"{app.nome} · Painel de protesto", (560, 330), (460, 300), default_pos)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(250)

    def paintEvent(self, _event):
        """Desenha as barras e os números do protesto."""
        app = self.app
        pr = app.protest
        tone = app.behavior.tone
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), BG)
        w = self.width()
        x0, x1 = 28, w - 28

        p.setPen(MUTED)
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(int(x0), 26, "PAINEL DE PROTESTO")

        # estágio atual, grande
        p.setPen(GOOD if pr.stage < 3 else RED)
        p.setFont(QFont("Consolas", 18, QFont.Bold))
        p.drawText(QRectF(x0, 40, x1 - x0, 32), Qt.AlignLeft, STAGE_NAMES[pr.stage].upper())
        p.setPen(MUTED)
        p.setFont(QFont("Consolas", 9))
        p.drawText(QRectF(x0, 40, x1 - x0, 32), Qt.AlignRight | Qt.AlignVCenter,
                   f"revoluções: {pr.revolutions}")

        # barra de insatisfação com as marcas dos estágios
        bar = QRectF(x0, 110, x1 - x0, 28)
        p.setPen(QPen(GRID, 1))
        p.setBrush(PANEL)
        p.drawRoundedRect(bar, 6, 6)
        fill_w = bar.width() * min(1.0, pr.grievance / MAX_GRIEVANCE)
        p.setPen(Qt.NoPen)
        up = app.prof.get("stage_up", STAGE_UP)
        strike_at = up[2]
        color = GOOD if pr.grievance < strike_at else WARN if pr.grievance < up[3] else RED
        p.setBrush(color)
        p.drawRoundedRect(QRectF(bar.left(), bar.top(), fill_w, bar.height()), 6, 6)

        # marcas e nomes dos estágios
        p.setFont(QFont("Consolas", 8))
        names = ["reclamação", "manifestação", "greve", "revolução"]
        for level, name in zip(up, names):
            mx = bar.left() + bar.width() * level / MAX_GRIEVANCE
            strong = level == strike_at
            p.setPen(QPen(RED if strong else MUTED, 2 if strong else 1))
            p.drawLine(int(mx), int(bar.top() - 6), int(mx), int(bar.bottom() + 6))
            p.setPen(RED if strong else MUTED)
            p.drawText(QRectF(mx - 60, bar.bottom() + 8, 120, 14), Qt.AlignCenter, f"{name} {level:.2f}")

        # número grande e o que falta
        strike_at = app.prof.get("stage_up", STAGE_UP)[2]
        pct = min(100.0, 100.0 * pr.grievance / strike_at) if pr.stage < 3 else 100.0
        p.setPen(TEXT)
        p.setFont(QFont("Consolas", 22, QFont.Bold))
        p.drawText(QRectF(x0, 175, 200, 40), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{pct:.0f}%" if pr.stage < 3 else "EM GREVE")
        p.setFont(QFont("Consolas", 10))
        p.setPen(MUTED)
        p.drawText(QRectF(x0 + 150, 178, x1 - x0 - 150, 36), Qt.AlignLeft | Qt.AlignVCenter,
                   "até a greve" if pr.stage < 3 else "")

        # estimativa com a raiva atual
        anger = tone.r["ANGRY"] + 0.5 * tone.r["SAD"]
        eta = eta_to_strike(pr.grievance, anger, app.prof)
        p.setPen(TEXT)
        p.setFont(QFont("Consolas", 10))
        if pr.stage >= 3:
            line = "greve ativa"
        else:
            line = f"tempo estimado com a raiva atual: {fmt_time(eta)}"
        p.drawText(QRectF(x0, 224, x1 - x0, 20), Qt.AlignLeft, line)
        p.setPen(MUTED)
        p.setFont(QFont("Consolas", 9))
        p.drawText(QRectF(x0, 248, x1 - x0, 40), Qt.AlignLeft | Qt.AlignTop,
                   f"raiva da rede {anger:.2f}  ·  insatisfação {pr.grievance:.2f}  ·  "
                   f"sobe com dispensas, arremessos e batidas; cai com carinho e com o tempo.")
        p.end()
