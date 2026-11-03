"""Cantinho no app inteiro, com relógio virtual: soltar no ar, pousar, ficar preso e reagir pela rede."""
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
from pestinha.mind.castigo_ctl import CARTAZ_MIN_S  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def mundo(monkeypatch):
    qt = QApplication.instance() or QApplication([])
    import pestinha.app as app_mod
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    monkeypatch.setattr(app_mod.senses, "list_windows", lambda exclude, *args, **kwargs: [])
    monkeypatch.setattr(app_mod.senses, "get_active_app", lambda: "explorer.exe")
    monkeypatch.setattr(app_mod.senses, "get_idle_seconds", lambda: 1.0)
    monkeypatch.setattr(app_mod.senses, "is_fullscreen", lambda: False)
    relogio = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])
    paths = Paths(root=Path(tempfile.mkdtemp()))
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS))
    b = app_mod.PestinhaApp(store, paths)
    for timer in b.findChildren(app_mod.QTimer):
        timer.stop()
    b.castigo.toggle(b.bounds())

    def rodar(segundos, cada_passo=None):
        for _ in range(int(segundos / 0.1)):
            relogio[0] += 0.1
            if cada_passo:
                cada_passo(b)
            b.think()
            b.frame()
            qt.processEvents()

    def soltar_sobre_a_placa():
        g = b.castigo.plaquinha.geometry()
        body = b.pet.body
        body.held, body.x, body.y = True, g.center().x(), g.y() - 150
        rodar(0.1)
        body.held = False
        rodar(3.0)                                   # cai, pousa e entra

    return SimpleNamespace(b=b, rodar=rodar, soltar=soltar_sobre_a_placa)


def test_soltar_no_ar_sobre_a_placa_fica_preso(mundo):
    mundo.soltar()
    assert mundo.b.castigo.dentro
    mundo.rodar(10.0)                                # sem tédio nem memória de fuga: continua preso
    assert mundo.b.castigo.dentro and mundo.b.pet_state.castigo


def test_preso_abaixa_cartaz_de_protesto(mundo):
    b = mundo.b
    b.protest.stage = 2
    b.protest.respawn_at = time.monotonic()
    mundo.rodar(0.3)
    assert b.protest.sign is not None              # protestando, segura o cartaz
    mundo.soltar()
    mundo.rodar(1.0)
    assert b.castigo.dentro and b.protest.sign is None


def test_cartaz_do_castigo_e_xingamento_quando_bravo(mundo):
    b = mundo.b
    mundo.soltar()
    for _ in range(20):
        b.castigo._decidir(time.monotonic(), 1.0, b.pet.body, b.bounds(), {"CARTAZ": 100.0, "ANGRY": 50.0})
        assert b.castigo.cartaz.text in b.castigo.cartazes + b.castigo.xingamentos
    textos = set()
    agora = time.monotonic()
    for _ in range(40):                              # o relógio anda: cada volta pode trocar o cartaz
        agora += CARTAZ_MIN_S + 0.1
        b.castigo._decidir(agora, 1.0, b.pet.body, b.bounds(), {"CARTAZ": 100.0, "ANGRY": 50.0})
        textos.add(b.castigo.cartaz.text)
    assert textos & set(b.castigo.xingamentos)


def test_pico_de_fuga_nao_basta_mas_vontade_sustentada_foge(mundo):
    b = mundo.b
    mundo.soltar()
    b.castigo._decidir(time.monotonic(), 0.1, b.pet.body, b.bounds(), {"FUGIR": 30.0})
    assert b.castigo.dentro                           # um pico não solta
    for _ in range(400):                             # ~25 s de vontade sustentada enchem a carga
        b.castigo._decidir(time.monotonic(), 0.1, b.pet.body, b.bounds(), {"FUGIR": 15.0})
        if not b.castigo.dentro:
            break
    assert not b.castigo.dentro and b.castigo.fuga is not None


def test_memoria_de_fuga_faz_fugir_depois_de_um_tempo(mundo):
    b = mundo.b
    b.castigo.vitorias["fugir"] = 5.0                 # LEMBRA_FUGA cheio
    mundo.soltar()
    assert b.castigo.dentro
    mundo.rodar(60.0)
    assert not b.castigo.dentro and b.castigo.vitorias["fugir"] >= 5.0


def test_carinho_no_canto_leva_ao_perdao(mundo):
    b = mundo.b
    mundo.soltar()
    assert b.castigo.dentro
    mundo.rodar(30.0, cada_passo=lambda app: app.pet_state.mark_caress())
    assert not b.castigo.dentro and b.castigo.vitorias["fugir"] == 0.0


def test_rancor_cresce_enquanto_preso(mundo):
    mundo.soltar()
    mundo.rodar(30.0)
    assert mundo.b.castigo.rancor > 0.1


def test_bravo_fica_preso_mais_de_20_segundos(mundo):
    b = mundo.b
    mundo.soltar()

    def revolta(app):
        app.protest.grievance, app.protest.stage = 1.3, 4

    mundo.rodar(20.0, cada_passo=revolta)
    assert b.castigo.dentro


def test_cartaz_fica_pelo_menos_8_segundos(mundo):
    b = mundo.b
    mundo.soltar()
    b.castigo._decidir(time.monotonic(), 1.0, b.pet.body, b.bounds(), {"CARTAZ": 100.0})
    primeiro = b.castigo.cartaz
    b.castigo._decidir(time.monotonic() + 3, 1.0, b.pet.body, b.bounds(), {"CARTAZ": 100.0})
    assert b.castigo.cartaz is primeiro


def test_aviso_da_placa_some_longe_dela(mundo):
    b = mundo.b
    g = b.castigo.plaquinha.geometry()
    perto = SimpleNamespace(x=g.center().x(), y=g.center().y())
    longe = SimpleNamespace(x=g.center().x() + 2000, y=g.center().y())
    assert b.castigo.sinais(perto)["PLACA"] == 1.0
    assert b.castigo.sinais(longe)["PLACA"] == 0.0
