"""Falhas do relatório técnico (docs/auditorias/ANALISE_TECNICA.md): cada caso tem um teste que reproduz o problema."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.core.episodic import EpisodicMemory  # noqa: E402
from pestinha.core.homeostasis import Drives  # noqa: E402
from pestinha.core.nervous_system import LIFBrain  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402
from pestinha.store import read_json, write_json  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def pet_app(qapp, tmp_path):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, travessuras=True))
    app = PestinhaApp(store, paths)
    yield app
    app.floats.hidden_by_tray = True
    for w in list(app.floats.windows.values()):
        w.close()


# 1) pânico e desligamento alcançam tudo
def test_pausa_congela_a_rede(pet_app):
    pet_app.toggle_pause()
    before = pet_app.brain.time_ms
    pet_app.think()
    assert pet_app.brain.time_ms == before


def test_desligado_nao_pensa(pet_app):
    pet_app.store.panic()
    before = pet_app.brain.time_ms
    pet_app.think()
    assert pet_app.brain.time_ms == before


def test_painel_nao_abre_com_o_bryan_desligado(pet_app):
    pet_app.store.panic()
    pet_app.floats.open("neural")
    assert "neural" not in pet_app.floats.opened
    assert not pet_app.floats.window("neural").isVisible()


def test_cartaz_de_tristeza_some_no_pânico(pet_app):
    pet_app.sad_ctl.protest.sign = None
    pet_app.panic()
    assert pet_app.sad_ctl.protest.sign is None


# 2) carregamento é tudo-ou-nada
def test_carregamento_invalido_nao_altera_a_rede(tmp_path):
    brain = LIFBrain(seed=7)
    brain.learned[0, 0] = 0.05
    path = tmp_path / "rede.json"
    brain.save(str(path))
    data = read_json(path)
    data["learned"]["MOTION"]["PLAYFUL"] = 0.02          # valor válido
    data["efficacy"][brain.sensory_names[1]] = [0.5]      # forma inválida no segundo canal
    write_json(path, data)
    other = LIFBrain(seed=7)
    before_learned = other.learned.copy()
    before_p = other.p.copy()
    assert other.load(str(path)) is False
    assert np.array_equal(other.learned, before_learned)
    assert np.array_equal(other.p, before_p)


# 3) NaN não entra na rede
def test_nan_no_json_e_rejeitado(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"a": NaN}', encoding="utf-8")
    assert read_json(path, default="padrao") == "padrao"


def test_escrita_recusa_nan(tmp_path):
    with pytest.raises(ValueError):
        write_json(tmp_path / "y.json", {"a": float("nan")})


def test_rede_recusa_peso_aprendido_nan(tmp_path):
    brain = LIFBrain(seed=7)
    brain.save(str(tmp_path / "rede.json"))
    data = read_json(tmp_path / "rede.json")
    data["learned"]["MOTION"]["PLAYFUL"] = float("nan")
    path = tmp_path / "rede2.json"
    path.write_text(json.dumps(data), encoding="utf-8")       # gravação manual, com NaN
    other = LIFBrain(seed=7)
    assert other.load(str(path)) is False
    assert np.isfinite(other.W).all()


# 4) JSON válido com schema errado não derruba nada
def test_homeostase_com_tipo_errado_nao_levanta(tmp_path):
    path = tmp_path / "drives.json"
    write_json(path, {"energy": "erro", "stimulation": 0.5, "contact": 0.1, "saved_at": 0})
    drives = Drives()
    assert drives.load(path, {"sleep_recover": 60.0, "stim_decay": 40.0, "contact_span": 120.0}) is False
    assert drives.energy == 1.0


def test_episodio_invalido_e_ignorado_no_sono(tmp_path):
    ep_path = tmp_path / "episodes.jsonl"
    ep_path.write_text('{}\n{"contexto": "IDLE|observando", "acao": "meme", "valencia": 0.5}\n'
                       'lixo não é json\n', encoding="utf-8")
    memory = EpisodicMemory(ep_path, tmp_path / "prefs.json")
    prefs = memory.consolidate()          # não pode levantar KeyError
    assert ("IDLE|observando", "meme") in [(c, a) for c, a, _m, _n in prefs]


def test_preferencias_corrompidas_viram_vazias(tmp_path):
    prefs = tmp_path / "prefs.json"
    write_json(prefs, {"tabela": {"ctx": {"meme": ["x", "y"]}}, "geral": 5})
    memory = EpisodicMemory(tmp_path / "episodes.jsonl", prefs)
    memory.load()
    assert memory.table == {} and memory.totals == {}


def test_permissao_com_tipo_errado_e_ignorada(tmp_path):
    paths = Paths(root=tmp_path)
    write_json(paths.permissions, {"modo_teste": "sim", "ativo": True})
    perms = config.load_permissions(paths)
    assert perms["modo_teste"] is config.DEFAULT_PERMISSIONS["modo_teste"]
    assert perms["ativo"] is True


# 5) troca de modo atualiza o condicionamento nos dois sentidos
def test_troca_de_modo_atualiza_taxa_do_condicionamento(pet_app):
    pet_app.store.update({"modo_teste": False})
    pet_app.apply_perms(dict(pet_app.perms, modo_teste=False))
    rate_normal = pet_app.conditioning.rate
    pet_app.apply_perms(dict(pet_app.perms, modo_teste=True))
    rate_teste = pet_app.conditioning.rate
    pet_app.apply_perms(dict(pet_app.perms, modo_teste=False))
    assert rate_teste == config.profile(dict(config.DEFAULT_PERMISSIONS, modo_teste=True))["cond_rate"]
    assert pet_app.conditioning.rate == rate_normal
    assert rate_normal != rate_teste


# 6) a transição da rotina é vista pelo app
def test_dialogo_nao_muda_o_dicionario_compartilhado(qapp, tmp_path):
    from pestinha.ui.ui import SettingsDialog
    paths = Paths(root=tmp_path)
    perms = dict(config.DEFAULT_PERMISSIONS, rotina=True)
    dialog = SettingsDialog(perms, paths, first_run=False)
    dialog._set("rotina", False)
    assert perms["rotina"] is True                 # o original não mudou antes de o app decidir


def test_apagar_dados_nao_recria_a_pasta(pet_app, monkeypatch):
    monkeypatch.setattr(pet_app, "quit", lambda: None)
    pet_app.memory.save()
    pet_app.wipe_all_data()
    assert not pet_app.paths.memory.exists()
    from pestinha import log as log_module
    log_module.log("depois de apagar")       # o log não pode recriar a pasta
    assert not pet_app.paths.memory.exists()
