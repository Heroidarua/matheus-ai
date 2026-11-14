"""
Mede se cada frase do cartazes.txt de cada pet cabe na placa em que aparece, com as fontes de verdade.

A placa diminui a letra até o texto caber, mas abaixo de 8 pt fica difícil de ler e abaixo de 7 pt
o texto corta. Rode no Windows (não no modo offscreen, que não tem fontes):

    python ferramentas/medir_cartazes.py            todos os pets
    python ferramentas/medir_cartazes.py jorge      só um
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontMetrics, QGuiApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.core.protesto import load_signs  # noqa: E402
from pestinha.paths import Paths  # noqa: E402

# seção -> (largura, altura, letra inicial) da placa onde ela aparece (world/cartazes.py)
PLACA = {
    "reclamacao": (116, 48, 10), "manifestacao": (150, 58, 12), "greve": (132, 54, 12),
    "acordo": (150, 54, 12), "desistiu": (150, 54, 12), "volto": (150, 54, 12),
    "saudade": (116, 48, 12), "chorando": (116, 48, 12), "abandonado": (116, 48, 12),
    "castigo": (190, 86, 13), "xingamento": (190, 86, 13),
    "revolucao": (190, 106, 13),                      # a bandeira, na menor escala
}
LEGIVEL = 8


def tamanho_que_cabe(texto, largura, altura, inicial):
    """A letra que a placa usaria e se o texto cabe nela."""
    area = QRectF(0, 0, largura, altura).adjusted(6, 4, -6, -4).toRect()
    flags = Qt.AlignCenter | Qt.TextWordWrap
    size = inicial
    while size > 6 and QFontMetrics(QFont("Arial Black", size)).boundingRect(area, flags, texto).height() > area.height():
        size -= 1
    size = max(7, size)
    return size, QFontMetrics(QFont("Arial Black", size)).boundingRect(area, flags, texto).height() <= area.height()


def medir(pet_id, paths=None):
    paths = paths or Paths(root=RAIZ)
    problemas = []
    for secao, textos in load_signs(paths.conteudo(pet_id).signs).items():
        largura, altura, inicial = PLACA[secao]
        for texto in textos:
            size, cabe = tamanho_que_cabe(texto, largura, altura, inicial)
            if not cabe or size < LEGIVEL:
                problemas.append((secao, texto, size, "corta" if not cabe else "letra pequena"))
    return problemas


if __name__ == "__main__":
    QGuiApplication(sys.argv[:1])
    paths = Paths(root=RAIZ)
    total = 0
    for pet in sys.argv[1:] or config.list_pets(paths):
        problemas = medir(pet, paths)
        total += len(problemas)
        print(f"{pet}: {'tudo cabe' if not problemas else f'{len(problemas)} frase(s) apertada(s)'}")
        for secao, texto, size, motivo in problemas:
            print(f"   [{secao}] {texto!r}: {size} pt, {motivo}")
    sys.exit(1 if total else 0)
