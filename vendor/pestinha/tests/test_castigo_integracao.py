"""Cantinho do castigo dentro do app: o castigo vence a mesa e as travessuras, e o pânico encerra a fuga."""
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

MOTORES = dict(SENTAR=30.0, CANTO=0, PAPEL=0, TRAVESSURA=0, FUGIR=0, CARTAZ=0, ANGRY=0, WATCH=0)


@pytest.fixture
def preso(monkeypatch):
    QApplication.instance() or QApplication([])
    import pestinha.app as app_mod
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    paths = Paths(root=Path(tempfile.mkdtemp()))
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, travessuras=True))
    b = app_mod.PestinhaApp(store, paths)
    b.castigo.toggle(b.bounds())
    b.castigo.plaquinha.move(0, 500)
    body = b.pet.body
    body.x, body.y, body.grounded = 100, b.bounds()[3] - 40, True
    b.castigo._entrar(time.monotonic(), b.pet_state)
    yield b
    b.castigo.toggle(b.bounds())


def test_preso_nao_senta_no_notebook(preso, monkeypatch):
    monkeypatch.setattr(preso.brain, "motor_activity", lambda: dict(MOTORES))
    preso._atualizar_mesa(time.monotonic())
    assert preso.mesa.sentado is False


def test_preso_nao_apronta(preso):
    preso.conteudo.proprio.mkdir(parents=True, exist_ok=True)
    preso.conteudo.notes.write_text("nota\n", encoding="utf-8")
    preso.memory.choose = Mock(return_value="bilhete")
    preso.mischief_ctl.pedir(time.monotonic())
    preso.maybe_mischief(time.monotonic(), 0.016, preso.bounds(), (0, 0), dict(MOTORES))
    assert preso.behavior.mission is None
    assert not preso.mischief.things


def test_panico_cancela_fuga_em_andamento(preso):
    preso.castigo._iniciar_fuga(time.monotonic(), preso.bounds())
    preso.panic()
    assert preso.castigo.fuga is None
    assert preso.behavior.fuga_alvo is None
