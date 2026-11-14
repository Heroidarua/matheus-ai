"""
Testes da bolinha e da tristeza (abandono). Rodar: python -m pytest tests -q
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.core.homeostasis import Drives  # noqa: E402
from pestinha.core.protesto import Protesto  # noqa: E402
from pestinha.body.toy import FAR, NEAR, ToyTracker  # noqa: E402


def test_levar_a_bolinha_conta_uma_vez_e_rearma_ao_voltar():
    t = ToyTracker()
    assert t.update((900, 500), (100, 500), True)[0] is True
    assert t.update((900, 500), (100, 500), True)[0] is False     # já contou
    t.update((100 + NEAR - 10, 500), (100, 500), True)             # voltou perto
    assert t.update((100 + FAR + 50, 500), (100, 500), True)[0] is True


def test_bolinha_longe_sem_voce_mexer_nao_conta():
    t = ToyTracker()
    assert t.update((900, 500), (100, 500), False)[0] is False


def test_perto_dele_a_brincadeira_aparece():
    t = ToyTracker()
    _, near = t.update((140, 500), (100, 500), False)
    _, far = t.update((700, 500), (100, 500), False)
    assert near > 0.9 and far == 0.0


def test_tristeza_sobe_com_triste_e_sozinho(tmp_path):
    from pestinha.paths import Paths
    p = Protesto(Paths(root=tmp_path).conteudo("bryan").signs, tmp_path / "s.json", kind="tristeza")
    prof = {"grievance_up": 40.0, "grievance_down": 300.0, "stage_up": [0.2, 0.5, 0.8, 1.0],
            "stage_hyst": 0.06}
    stages = []
    for i in range(3000):
        ch = p.update(0.1, 0.5, prof, False, i * 0.1)
        if ch:
            stages.append(ch[1])
    assert max(stages) == 3            # tristeza chega ao abandono, e nunca à revolução
    assert 4 not in stages


def test_sozinho_por_muito_tempo_fica_carente():
    d = Drives()
    d.contact = 1.0
    assert d.channels()["LONELY"] > 0.9
