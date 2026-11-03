"""Reproduções diagnósticas: asserções descrevem o comportamento esperado."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PySide6.QtWidgets import QApplication
from pestinha.body.pet_state import PetState
from pestinha.core.episodic import EpisodicMemory
from pestinha.mind.castigo_ctl import CastigoController


@pytest.fixture
def memoria(tmp_path):
    return EpisodicMemory(tmp_path / 'episodios.jsonl', tmp_path / 'prefs.json')


@pytest.fixture
def canto(tmp_path):
    qt = QApplication.instance() or QApplication([])
    app = SimpleNamespace(paths=SimpleNamespace(memory=tmp_path),
                          pet_paths=SimpleNamespace(castigo=tmp_path / 'castigo.json'),
                          conteudo=SimpleNamespace(signs=tmp_path / 'cartazes.txt'),
                          behavior=SimpleNamespace(fuga_alvo=None))
    ctl = CastigoController(app, lambda: False)
    yield ctl
    assert qt is not None


def test_punir_ultimo_episodio_e_nao_primeiro(memoria):
    antigo = memoria.start('WORK|curioso', 'meme', object())
    novo = memoria.start('WORK|curioso', 'meme', object())
    memoria.punir(novo['inicio'] + 1, 20)
    assert antigo in memoria.open and novo not in memoria.open


def test_punicao_de_episodio_resolvido_sobrevive_ao_sono(memoria):
    ep = memoria.start('WORK|curioso', 'meme')
    memoria._resolve(ep, 'atenção', 0.5)
    memoria.punir(ep['inicio'] + 1, 20)
    antes = memoria.table['WORK|curioso']['meme'][1]
    memoria.consolidate()
    assert memoria.table['WORK|curioso']['meme'][1] == pytest.approx(antes)


def test_pausa_preserva_janela_de_castigo(memoria):
    ep = memoria.start('WORK|curioso', 'meme')
    inicio = ep['inicio']
    memoria.deslocar(100)
    assert memoria.punir(inicio + 101, 20) == 'meme'


def test_liberacao_cancela_recompensa_negativa(canto):
    estado = PetState()
    canto._entrar(10, estado)
    canto._soltar(estado)
    assert canto.punicao(10.5) == 0


def test_recaptura_cancela_tentativa_de_fuga(canto):
    canto.fuga = 10
    canto.zona_fuga = (0, 190)
    canto.app.behavior.fuga_alvo = 490
    canto._entrar(11, PetState())
    assert canto.fuga is None and canto.app.behavior.fuga_alvo is None
