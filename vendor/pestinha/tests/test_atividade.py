"""Programas de trabalho: VS Code, Claude e Codex contam como programação."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.sense.senses import detect_activity  # noqa: E402


def test_editores_e_assistentes_sao_programacao():
    for app in ("code.exe", "claude.exe", "codex.exe"):
        assert detect_activity(app, 0.0, 300.0) == "PROGRAMMING"


def test_outro_programa_nao_e_programacao():
    assert detect_activity("discord.exe", 0.0, 300.0) == "SOCIAL"


def test_ocioso_vira_ausente_mesmo_com_editor_aberto():
    assert detect_activity("code.exe", 400.0, 300.0) == "AWAY"
