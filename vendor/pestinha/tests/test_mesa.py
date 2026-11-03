"""Notebook: sentar e levantar pelo disparo do neurônio SENTAR. Rodar: python -m pytest tests -q"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.ajustes import FOCO_MAXIMO_HZ, LIMIAR_LEVANTAR_HZ, LIMIAR_SENTAR_HZ  # noqa: E402
from pestinha.mind.mesa import DeskController, distraction_level, focus_level  # noqa: E402


def test_senta_quando_o_neuronio_dispara_forte():
    d = DeskController()
    change = d.tick(1.0, LIMIAR_SENTAR_HZ + 1.0, True)
    assert d.at_desk and change == (False, True)


def test_nao_senta_com_disparo_fraco():
    d = DeskController()
    for i in range(100):
        d.tick(i * 0.1, LIMIAR_SENTAR_HZ - 1.0, True)
    assert not d.at_desk


def test_histerese_nao_levanta_com_disparo_intermediario():
    d = DeskController()
    d.tick(0.0, LIMIAR_SENTAR_HZ + 1.0, True)
    d.tick(0.1, (LIMIAR_SENTAR_HZ + LIMIAR_LEVANTAR_HZ) / 2, True)
    assert d.at_desk


def test_levanta_quando_o_disparo_cai_ou_nao_pode():
    d = DeskController()
    d.tick(0.0, LIMIAR_SENTAR_HZ + 1.0, True)
    assert d.tick(1.0, LIMIAR_LEVANTAR_HZ - 1.0, True) == (True, False)
    d.tick(2.0, LIMIAR_SENTAR_HZ + 1.0, True)
    assert d.tick(3.0, LIMIAR_SENTAR_HZ + 1.0, False) == (True, False)


def test_niveis_vem_das_populacoes():
    rates = {"FOCUS": FOCO_MAXIMO_HZ, "PLAYFUL": 0.0, "CURIOUS": FOCO_MAXIMO_HZ / 2}
    assert focus_level(rates) == 1.0
    assert distraction_level(rates) == 0.5
