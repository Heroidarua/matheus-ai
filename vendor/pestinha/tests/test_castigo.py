"""Cantinho do castigo: soltar o Bryan na frente da placa prende ele, e a fuga bem-sucedida fica salva."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.mind.castigo_ctl import CastigoController  # noqa: E402
from pestinha.paths import Paths  # noqa: E402


class Corpo:
    def __init__(self, x):
        self.x, self.y = x, 600.0
        self.grounded = True
        self.held = False

    def extents(self):
        return (20.0, 30.0)


class Comportamento:
    def __init__(self):
        self.caminhos = []
        self.body = Corpo(100.0)

    def walk_to(self, x, speed):
        self.caminhos.append(x)


class Janela:
    def raise_(self):
        pass


class App:
    def __init__(self, paths):
        self.paths = paths
        self.pet_paths = paths.pet("bryan")
        self.behavior = Comportamento()
        self.pet = Janela()


BOUNDS = (0, 0, 1000, 700)


@pytest.fixture
def qt():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def castigo(qt, tmp_path):
    c = CastigoController(App(Paths(root=tmp_path)), lambda: False)
    c.toggle(BOUNDS)
    c.plaquinha.move(0, 550)          # a placa fica no canto esquerdo: x entre 0 e a largura
    return c


def soltar_no_canto(c, state, x=100.0, t=0.0):
    corpo = Corpo(x)
    corpo.held = True
    c.act(t, corpo, BOUNDS, (500, 500), state, {})
    corpo.held = False
    c.act(t + 0.1, corpo, BOUNDS, (500, 500), state, {})


def test_soltar_na_frente_da_placa_prende_o_bryan(castigo):
    state = PetState()
    soltar_no_canto(castigo, state)
    assert state.castigo is True


def test_andar_ate_o_canto_sem_ser_solto_nao_prende(castigo):
    state = PetState()
    castigo.act(0.0, Corpo(100.0), BOUNDS, (500, 500), state, {})
    assert state.castigo is False


def test_sair_do_canto_solta_o_bryan(castigo):
    state = PetState()
    soltar_no_canto(castigo, state)
    castigo.act(1.0, Corpo(500.0), BOUNDS, (500, 500), state, {})
    assert state.castigo is False


def test_fuga_bem_sucedida_fica_salva(castigo):
    castigo.fuga = 0.0
    castigo._checar_fuga(1.0, Corpo(400.0))
    assert castigo.vitorias["fugir"] == 1.0
    assert castigo.fuga is None
    assert castigo.path.exists()


def test_desligar_o_menu_solta_o_bryan(castigo):
    state = PetState()
    soltar_no_canto(castigo, state)
    castigo.toggle(BOUNDS)
    assert state.castigo is False
    assert castigo.ativo is False
