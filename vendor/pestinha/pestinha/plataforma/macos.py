"""
macOS: Quartz (pyobjc) para as janelas e o tempo ocioso; AppKit para o programa em primeiro plano.

Sem pyobjc, o tempo ocioso sai do ioreg. O atalho global usa pynput, e o macOS pede permissão de
Acessibilidade na primeira vez. Os retângulos saem em pixels físicos (pontos x escala).
"""

import os
import re
import threading

from ._comum import rodar
from PySide6.QtWidgets import QApplication
from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import (
    kVK_ANSI_B,
    controlKey,
    optionKey,
    shiftKey,
)

LARGURA_MINIMA, ALTURA_MINIMA = 120, 60
OPCOES_NA_TELA = (1 << 0) | (1 << 4)        # OnScreenOnly | ExcludeDesktopElements
JANELA_NULA = 0
_hotkey = None

def _quartz():
    """Carrega o módulo Quartz (pyobjc); devolve None se não estiver instalado."""
    try:
        import Quartz
        return Quartz
    except Exception:
        return None


def _programa_da_frente():
    """Programa em primeiro plano (objeto do AppKit), ou None se não der para ler."""
    try:
        from AppKit import NSWorkspace
        return NSWorkspace.sharedWorkspace().frontmostApplication()
    except Exception:
        return None


def ocioso_do_ioreg(texto):
    """Segundos desde a última entrada, a partir da saída de `ioreg -c IOHIDSystem`."""
    achado = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', texto)
    return int(achado.group(1)) / 1e9 if achado else 0.0


def ocioso_segundos():
    """Tempo ocioso pelo Quartz, ou pelo ioreg se o pyobjc não estiver instalado."""
    quartz = _quartz()
    if quartz is not None:
        try:
            return float(quartz.CGEventSourceSecondsSinceLastEventType(
                quartz.kCGEventSourceStateCombinedSessionState, quartz.kCGAnyInputEventType))
        except Exception:
            pass
    return ocioso_do_ioreg(rodar(["ioreg", "-c", "IOHIDSystem", "-d", "4"]) or "")


def processo_ativo():
    """Nome do programa em primeiro plano, em minúsculo."""
    app = _programa_da_frente()
    nome = app.localizedName() if app is not None else None
    return str(nome).lower() if nome else "unknown"


def _rect_de(bounds):
    """Converte o retângulo do Quartz (X, Y, largura, altura) em (esquerda, topo, direita, base)."""
    return (bounds["X"], bounds["Y"], bounds["X"] + bounds["Width"], bounds["Y"] + bounds["Height"])


def _grande_o_bastante(rect):
    """Diz se a janela é grande o bastante para ser 'de verdade' (descarta menus e balõezinhos)."""
    return rect[2] - rect[0] >= LARGURA_MINIMA and rect[3] - rect[1] >= ALTURA_MINIMA


def _escalar(rect, escala):
    """Multiplica o retângulo pela escala da tela (pontos para pixels físicos)."""
    return tuple(valor * escala for valor in rect)


def janela_da_frente(janelas, pid):
    """Retângulo (em pontos) da janela de maior z do programa `pid`. `janelas` vem de cima para baixo."""
    for janela in janelas:
        if janela.get("kCGWindowOwnerPID") != pid or janela.get("kCGWindowLayer", 1) != 0:
            continue
        rect = _rect_de(janela["kCGWindowBounds"])
        if _grande_o_bastante(rect):
            return rect
    return None


def janelas_de(janelas, meu_pid, excluir, escala):
    """[(id, (l, t, r, b) físicos, maximizada)] das janelas de outros programas, de cima para baixo."""
    achadas = []
    for janela in janelas:
        if janela.get("kCGWindowLayer") != 0 or janela.get("kCGWindowOwnerPID") == meu_pid:
            continue
        rect = _rect_de(janela["kCGWindowBounds"])
        janela_id = janela.get("kCGWindowNumber")
        if not _grande_o_bastante(rect) or janela_id in excluir:
            continue
        achadas.append((janela_id, _escalar(rect, escala), False))
    return achadas


def _cobre(rect, tela):
    """Diz se o retângulo `rect` cobre a tela inteira `tela`."""
    return rect[0] <= tela[0] and rect[1] <= tela[1] and rect[2] >= tela[2] and rect[3] >= tela[3]


def _listar(quartz):
    """Lista as janelas na tela, de cima para baixo, pelo Quartz."""
    return list(quartz.CGWindowListCopyWindowInfo(OPCOES_NA_TELA, JANELA_NULA) or [])


def retangulo_ativo(escala=1.0):
    """Retângulo da janela em primeiro plano do programa ativo (em pixels físicos), ou None."""
    quartz, app = _quartz(), _programa_da_frente()
    if quartz is None or app is None:
        return None
    rect = janela_da_frente(_listar(quartz), app.processIdentifier())
    return _escalar(rect, escala) if rect else None


def tela_cheia():
    """Diz se a janela em primeiro plano cobre a tela principal inteira."""
    quartz = _quartz()
    rect = retangulo_ativo(1.0)
    if quartz is None or rect is None:
        return False
    tela = quartz.CGDisplayBounds(quartz.CGMainDisplayID())
    return _cobre(rect, (tela.origin.x, tela.origin.y, tela.origin.x + tela.size.width,
                         tela.origin.y + tela.size.height))


def janelas_visiveis(excluir, escala=1.0):
    """Janelas visíveis de outros programas, de cima para baixo (sem as do próprio pet)."""
    quartz = _quartz()
    if quartz is None:
        return []
    return janelas_de(_listar(quartz), os.getpid(), excluir, escala)


def sem_foco_nativo(janela_id):
    """No macOS o pet já é uma janela sem foco (Qt.WA_ShowWithoutActivating); nada a fazer aqui."""


def iniciar_atalho(callback):
    """Registra Ctrl+Alt+Shift+B pelo QuickMacHotKey; devolve True se conseguiu."""
    global _hotkey

    if _hotkey is not None:
        return True

    if threading.current_thread() is not threading.main_thread() or (
        app := QApplication.instance()
    ) is None:
        return False

    try:
        _hotkey = quickHotKey(
            virtualKey=kVK_ANSI_B,
            modifierMask=mask(controlKey, optionKey, shiftKey),
        )(lambda: callback())

        app.aboutToQuit.connect(_hotkey.unregister)
        return True

    except Exception:
        return False
