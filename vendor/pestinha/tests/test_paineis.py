"""Painéis do menu (monitor neural e painel de protesto): abrir à mão deve manter o painel na tela."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def pet_app(tmp_path):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS))           # modo teste desligado (padrão)
    app = PestinhaApp(store, paths)
    yield app
    app.floats.hidden_by_tray = True
    for w in list(app.floats.windows.values()):
        w.close()


def test_painel_aberto_no_menu_fica_na_tela_fora_do_modo_teste(pet_app):
    pet_app.floats.open("neural")
    pet_app.floats.sync(pet_app.floats_allowed(), pet_app.floats_base())
    assert pet_app.floats.window("neural").isVisible()


def test_clicar_de_novo_fecha_o_painel(pet_app):
    pet_app.floats.toggle("greve")
    pet_app.floats.toggle("greve")
    pet_app.floats.sync(pet_app.floats_allowed(), pet_app.floats_base())
    assert not pet_app.floats.window("greve").isVisible()


def test_esconder_o_bryan_esconde_o_painel(pet_app):
    pet_app.floats.open("greve")
    pet_app.floats.sync(False, False)
    assert not pet_app.floats.window("greve").isVisible()
