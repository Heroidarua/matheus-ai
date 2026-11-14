"""
Linux (X11): xdotool e wmctrl para as janelas, xprintidle para o tempo ocioso, e pynput para o atalho.

Em Wayland a maior parte dessas leituras não existe: o pet continua andando, mas não enxerga as janelas
nem o tempo ocioso (fica como se você estivesse sempre ativo). Os comandos são opcionais; se faltarem,
a leitura correspondente vira o valor padrão.
"""

import os

import psutil

from ._comum import atalho_pynput, rodar

LARGURA_MINIMA, ALTURA_MINIMA = 120, 60


def parse_geometria(texto):
    """Retângulo (l, t, r, b) a partir de `xdotool getwindowgeometry --shell` (linhas CHAVE=valor)."""
    campos = {}
    for linha in (texto or "").splitlines():
        if "=" in linha:
            chave, valor = linha.split("=", 1)
            campos[chave.strip()] = valor.strip()
    try:
        x, y = int(campos["X"]), int(campos["Y"])
        return (x, y, x + int(campos["WIDTH"]), y + int(campos["HEIGHT"]))
    except (KeyError, ValueError):
        return None


def parse_wmctrl(texto, meu_pid, excluir):
    """[(id, (l, t, r, b), False)] de `wmctrl -lGp`: id desktop pid x y largura altura host título."""
    achadas = []
    for linha in (texto or "").splitlines():
        partes = linha.split(None, 8)
        if len(partes) < 8:
            continue
        try:
            janela_id, pid = int(partes[0], 16), int(partes[2])
            x, y, largura, altura = (int(v) for v in partes[3:7])
        except ValueError:
            continue
        if pid == meu_pid or janela_id in excluir or largura < LARGURA_MINIMA or altura < ALTURA_MINIMA:
            continue
        achadas.append((janela_id, (x, y, x + largura, y + altura), False))
    return achadas


def _janela_ativa():
    """Id da janela ativa no X11 (via xdotool), ou None."""
    return (rodar(["xdotool", "getactivewindow"]) or "").strip() or None


def _tela():
    """Tamanho da tela principal (via xdotool), como (0, 0, largura, altura), ou None."""
    texto = (rodar(["xdotool", "getdisplaygeometry"]) or "").split()
    if len(texto) == 2 and all(v.isdigit() for v in texto):
        return (0, 0, int(texto[0]), int(texto[1]))
    return None


def ocioso_segundos():
    """Tempo ocioso pelo xprintidle (X11). Em Wayland ou sem o comando, devolve 0 (sempre ativo)."""
    texto = (rodar(["xprintidle"]) or "").strip()
    return int(texto) / 1000.0 if texto.isdigit() else 0.0


def processo_ativo():
    """Nome do programa da janela ativa, pegando o pid pelo xdotool e o nome pelo psutil."""
    janela = _janela_ativa()
    pid = (rodar(["xdotool", "getwindowpid", janela]) or "").strip() if janela else ""
    try:
        return psutil.Process(int(pid)).name().lower()
    except (ValueError, psutil.Error):
        return "unknown"


def retangulo_ativo(escala=1.0):
    """Retângulo da janela ativa (pixels), ou None se não houver janela ativa."""
    janela = _janela_ativa()
    if janela is None:
        return None
    return parse_geometria(rodar(["xdotool", "getwindowgeometry", "--shell", janela]))


def tela_cheia():
    """Diz se a janela ativa cobre a tela inteira."""
    rect, tela = retangulo_ativo(), _tela()
    if rect is None or tela is None:
        return False
    return rect[0] <= tela[0] and rect[1] <= tela[1] and rect[2] >= tela[2] and rect[3] >= tela[3]


def janelas_visiveis(excluir, escala=1.0):
    """Janelas visíveis de outros programas pelo wmctrl (sem as do próprio pet)."""
    return parse_wmctrl(rodar(["wmctrl", "-lGp"]), os.getpid(), excluir)


def sem_foco_nativo(janela_id):
    """O X11 não tem um jeito padrão de pedir isso: a janela do pet usa só as flags do Qt."""


def iniciar_atalho(callback):
    """Registra Ctrl+Alt+Shift+B pelo pynput; devolve True se conseguiu."""
    return atalho_pynput(callback)
