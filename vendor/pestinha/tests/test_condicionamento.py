"""
Testes do condicionamento: aprender a reagir antes, extinguir, e persistir.

Rodar (na pasta v7):  python -m pytest tests -q
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from pestinha.core.conditioning import Conditioning  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402


def repeat(c, n, with_outcome, start=0.0, gap=3.0):
    t = start
    for _ in range(n):
        c.set_cue("PRESS", True, t)
        t += 0.3
        if with_outcome:
            c.outcome(t)
        c.set_cue("PRESS", False, t)
        t += gap
        c.tick(t)
    return t


def test_sempre_jogado_depois_de_apertar_aprende_a_antecipar():
    c = Conditioning(rate=0.2)
    repeat(c, 10, with_outcome=True)
    assert c.V["PRESS"] > 0.8


def test_apertar_sem_nada_depois_extingue():
    c = Conditioning(rate=0.2)
    t = repeat(c, 10, with_outcome=True)
    repeat(c, 15, with_outcome=False, start=t)
    assert c.V["PRESS"] < 0.1


def test_antecipacao_so_aparece_com_o_cue_ativo():
    c = Conditioning(rate=0.2)
    repeat(c, 10, with_outcome=True)
    assert c.strength() == 0.0          # nenhum cue ativo agora
    c.set_cue("PRESS", True, 100.0)
    assert c.strength() > 0.8


def test_desfecho_depois_da_janela_nao_conta():
    c = Conditioning(rate=0.5)
    c.set_cue("PRESS", True, 0.0)
    c.set_cue("PRESS", False, 0.1)
    c.outcome(10.0)                      # longe demais do fim do cue
    c.tick(20.0)
    assert c.V["PRESS"] == 0.0


def test_pausa_nao_expira_janela_de_condicionamento():
    c = Conditioning(rate=0.5)
    c.V["PRESS"] = 1.0
    c.set_cue("PRESS", True, 10.0)
    c.set_cue("PRESS", False, 10.1)

    c.deslocar(60.0)
    c.tick(70.1)                       # retomada imediata: a janela ainda está aberta

    assert c.V["PRESS"] == 1.0
    assert c.ended == [["PRESS", 70.1, False]]


def test_persiste_entre_sessoes(tmp_path):
    path = tmp_path / "conditioning.json"
    c = Conditioning(path, rate=0.2)
    repeat(c, 10, with_outcome=True)
    c.save()
    again = Conditioning(path, rate=0.2)
    again.load()
    assert abs(again.V["PRESS"] - c.V["PRESS"]) < 1e-9


def test_antecipacao_chega_na_rede_e_acorda_o_alerta():
    def alert_after(anticipate):
        brain = LIFBrain(seed=7)
        brain.rng = np.random.default_rng(123)
        for _ in range(20):
            brain.stimulate({})
            brain.step(100)
        peak = 0.0
        for _ in range(10):
            brain.stimulate({"ANTICIPATE": anticipate})
            brain.step(100)
            peak = max(peak, brain.pool_rates()["ALERT"])
        return peak

    assert alert_after(1.0) > alert_after(0.0) + 1.0
