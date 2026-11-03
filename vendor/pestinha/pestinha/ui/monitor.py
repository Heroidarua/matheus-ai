"""
NEURAL MONITOR - o que a rede está fazendo agora, sincronizado com o corpo.

    esquerda   raster de todos os neurônios (últimos 3 s, colunas de 10 ms),
               agrupados por população: sensores, interneurônios, motores
    direita    entrada de cada canal + eficácia sináptica (habituação),
               atividade de cada motor e o parâmetro do corpo que ela controla,
               emoção, homeostase e a resposta da última cutucada

Abre pela bandeja ("Monitor neural"). Só grava o raster enquanto está aberto.
"""

import numpy as np
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from ..world.arrastavel import FloatingWidget

from ..config import EMOTION_NAMES
from .rotulos import nome_canal
from ..core.protesto import STAGE_NAMES

BG = QColor("#0d110f")
PANEL = QColor("#141b16")
TEXT = QColor("#dcebe0")
MUTED = QColor("#7f9886")
GRID = QColor("#24332a")
INPUT = QColor("#4fb3ff")
EFFICACY = QColor("#ffb347")
MOTOR = QColor("#ffd84d")
GOOD = QColor("#5fe07a")

# cor do disparo por tipo: 0 sensor, 1 excitatório, 2 inibitório, 3 motor
KIND_RGB = {0: (79, 179, 255), 1: (95, 224, 122), 2: (255, 140, 90), 3: (255, 216, 77)}

MOTOR_EFFECT = {
    "WANDER": "velocidade, passeios",
    "WATCH": "fixa o cursor",
    "CHEER": "pulinhos, giros",
    "STARTLE": "pulo de susto",
    "DROWSE": "lentidão, pálpebras",
    "ANGRY": "tremor",
    "SAD": "menos exploração",
    "SETTLE": "balanço",
}


class NeuralMonitor(FloatingWidget):
    """Janela de diagnóstico: mostra os disparos da rede, a atividade dos motores e as necessidades do pet em tempo real."""
    def __init__(self, app, default_pos):
        """Cria a janela do monitor e um relógio para redesenhar."""
        super().__init__(app, "neural", f"{app.nome} · Monitor neural", (1180, 700), (980, 620), default_pos)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(100)

    def showEvent(self, event):
        """Ao abrir, a rede passa a gravar os disparos para o desenho."""
        super().showEvent(event)
        self.app.brain.recording = True

    def hideEvent(self, event):
        """Ao fechar, a rede para de gravar e apaga o histórico de disparos (economiza memória)."""
        self.app.brain.recording = False
        self.app.brain.raster.clear()
        super().hideEvent(event)

    # ---------------- desenho ----------------

    def paintEvent(self, _event):
        """Desenha o monitor inteiro: raster, barras e painéis."""
        p = QPainter(self)
        p.fillRect(self.rect(), BG)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        split = int(w * 0.52)
        self._raster(p, QRectF(16, 16, split - 24, h - 32))
        self._panel(p, QRectF(split + 8, 16, w - split - 24, h - 32))
        p.end()

    def _title(self, p, x, y, text):
        """Escreve um título de seção no monitor."""
        p.setPen(MUTED)
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(int(x), int(y), text.upper())

    def _raster(self, p, area):
        """Desenha o raster dos disparos dos últimos 3 segundos (uma coluna = 10 ms)."""
        brain = self.app.brain
        self._title(p, area.left(), area.top() + 10, "Disparos · últimos 3 s · 1 coluna = 10 ms")
        label_w = 92
        box = QRectF(area.left() + label_w, area.top() + 20, area.width() - label_w, area.height() - 40)
        p.fillRect(box, PANEL)

        bins = list(brain.raster)
        if bins:
            fired = np.stack(bins, axis=1)                  # N x T
            T = fired.shape[1]
            rgb = np.zeros((brain.N, T, 3), dtype=np.uint8)
            rgb[:] = (20, 27, 22)
            for kind, color in KIND_RGB.items():
                rows = brain.kind == kind
                rgb[rows] = np.where(fired[rows][..., None], np.array(color, dtype=np.uint8), rgb[rows])
            data = np.ascontiguousarray(rgb)
            img = QImage(data.data, T, brain.N, 3 * T, QImage.Format_RGB888)
            # ancorado à direita: o "agora" fica sempre na borda direita
            width = box.width() * T / brain.raster.maxlen
            target = QRectF(box.right() - width, box.top(), width, box.height())
            p.drawImage(target, img)

        # nomes e divisões das populações
        p.setFont(QFont("Consolas", 7))
        row_h = box.height() / brain.N
        for pool in brain.pools:
            y0 = box.top() + pool["start"] * row_h
            y1 = y0 + pool["n"] * row_h
            p.setPen(GRID)
            p.drawLine(int(box.left()), int(y0), int(box.right()), int(y0))
            if pool["n"] * row_h >= 7:
                color = {"sensory": INPUT, "motor": MOTOR}.get(pool["group"], TEXT)
                p.setPen(color)
                p.drawText(QRectF(area.left(), y0, label_w - 6, y1 - y0), Qt.AlignRight | Qt.AlignVCenter, nome_canal(pool["name"]))
        p.setPen(MUTED)
        p.drawText(QRectF(box.left(), box.bottom() + 4, box.width(), 14), Qt.AlignLeft, "−3 s")
        p.drawText(QRectF(box.left(), box.bottom() + 4, box.width(), 14), Qt.AlignRight, "agora")

    def _bar(self, p, x, y, w, value, color, h=6):
        """Desenha uma barra de 0 a 1 (cheia = 1)."""
        p.fillRect(QRectF(x, y, w, h), GRID)
        p.fillRect(QRectF(x, y, w * max(0.0, min(1.0, value)), h), color)

    def _panel(self, p, area):
        """Desenha o painel de motores e necessidades, com as barras e o comportamento atual."""
        app = self.app
        brain = app.brain
        x, y, w = area.left(), area.top(), area.width()
        mono = QFont("Consolas", 8)

        # ---- entradas e habituação ----
        self._title(p, x, y + 10, "Entrada (azul) · eficácia sináptica / habituação (laranja)")
        y += 20
        eff = brain.efficacy()
        names = brain.sensory_names
        col_w = (w - 12) / 2
        for i, name in enumerate(names):
            cx = x + (i % 2) * (col_w + 12)
            cy = y + (i // 2) * 22
            p.setFont(mono)
            p.setPen(TEXT)
            p.drawText(QRectF(cx, cy, 64, 12), Qt.AlignLeft | Qt.AlignVCenter, nome_canal(name))
            bx = cx + 66
            bw = col_w - 66 - 34
            self._bar(p, bx, cy + 1, bw, app.intensities.get(name, 0.0), INPUT, 5)
            self._bar(p, bx, cy + 8, bw, eff[name], EFFICACY, 3)
            p.setPen(MUTED)
            p.drawText(QRectF(bx + bw + 2, cy, 32, 12), Qt.AlignRight | Qt.AlignVCenter, f"{eff[name]:.2f}")
        y += ((len(names) + 1) // 2) * 22 + 10

        # ---- motores -> corpo ----
        self._title(p, x, y + 10, "Motores → o que controlam no corpo")
        y += 20
        motor = brain.motor_activity()
        tone = app.behavior.tone
        for m in tone.r:
            p.setFont(mono)
            p.setPen(MOTOR)
            p.drawText(QRectF(x, y, 62, 14), Qt.AlignLeft | Qt.AlignVCenter, nome_canal(m))
            self._bar(p, x + 64, y + 4, w * 0.36, tone.r[m], MOTOR)
            p.setPen(TEXT)
            p.drawText(QRectF(x + 70 + w * 0.36, y, 60, 14), Qt.AlignLeft | Qt.AlignVCenter, f"{motor[m]:5.1f} Hz")
            p.setPen(MUTED)
            p.drawText(QRectF(x + 130 + w * 0.36, y, w, 14), Qt.AlignLeft | Qt.AlignVCenter, MOTOR_EFFECT[m])
            y += 17
        y += 4
        p.setPen(TEXT)
        p.drawText(QRectF(x, y, w, 14), Qt.AlignLeft,
                   f"velocidade {tone.speed():3.0f} px/s · pulinho {tone.hop_chance():.0%} · "
                   f"altura {tone.hop_power():3.0f} · tremor {tone.shake():.1f} px")
        y += 15
        p.drawText(QRectF(x, y, w, 14), Qt.AlignLeft,
                   f"balanço {tone.sway():.1f}° · pálpebra +{tone.lid_droop():.2f} · "
                   f"fixa cursor {tone.watch():.0%} · sobe janela {tone.climb_chance():.0%}")
        y += 26

        # ---- estado ----
        self._title(p, x, y, "Estado")
        y += 10
        emo = app.emotion
        p.setFont(QFont("Consolas", 11, QFont.Bold))
        p.setPen(GOOD)
        p.drawText(QRectF(x, y, w, 18), Qt.AlignLeft, EMOTION_NAMES.get(app.pet_state.emotion, app.pet_state.emotion))
        p.setFont(mono)
        p.setPen(TEXT)
        p.drawText(QRectF(x + 140, y + 3, w, 16), Qt.AlignLeft,
                   f"valência {emo.valence:+.2f} · ativação {emo.arousal:+.2f}")
        y += 24
        d = app.drives
        for label, value in (("energia", d.energy), ("estimulação", d.stimulation), ("carência", d.contact)):
            p.setPen(TEXT)
            p.drawText(QRectF(x, y, 90, 12), Qt.AlignLeft | Qt.AlignVCenter, label)
            self._bar(p, x + 92, y + 3, w * 0.4, value, GOOD)
            p.drawText(QRectF(x + 98 + w * 0.4, y, 50, 12), Qt.AlignLeft | Qt.AlignVCenter, f"{value:.2f}")
            y += 16
        y += 6
        pr = app.protest
        p.drawText(QRectF(x, y, w, 14), Qt.AlignLeft,
                   f"insatisfação {pr.grievance:.2f} · protesto: {STAGE_NAMES[pr.stage]} · revoluções {pr.revolutions}")
        y += 16
        poke = app.last_poke_response
        poke_text = "—" if poke is None else f"{poke:.2f}"
        p.drawText(QRectF(x, y, w, 14), Qt.AlignLeft,
                   f"última cutucada: resposta {poke_text} · eficácia da cutucada {eff['POKE']:.2f}"
                   + ("   · DORMINDO" if app.asleep else ""))
