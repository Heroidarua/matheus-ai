"""Fogos de artifício ligados à rede e brincadeira mais animada quando feliz. Rodar: python -m pytest tests -q"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.world.fireworks import Fireworks  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_fogo_sobe_e_explode(qapp):
    f = Fireworks()
    f.launch(400, 400)
    assert f.rocket is not None and f.isVisible()
    for _ in range(80):                       # ~1,3 s: o foguete já explodiu
        f._step()
    assert f.rocket is None
    assert len(f.sparks) > 0
    for _ in range(200):                      # depois de LIFE s, tudo some e a janela esconde
        f._step()
    assert f.sparks == [] and not f.isVisible()
    f.close()


def test_fogo_so_quando_euforia_cheia_e_feliz(tmp_path):
    from pestinha.mind.festa import FestaController

    class Corpo:
        x, y = 100.0, 100.0

    festa = FestaController(lambda: False)
    try:
        for i in range(60):                     # alegria forte: CHEER bem acima do repouso
            festa.tick(100.0 + i * 0.1, {"CHEER": 12.0}, "feliz", Corpo(), True)
        assert festa.pronto_em > 100.0          # soltou um fogo e entrou em espera
        before = festa.pronto_em
        for i in range(60):                     # sem alegria e sem feliz, não solta
            festa.tick(200.0 + i * 0.1, {"CHEER": 0.0}, "contente", Corpo(), True)
        assert festa.pronto_em == before
    finally:
        festa.fechar()
