"""
FIREWORKS - o fogo de artifício do bichinho feliz.

Não é sorteado. Quem decide é a rede: a população motora CHEER (alegria) carrega
um acúmulo de euforia (a "euforia" fica em app.py). Quando a euforia enche, ele
solta o fogo, e depois precisa de um tempo de refratário antes de soltar outro.

Desenho: um foguete sobe do pet, explode em partículas e as partículas caem e
somem. A janela é transparente e não recebe cliques.
"""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..body.pet import overlay_flags, set_no_activate
from ..ajustes import (
    TAMANHO_JANELA_FOGOS as WIN,
    TEMPO_FOGUETE as ROCKET_TIME,
    GRAVIDADE_FOGOS as GRAVITY,
    VIDA_PARTICULA as LIFE,
)

PALETTE = ["#ff6b6b", "#ffd84d", "#63e56f", "#6bb8ff", "#e98bff", "#ffffff"]


class Fireworks(QWidget):
    """Fogos de artifício: um foguete sobe e explode em pontos coloridos. Não recebe clique (passa através)."""
    def __init__(self):
        """Cria a janela transparente dos fogos, que deixa o mouse passar."""
        super().__init__(None, overlay_flags() | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(WIN, WIN)
        self.rocket = None          # [x, y, vy, t0] enquanto sobe
        self.sparks = []            # [x, y, vx, vy, t0, cor]
        self._pausado = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.hide()

    def showEvent(self, event):
        """Ao aparecer, não rouba o foco do programa que você está usando."""
        super().showEvent(event)
        set_no_activate(self)

    def launch(self, x, y):
        """Solta o foguete de (x, y), a posição do pet na tela."""
        self.move(int(x - WIN / 2), int(y - WIN))
        self.rocket = [WIN / 2, WIN - 40.0, -380.0, 0.0]
        self.sparks = []
        self.show()
        if not self._pausado:
            self.timer.start(16)

    def pausar(self, pausado):
        """Pausa ou retoma a animação junto com a sessão."""
        self._pausado = pausado
        if pausado:
            self.timer.stop()
        elif self.rocket is not None or self.sparks:
            self.timer.start(16)

    def recolher(self):
        """Para e some na hora (o efeito foi desligado ou o pet foi escondido)."""
        self.timer.stop()
        self.rocket = None
        self.sparks = []
        self.hide()

    def _burst(self, x, y):
        """Explosão: solta dezenas de faíscas de uma cor ao acaso."""
        color = random.choice(PALETTE)
        for _ in range(random.randint(34, 46)):
            a = random.uniform(0, math.tau)
            s = random.uniform(90, 230)
            self.sparks.append([x, y, math.cos(a) * s, math.sin(a) * s, 0.0,
                                random.choice([color, random.choice(PALETTE)])])

    def _step(self):
        """Um quadro dos fogos: sobe o foguete, anima as faíscas e para quando acabam."""
        dt = 0.016
        if self.rocket is not None:
            r = self.rocket
            r[0] += 0.0
            r[1] += r[2] * dt
            r[3] += dt
            if r[3] >= ROCKET_TIME:
                self._burst(r[0], r[1])
                self.rocket = None
        for s in self.sparks:
            s[4] += dt
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += GRAVITY * dt
        self.sparks = [s for s in self.sparks if s[4] < LIFE]
        if self.rocket is None and not self.sparks:
            self.timer.stop()
            self.hide()
        self.update()

    def paintEvent(self, _event):
        """Desenha o foguete e as faíscas."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        if self.rocket is not None:
            p.setBrush(QColor("#ffd84d"))
            p.drawEllipse(QPointF(self.rocket[0], self.rocket[1]), 4, 4)
        for x, y, _vx, _vy, t, color in self.sparks:
            c = QColor(color)
            c.setAlphaF(max(0.0, 1.0 - t / LIFE))
            p.setBrush(c)
            p.drawEllipse(QRectF(x - 2.5, y - 2.5, 5, 5))
        p.end()
