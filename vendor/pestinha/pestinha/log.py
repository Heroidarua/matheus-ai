"""
LOG - um lugar só para mensagens do app: terminal e arquivo em memory/logs/.

O arquivo é aparado quando passa de 1 MB (fica com a metade mais recente).
Se o arquivo não puder ser escrito, a mensagem vai só para o terminal.
"""

import datetime
import os
from pathlib import Path

MAX_BYTES = 1_000_000
_file = None


def setup(path):
    """Escolhe o arquivo do log (criado sob demanda)."""
    global _file
    _file = Path(path)


def desligar_arquivo():
    """Para de gravar em arquivo (usado ao apagar os dados: nada pode recriar a pasta)."""
    global _file
    _file = None


def _trim():
    """Corta o início do log quando ele passa do limite, para não crescer sem fim."""
    try:
        if _file.exists() and _file.stat().st_size > MAX_BYTES:
            lines = _file.read_text(encoding="utf-8", errors="replace").splitlines()
            _file.write_text("\n".join(lines[len(lines) // 2:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def log(*parts):
    """Escreve uma mensagem no terminal e no arquivo do log (uma linha por chamada)."""
    text = " ".join(str(p) for p in parts)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    if _file is None:
        return
    try:
        _file.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        with open(_file, "a", encoding="utf-8") as f:
            f.write(f"{stamp} {text}{os.linesep}")
        _trim()
    except OSError:
        pass
