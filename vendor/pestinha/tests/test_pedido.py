"""Pedir para trabalhar: o neurônio SENTAR decide. Se ele não senta até o pedido acabar, recusa."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.ajustes import LIMIAR_SENTAR_HZ, PEDIDO_VALIDADE_S  # noqa: E402
from pestinha.mind.mesa import MesaController  # noqa: E402
from pestinha.paths import Paths  # noqa: E402


class App:
    def __init__(self, paths):
        self.paths = paths
        self.conteudo = paths.conteudo("bryan")
        self.nome = "Bryan"


class Brincadeira:
    next_at = 0.0


QUER = LIMIAR_SENTAR_HZ + 4.0       # SENTAR disparando forte: ele quer trabalhar
NAO_QUER = 0.0                      # SENTAR calado: ele não quer


@pytest.fixture
def mesa(tmp_path):
    QApplication.instance() or QApplication([])
    return MesaController(lambda: False, App(Paths(root=tmp_path)))


def test_senta_quando_o_neuronio_quer(mesa):
    mesa.pedir(0.0)
    mesa.tick(1.0, {}, QUER, True, Brincadeira())
    assert mesa.sentado is True
    assert mesa.pop_recusa() is False


def test_recusa_quando_o_pedido_acaba_sem_sentar(mesa):
    mesa.pedir(0.0)
    mesa.tick(1.0, {}, NAO_QUER, True, Brincadeira())
    assert mesa.sentado is False
    assert mesa.pop_recusa() is False            # o pedido ainda vale
    mesa.tick(PEDIDO_VALIDADE_S + 1.0, {}, NAO_QUER, True, Brincadeira())
    assert mesa.pop_recusa() is True


def test_pedido_que_deu_certo_nao_recusa(mesa):
    mesa.pedir(0.0)
    mesa.tick(1.0, {}, QUER, True, Brincadeira())
    mesa.tick(PEDIDO_VALIDADE_S + 1.0, {}, QUER, True, Brincadeira())
    assert mesa.pop_recusa() is False


def test_intensidade_do_pedido_decai(mesa):
    mesa.pedir(0.0)
    assert mesa.intensidade_pedido(0.0) == 1.0
    assert 0.0 < mesa.intensidade_pedido(PEDIDO_VALIDADE_S / 2) < 1.0
    assert mesa.intensidade_pedido(PEDIDO_VALIDADE_S + 1.0) == 0.0


def test_pedidos_recentes_contam(mesa):
    mesa.pedir(0.0)
    mesa.pedir(10.0)
    mesa.pedir(20.0)
    assert mesa.pedidos_recentes() == 3


def test_esconder_e_mostrar_o_notebook(mesa):
    mesa.set_visible(True)
    assert not mesa.caderno.isHidden()
    mesa.alternar_notebook()
    assert mesa.caderno.isHidden()
    mesa.alternar_notebook()
    assert not mesa.caderno.isHidden()
