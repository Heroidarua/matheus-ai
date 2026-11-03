"""Homeostase: trabalhar é estímulo, então o tédio não sobe enquanto ele programa."""

from pestinha.core.homeostasis import BORED_BELOW, Drives

PROF = {"sleep_recover": 300.0, "energy_span": 600.0, "stim_decay": 120.0, "contact_span": 900.0}


def run(drives, seconds, **kwargs):
    for _ in range(int(seconds / 0.1)):
        drives.update(0.1, PROF, False, 0.0, 0.0, False, **kwargs)


def test_tedio_sobe_sem_trabalho():
    drives = Drives()
    run(drives, 300)
    assert drives.channels()["BOREDOM"] > 0.0
    assert drives.stimulation < BORED_BELOW


def test_trabalhando_nao_fica_entediado():
    drives = Drives()
    drives.stimulation = 0.1           # já estava entediado antes de começar a programar
    run(drives, 60, engaged=True)
    assert drives.channels()["BOREDOM"] == 0.0


def test_trabalho_nao_eleva_acima_do_nivel():
    drives = Drives()
    run(drives, 120, engaged=True)
    assert drives.stimulation <= 0.6 + 1e-9
