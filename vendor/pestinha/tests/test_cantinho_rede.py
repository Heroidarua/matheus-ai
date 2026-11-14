"""As 10 funções do cantinho que mexem na rede neural: entrada, aprendizado e efeito nos motores."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha.ajustes import LIMIAR_SENTAR_HZ  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.core.conditioning import Conditioning  # noqa: E402
from pestinha.core.episodic import EpisodicMemory  # noqa: E402
from pestinha.core.homeostasis import Drives  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402
from pestinha.mind.castigo_ctl import LIMIAR_PERDAO_HZ, CastigoController  # noqa: E402
from pestinha.paths import Paths  # noqa: E402

BOUNDS = (0, 0, 1000, 700)
PROF = {"sleep_recover": 60.0, "energy_span": 300.0, "stim_decay": 40.0, "contact_span": 120.0}


def rede(entradas, segundos=40):
    brain = LIFBrain(seed=7)
    brain.rng = np.random.default_rng(123)
    for _ in range(int(segundos * 10)):
        brain.stimulate(dict(entradas))
        brain.step(100)
    return brain


class Corpo:
    def __init__(self, x):
        self.x, self.y = x, 600.0
        self.grounded, self.held = True, False

    def extents(self):
        return (20.0, 30.0)


@pytest.fixture
def castigo(tmp_path):
    QApplication.instance() or QApplication([])
    app = SimpleNamespace(paths=Paths(root=tmp_path), pet_paths=Paths(root=tmp_path).pet("bryan"),
                          pet=SimpleNamespace(raise_=lambda: None),
                          behavior=SimpleNamespace(fuga_alvo=None, walk_to=lambda x, v: None),
                          memory=EpisodicMemory(tmp_path / "ep.jsonl", tmp_path / "prefs.json"),
                          conditioning=Conditioning())
    c = CastigoController(app, lambda: False)
    c.toggle(BOUNDS)
    c.plaquinha.move(0, 550)
    return c


# 1) acostumar-se: o canal PRESO perde eficácia com castigo longo
def test_preso_habitua():
    brain = rede({"PRESO": 1.0}, segundos=60)
    assert brain.efficacy()["PRESO"] < 0.95


# 2) medo da placa: a pista da placa só aprende com o desfecho "ficar preso"
def test_pista_da_placa_aprende_com_castigo():
    cond = Conditioning(rate=0.5)
    for k in range(4):
        t = k * 10.0
        cond.set_cue("PLACA", True, t)
        cond.set_cue("PLACA", False, t + 1)
        cond.outcome(t + 1.2, cues=("PLACA",))
        cond.tick(t + 5)
    assert cond.V["PLACA"] > 0.5


def test_cutucada_nao_ensina_a_pista_da_placa():
    cond = Conditioning(rate=0.5)
    cond.set_cue("PLACA", True, 0.0)
    cond.set_cue("PLACA", False, 1.0)
    cond.outcome(1.2)                     # desfecho de cutucada/arraste
    cond.tick(5.0)
    assert cond.V["PLACA"] == 0.0


# 3) aviso: a placa à vista entra na rede e reduz travessuras
def test_placa_visivel_e_sinal_e_reduz_travessura(castigo):
    assert castigo.sinais()["PLACA"] == 1.0
    sem = rede({"BOREDOM": 1.0}).motor_activity()["TRAVESSURA"]
    com = rede({"BOREDOM": 1.0, "PLACA": 1.0}).motor_activity()["TRAVESSURA"]
    assert com < sem


# 4) castigo ensina: a travessura feita logo antes vira episódio ruim
def test_castigo_logo_depois_de_travessura_ensina(tmp_path):
    mem = EpisodicMemory(tmp_path / "ep.jsonl", tmp_path / "prefs.json")
    mem.start("IDLE|curioso", "meme")
    assert mem.punir(time.monotonic(), 20.0) == "meme"
    assert mem.table["IDLE|curioso"]["meme"][1] < 0


def test_castigo_muito_depois_nao_ensina(tmp_path):
    mem = EpisodicMemory(tmp_path / "ep.jsonl", tmp_path / "prefs.json")
    mem.start("IDLE|curioso", "meme")
    assert mem.punir(time.monotonic() + 100.0, 20.0) is None


def test_ser_preso_da_recompensa_negativa(castigo):
    state = PetState()
    castigo._entrar(10.0, state)
    assert castigo.punicao(10.5) < 0
    assert castigo.punicao(20.0) == 0


# 5) rancor: sobe preso, cai solto, e na rede tira a vontade de trabalhar
def test_rancor_sobe_preso_e_cai_solto(castigo):
    castigo.dentro = True
    castigo.tick_lento(60.0)
    alto = castigo.rancor
    castigo.dentro = False
    castigo.tick_lento(60.0)
    assert alto > 0 and castigo.rancor < alto


def test_rancor_tira_vontade_de_trabalhar():
    sem = rede({"WORK": 1.0, "TYPING": 0.6}).motor_activity()["SENTAR"]
    com = rede({"WORK": 1.0, "TYPING": 0.6, "RANCOR": 1.0}).motor_activity()["SENTAR"]
    assert sem >= LIMIAR_SENTAR_HZ > com


# 6) carinho como perdão: ACEITAR dispara e ele sai sem contar fuga
def test_carinho_leva_ao_perdao():
    assert rede({"PRESO": 1.0, "CARESS": 1.0}).motor_activity()["ACEITAR"] >= LIMIAR_PERDAO_HZ
    assert rede({"PRESO": 1.0}).motor_activity()["ACEITAR"] < LIMIAR_PERDAO_HZ


def test_perdao_solta_sem_vitoria(castigo):
    state = PetState()
    castigo._entrar(0.0, state)
    castigo.rancor = 0.8
    castigo._decidir(1.0, 0.1, Corpo(100.0), BOUNDS, {"ACEITAR": LIMIAR_PERDAO_HZ + 1})
    assert castigo.dentro is False and state.castigo is False
    assert castigo.vitorias["fugir"] == 0.0 and castigo.rancor == pytest.approx(0.4)


# 7) visitas: cursor perto vira sinal; ignorado, a carência cresce mais rápido
def test_visita_vira_sinal(castigo):
    state = PetState()
    castigo._entrar(0.0, state)
    castigo.ultimo = 0.0
    corpo = Corpo(100.0)
    for k in range(1, 30):
        castigo.act(k * 0.1, corpo, BOUNDS, (110, 600), state, {})
    assert castigo.sinais()["VISITA"] > 0.5


def test_ignorado_preso_fica_carente_mais_rapido():
    solto, ignorado = Drives(), Drives()
    solto.update(10.0, PROF, False, 0, 0, False)
    ignorado.update(10.0, PROF, False, 0, 0, False, preso=True, visitado=False)
    assert ignorado.contact > solto.contact


# 8) fuga que deu errado: devolvido ao canto, perde a vitória e ganha receio, que inibe a fuga
def test_fuga_desfeita_vira_receio(castigo):
    castigo.vitorias["fugir"] = 2.0
    castigo.ultima_fuga_em = 100.0
    castigo._entrar(130.0, PetState())
    assert castigo.vitorias["fugir"] == 1.0 and castigo.receio > 0


def test_receio_inibe_fuga():
    sem = rede({"PRESO": 1.0, "LEMBRA_FUGA": 1.0}).motor_activity()["FUGIR"]
    com = rede({"PRESO": 1.0, "LEMBRA_FUGA": 1.0, "RECEIO": 1.0}).motor_activity()["FUGIR"]
    assert com < sem


# 9) cartaz como desabafo: a ligação CARTAZ -> FRUSTRATION é inibitória
def test_cartaz_inibe_frustracao():
    brain = LIFBrain(seed=7)
    pre, post = brain.pool("CARTAZ"), brain.pool("FRUSTRATION")
    bloco = brain.W[pre["start"]:pre["start"] + pre["n"], post["start"]:post["start"] + post["n"]]
    bloco_t = brain.W[post["start"]:post["start"] + post["n"], pre["start"]:pre["start"] + pre["n"]]
    assert min(bloco.min(), bloco_t.min()) < 0


# 10) tédio no canto: o tédio cresce mais rápido preso, e o tédio puxa a fuga
def test_preso_entedia_mais_rapido():
    solto, preso = Drives(), Drives()
    solto.update(10.0, PROF, False, 0, 0, False)
    preso.update(10.0, PROF, False, 0, 0, False, preso=True)
    assert preso.stimulation < solto.stimulation


def test_tedio_puxa_a_fuga():
    sem = rede({"PRESO": 1.0}).motor_activity()["FUGIR"]
    com = rede({"PRESO": 1.0, "BOREDOM": 1.0}).motor_activity()["FUGIR"]
    assert com > sem


def test_rancor_e_receio_sao_salvos(castigo, tmp_path):
    castigo.rancor, castigo.receio = 0.5, 0.25
    castigo.salvar()
    outro = CastigoController(castigo.app, lambda: False)
    assert outro.rancor == 0.5 and outro.receio == 0.25


# a antecipação de cutucadas não vira fuga; a antecipação da placa vira
def test_antecipacao_separada_por_pista():
    cond = Conditioning()
    cond.V["PRESS"], cond.V["PLACA"] = 0.9, 0.0
    cond.set_cue("PRESS", True, 0.0)
    assert cond.strength() == 0.9 and cond.strength(cues=("PLACA",)) == 0.0


def test_so_a_placa_antecipada_puxa_a_fuga():
    base = rede({"PRESO": 1.0}).motor_activity()["FUGIR"]
    cutucada = rede({"PRESO": 1.0, "ANTICIPATE": 1.0}).motor_activity()["FUGIR"]
    placa = rede({"PRESO": 1.0, "ANTECIPA_PLACA": 1.0}).motor_activity()["FUGIR"]
    assert placa > base and placa > cutucada
