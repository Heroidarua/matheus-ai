"""
STORE - a única forma de gravar e ler arquivos de estado.

Escrita atômica (arquivo temporário + troca), leitura tolerante (arquivo
ausente ou corrompido vira o valor padrão, sem derrubar o app) e uma linha
por registro para os históricos. Todos os módulos usam isto.
"""

import json
import os
from pathlib import Path


def write_json(path, data, indent=None):
    """Grava um JSON de forma atômica (arquivo temporário e troca), recusando NaN e infinito."""
    path = Path(path)
    texto = json.dumps(data, ensure_ascii=False, indent=indent, allow_nan=False)   # erro antes de tocar no arquivo
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, path)


def _sem_nan(valor):
    """Recusa NaN e infinito ao gravar ou ler JSON."""
    raise ValueError(f"constante não permitida no JSON: {valor}")


def read_json(path, default=None):
    """Lê um JSON; se o arquivo não existir ou estiver corrompido, devolve `default` (e guarda o arquivo ruim como .corrompido)."""
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.loads(f.read(), parse_constant=_sem_nan)
    except OSError:
        return default
    except ValueError:
        # arquivo existe mas está ilegível: guarda uma cópia para não perder de vez
        try:
            os.replace(path, path.with_name(path.name + ".corrompido"))
        except OSError:
            pass
        return default


def append_line(path, line):
    """Acrescenta uma linha no fim de um arquivo de texto (cria a pasta se preciso)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(line.rstrip("\n") + "\n")


def read_lines(path):
    """Lê as linhas de um arquivo de texto (tolerante a caracteres ruins); vazio se não existir."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def write_lines(path, lines):
    """Grava uma lista de linhas em um arquivo de texto."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line.rstrip("\n") + "\n")
    os.replace(tmp, path)
