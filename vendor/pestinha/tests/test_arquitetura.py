"""
Regra de camadas do pacote `pestinha`: cada camada só importa das que estão abaixo dela.

    core  <  sense  <  body  <  world  <  mind  <  ui  <  controle  <  app

Módulos compartilhados (ajustes, config, store, log, mathutil, paths, settings_store) podem ser
usados por todas. `core/` é puro: sem Qt e sem Windows, para ser testável em qualquer lugar.
"""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "pestinha"
ORDEM = ["core", "sense", "body", "world", "mind", "ui", "controle", "app"]
COMPARTILHADOS = {"ajustes", "config", "store", "log", "mathutil", "paths", "settings_store", "__init__",
                  "plataforma"}


def camada_de(partes):
    """('bryan', 'world', 'notebook') -> 'world'; ('bryan', 'app') -> 'app'."""
    return partes[1] if len(partes) > 2 else partes[1]


def importacoes(arquivo):
    rel = arquivo.relative_to(RAIZ.parent).with_suffix("").parts
    pacote = rel[:-1]
    for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
        if isinstance(no, ast.ImportFrom) and no.level:
            base = list(pacote[: len(pacote) - no.level + 1])
            alvo = base + (no.module.split(".") if no.module else [a.name for a in no.names][:1])
            yield rel, tuple(alvo), no.lineno
        elif isinstance(no, (ast.Import, ast.ImportFrom)):
            nome = no.module if isinstance(no, ast.ImportFrom) else no.names[0].name
            yield rel, ("externo", nome or ""), no.lineno


def test_camadas_so_importam_de_baixo():
    violacoes = []
    for arquivo in RAIZ.rglob("*.py"):
        for origem, alvo, linha in importacoes(arquivo):
            if alvo[0] == "externo":
                continue
            de, para = camada_de(origem), alvo[1] if len(alvo) > 1 else alvo[0]
            if para in COMPARTILHADOS or de in COMPARTILHADOS or de == para:
                continue
            if de in ORDEM and para in ORDEM and ORDEM.index(para) > ORDEM.index(de):
                violacoes.append(f"{'/'.join(origem)}.py:{linha} ({de} importa {para})")
    assert violacoes == []


def test_core_e_puro():
    impuros = []
    for arquivo in (RAIZ / "core").rglob("*.py"):
        for origem, alvo, linha in importacoes(arquivo):
            if alvo[0] == "externo" and alvo[1].split(".")[0] in ("PySide6", "win32gui", "win32api", "win32con",
                                                                     "win32process", "pywintypes", "ctypes"):
                impuros.append(f"{'/'.join(origem)}.py:{linha} ({alvo[1]})")
    assert impuros == []
