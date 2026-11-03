"""
Desenha pets/jorge/bolinha_papel.png: um panfleto de mentoria amassado, que o Jorge atira na revolução.

Desenho feito por código (sem imagem de terceiros). Rode de novo para refazer o arquivo.
"""
import math
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen  # noqa: E402

LADO = 360
DESTINO = Path(__file__).resolve().parent.parent / "pets" / "jorge" / "bolinha_papel.png"


def contorno_amassado(rng, centro, raio, pontas=30):
    """Um círculo de bordas quebradas, como papel amassado."""
    caminho = QPainterPath()
    for i in range(pontas):
        angulo = 2 * math.pi * i / pontas
        r = raio * rng.uniform(0.92, 1.0)
        ponto = QPointF(centro + r * math.cos(angulo), centro + r * math.sin(angulo))
        caminho.moveTo(ponto) if i == 0 else caminho.lineTo(ponto)
    caminho.closeSubpath()
    return caminho


def desenhar(destino=DESTINO, semente=11):
    QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    rng = random.Random(semente)
    img = QImage(LADO, LADO, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    centro, raio = LADO / 2, LADO * 0.46
    papel = contorno_amassado(rng, centro, raio)

    p.setPen(QPen(QColor("#8a7a3c"), 6))
    p.setBrush(QColor("#fff6c2"))                       # papel de panfleto, amarelinho
    p.drawPath(papel)

    p.save()
    p.setClipPath(papel)
    p.setPen(QPen(QColor(150, 130, 60, 110), 4))        # vincos do amassado
    for _ in range(9):
        a, b = rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi)
        p.drawLine(QPointF(centro + raio * math.cos(a), centro + raio * math.sin(a)),
                   QPointF(centro + raio * 0.3 * math.cos(b), centro + raio * 0.3 * math.sin(b)))
    p.translate(centro, centro)                          # o "$" e as linhas de texto, meio tortos
    p.rotate(-14)
    cifrao = QPainterPath()                              # desenhado em traço: não depende de fonte
    cifrao.moveTo(55, -95)
    cifrao.cubicTo(20, -130, -70, -120, -65, -65)
    cifrao.cubicTo(-60, -20, 60, -25, 62, 25)
    cifrao.cubicTo(65, 80, -30, 90, -65, 50)
    p.setPen(QPen(QColor("#1f8a3b"), 26, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(cifrao)
    p.drawLine(QPointF(0, -140), QPointF(0, 115))
    p.setPen(QPen(QColor("#b3261e"), 9, Qt.SolidLine, Qt.RoundCap))
    for y, largura in ((128, 150), (146, 110)):          # "MENTORIA" e o letreiro miúdo
        p.drawLine(QPointF(-largura / 2, y), QPointF(largura / 2, y))
    p.restore()
    p.end()

    destino.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(destino)):
        raise OSError(f"não deu para salvar {destino}")
    return destino


if __name__ == "__main__":
    print(f"panfleto salvo em {desenhar()}")
