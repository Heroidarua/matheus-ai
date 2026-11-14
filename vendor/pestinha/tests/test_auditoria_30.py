"""Contratos dos 30 bugs da auditoria (docs/auditorias/AUDITORIA_30_BUGS.md). Todos passam desde a correção.
Sem escrita na memória pessoal do pet.
"""
import os
import json
import time
from collections import Counter
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from pestinha import config
from pestinha.app import PestinhaApp
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore
from pestinha.world.arrastavel import FloatingWidget
from pestinha.body.brincadeira import Play
from pestinha.body.toy import bounce_off, RADIUS
from pestinha.core.physics import Body
from pestinha.core.protesto import Protesto
from pestinha.core.nervous_system import LIFBrain
from pestinha.core.episodic import EpisodicMemory
from pestinha.mind.castigo_ctl import CastigoController
from pestinha import log as log_module


@pytest.fixture(scope="module")
def qa_qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def audit_buddy(qa_qapp, tmp_path, monkeypatch):
    previous = set(qa_qapp.topLevelWidgets())
    monkeypatch.setattr("pestinha.app.PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    monkeypatch.setattr("pestinha.app.senses.get_active_app", lambda: "code.exe")
    monkeypatch.setattr("pestinha.app.senses.get_idle_seconds", lambda: 0.)
    monkeypatch.setattr("pestinha.app.senses.is_fullscreen", lambda: False)
    monkeypatch.setattr("pestinha.app.senses.list_windows", lambda exclude, escala=1.0: [])
    paths = Paths(tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, rotina=False, travessuras=True))
    buddy = PestinhaApp(store, paths)
    for timer in buddy.findChildren(QTimer):
        timer.stop()
    yield buddy
    for widget in set(qa_qapp.topLevelWidgets()) - previous:
        for timer in widget.findChildren(QTimer):
            timer.stop()
        widget.close()
    log_module.desligar_arquivo()


def prepare_mischief(b):
    b.conteudo.proprio.mkdir(parents=True, exist_ok=True)
    b.conteudo.notes.write_text("Nota de teste\n", encoding="utf-8")
    b.pet.body.grounded = True
    b.pet.body.held = False
    b.behavior.mission = None
    b.memory.choose = Mock(return_value="bilhete")


def test_01_configuracao_aberta_nao_reverte_panico(audit_buddy):
    b = audit_buddy
    b.open_settings()
    b.panic()
    b.settings._set("memes", False)
    assert b.perms["ativo"] is False


def test_02_panico_ainda_esconde_tudo_se_disco_falhar(audit_buddy, monkeypatch):
    b = audit_buddy
    monkeypatch.setattr(b.store, "save", Mock(side_effect=OSError("disco indisponível")))
    try:
        b.panic()
    except OSError:
        pass
    assert not b.pet.isVisible()


def test_03_sair_continua_se_condicionamento_nao_puder_salvar(audit_buddy, monkeypatch):
    quit_app = Mock()
    monkeypatch.setattr(QApplication, "quit", quit_app)
    monkeypatch.setattr(audit_buddy.conditioning, "save", Mock(side_effect=OSError("disco")))
    try:
        audit_buddy.quit()
    except OSError:
        pass
    quit_app.assert_called_once()


def test_04_fim_de_tristeza_nao_mostra_cartaz_quando_oculto(audit_buddy):
    b = audit_buddy
    b.hidden = True
    b.update_visibility()
    b.sad.stage = 0
    b.sad_ctl.on_stage(1, 0)
    assert b.sad.sign is None or not b.sad.sign.isVisible()


def test_05_cutucada_nao_altera_estado_durante_pausa(audit_buddy):
    b = audit_buddy
    b.toggle_pause()
    before = b.drives.stimulation
    b.on_poke()
    assert b.drives.stimulation == before


def test_06_pausa_para_timer_independente_dos_fogos(audit_buddy):
    b = audit_buddy
    b.festa.fogos.launch(300, 300)
    b.toggle_pause()
    assert not b.festa.fogos.timer.isActive()


def test_07_desligar_fogos_recolhe_efeito_ja_aberto(audit_buddy):
    b = audit_buddy
    b.festa.fogos.launch(300, 300)
    b.apply_perms(dict(b.perms, fogos=False))
    assert not b.festa.fogos.isVisible()


def test_08_tempo_pausado_nao_expira_episodio_pendente(audit_buddy, monkeypatch):
    b = audit_buddy
    now = time.monotonic()
    b.memory.start("IDLE|curioso", "nada")
    b.toggle_pause()
    monkeypatch.setattr(time, "monotonic", lambda: now + 120)
    b.toggle_pause()
    b.think()
    assert len(b.memory.open) == 1


def test_09_bolinha_guardada_nao_estimula_rede(audit_buddy):
    b = audit_buddy
    b.ball.body.x, b.ball.body.y = b.pet.body.x, b.pet.body.y
    b.menu_store_ball()
    b.think()
    assert b.intensities["TOY_NEAR"] == 0


def test_10_comando_agora_nao_depende_de_disparo_espontaneo(audit_buddy):
    b = audit_buddy
    prepare_mischief(b)
    b.menu_mischief()
    result = b.mischief_ctl.maybe_act(time.monotonic(), .016, b.bounds(), (0, 0), b.pet.body,
        motores={"TRAVESSURA": 0}, activity="IDLE", emotion="curioso", perms=b.perms,
        prof=b.prof, fullscreen=False, asleep=False, protest_stage=0)
    assert result is not None


def test_11_peso_postit_zero_realmente_desliga_postit(audit_buddy, monkeypatch):
    b = audit_buddy
    prepare_mischief(b)
    b.mischief_ctl.postit_weight = 0
    monkeypatch.setattr("pestinha.mind.mischief_ctl.random.random", lambda: 0.)
    result = b.mischief_ctl.maybe_act(time.monotonic(), .016, b.bounds(), (0, 0), b.pet.body,
        motores={"TRAVESSURA": 100}, activity="IDLE", emotion="curioso", perms=b.perms,
        prof=b.prof, fullscreen=False, asleep=False, protest_stage=0)
    assert result not in ("bilhete", "bilhete_canto", "bilhete_triste")


def test_12_bryan_nao_chuta_bola_segurada_pelo_usuario(audit_buddy, monkeypatch):
    b = audit_buddy
    b.ball.show()
    b.ball.dragging = True
    b.ball.body.x, b.ball.body.y = b.pet.body.x, b.pet.body.y
    monkeypatch.setattr("pestinha.body.brincadeira.random.random", lambda: 0.)
    assert Play({"bola": 1}).tick(100, b.pet.body, b.ball, (0, 0), "feliz") is None


def test_13_soltar_botao_direito_nao_encerra_arraste_esquerdo(audit_buddy):
    ball = audit_buddy.ball
    ball.dragging = True
    ball.mouseReleaseEvent(SimpleNamespace(button=lambda: Qt.RightButton))
    assert ball.dragging


def test_14_colisao_retira_centro_do_interior_do_retangulo():
    ball = SimpleNamespace(body=Body(150, 150, RADIUS, RADIUS), place=Mock())
    bounce_off(ball, [(100, 100, 100, 100)])
    x, y = ball.body.x, ball.body.y
    assert x <= 100 - RADIUS or x >= 200 + RADIUS or y <= 100 - RADIUS or y >= 200 + RADIUS


def test_15_pouso_escolhe_primeira_superficie_cruzada_na_queda():
    body = Body(200, 100, 10, 10)
    body.vy = 1000
    body.step(.05, (0, 0, 1000, 1000), [(2, 0, 1000, 150), (1, 0, 1000, 120)])
    assert body.surface == 120


def test_16_panico_cancela_arraste_para_permitir_gravidade_ao_religar(audit_buddy):
    b = audit_buddy
    b.pet.body.held = True
    b.pet._dragging = True
    b.pet_state.pressing = True
    b.panic()
    b.apply_perms(dict(b.perms, ativo=True))
    assert not b.pet.body.held and not b.pet.dragging


def test_17_posicao_antiga_fora_das_telas_e_recuperada(audit_buddy, qa_qapp):
    b = audit_buddy
    b.paths.panels.write_text(json.dumps({"neural": [-50000, -50000]}), encoding="utf-8")
    b.floats.open("neural")
    rect = b.floats.windows["neural"].frameGeometry()
    assert any(screen.availableGeometry().intersects(rect) for screen in qa_qapp.screens())


def test_18_posicao_com_schema_errado_usa_padrao(audit_buddy):
    b = audit_buddy
    b.paths.panels.write_text('{"notebook":"x"}', encoding="utf-8")
    w = FloatingWidget(b, "notebook", "Teste", (100, 100), (50, 50), (10, 10))
    assert w.x() == 10 and w.y() == 10


def test_19_estado_de_castigo_invalido_nao_impede_criacao(audit_buddy):
    b = audit_buddy
    b.pet_paths.base.mkdir(parents=True, exist_ok=True)
    b.pet_paths.castigo.write_text('{"vitorias":{"fugir":"erro"}}', encoding="utf-8")
    controller = CastigoController(b, lambda: False)
    assert controller.vitorias["fugir"] == 0


def test_20_estado_de_protesto_invalido_nao_impede_carga(audit_buddy):
    b = audit_buddy
    b.pet_paths.base.mkdir(parents=True, exist_ok=True)
    b.pet_paths.protest.write_text('{"grievance":"erro"}', encoding="utf-8")
    state = Protesto(b.conteudo.signs, b.pet_paths.protest)
    state.load(b.prof)
    assert state.grievance == 0


def test_21_definicao_de_pet_com_seed_invalida_usa_padrao(audit_buddy):
    b = audit_buddy
    b.paths.pets.mkdir()
    (b.paths.pets / "ruim.json").write_text('{"seed":"invalida"}', encoding="utf-8")
    pet = config.load_pet(b.paths, "ruim")
    brain = LIFBrain(seed=pet["seed"])
    assert brain.seed == config.DEFAULT_PET["seed"]


def test_22_linha_com_utf8_invalido_nao_derruba_memoria(tmp_path):
    episodes = tmp_path / "episodes.jsonl"
    episodes.write_bytes(b'\xff\xfe\n')
    memory = EpisodicMemory(episodes, tmp_path / "prefs.json")
    memory.load()
    assert memory.recent == []


def test_23_valencia_textual_validada_e_normalizada_antes_de_consolidar(tmp_path):
    episodes = tmp_path / "episodes.jsonl"
    episodes.write_text('{"contexto":"IDLE|feliz","acao":"nada","valencia":"0.5"}\n', encoding="utf-8")
    memory = EpisodicMemory(episodes, tmp_path / "prefs.json")
    memory.load()
    memory.consolidate()


def test_24_contagem_infinita_nao_produz_estimativa_nan(tmp_path):
    prefs = tmp_path / "prefs.json"
    prefs.write_text('{"tabela":{"X":{"nada":[1e400,0.5]}},"geral":{}}', encoding="utf-8")
    memory = EpisodicMemory(tmp_path / "episodes.jsonl", prefs)
    memory.load()
    import math
    assert math.isfinite(memory.estimate("X", "nada"))


def test_25_integracao_nao_perde_tempo_em_callback_atrasado(audit_buddy, monkeypatch):
    b = audit_buddy
    now = time.monotonic()
    b.think()
    before = b.brain.time_ms
    monkeypatch.setattr(time, "monotonic", lambda: now + 1.)
    b.think()
    assert b.brain.time_ms - before == pytest.approx(1000, abs=1)


def test_26_apagar_historico_descarta_minuto_anterior_em_ram(audit_buddy, monkeypatch):
    b = audit_buddy
    b.timeline.seconds = 40
    b.timeline.activity = Counter(PROGRAMMING=40)
    b.open_settings()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    b.settings._wipe_history()
    b.timeline.flush()
    assert not b.paths.timeline.exists()


def test_27_revogar_travessuras_recolhe_objetos_ja_exibidos(audit_buddy):
    from pestinha.world.objetos import NoteThing
    b = audit_buddy
    note = NoteThing("Teste")
    b.mischief._add(note)
    b.apply_perms(dict(b.perms, travessuras=False))
    assert not note.isVisible()


def test_28_rotina_desligada_nao_acumula_emocoes_para_proximo_minuto(audit_buddy):
    b = audit_buddy
    assert b.perms["rotina"] is False
    b.think()
    assert sum(b.timeline.emotion.values()) == 0


def test_29_levantamento_de_janelas_nao_le_titulos(monkeypatch):
    import sys
    if sys.platform != "win32":
        pytest.skip("caminho específico do Windows (plataforma/windows.py)")
    from pestinha.plataforma import windows as win_mod
    monkeypatch.setattr(win_mod.win32gui, "EnumWindows", lambda cb, arg: cb(1, arg))
    monkeypatch.setattr(win_mod.win32gui, "IsWindowVisible", lambda hwnd: True)
    monkeypatch.setattr(win_mod.win32gui, "IsIconic", lambda hwnd: False)
    title = Mock(return_value="Título de documento privado")
    monkeypatch.setattr(win_mod.win32gui, "GetWindowText", title)
    monkeypatch.setattr(win_mod.win32gui, "GetClassName", lambda hwnd: "App")
    monkeypatch.setattr(win_mod.win32gui, "GetWindowLong", lambda *args: 0)
    monkeypatch.setattr(win_mod.win32gui, "GetWindow", lambda *args: 0)
    monkeypatch.setattr(win_mod, "_is_cloaked", lambda hwnd: False)
    monkeypatch.setattr(win_mod, "_frame_rect", lambda hwnd: (100, 100, 500, 500))
    win_mod.janelas_visiveis(set())
    title.assert_not_called()


def test_30_janela_que_sumiu_no_meio_da_leitura_degrada_para_desconhecida(monkeypatch):
    import sys
    if sys.platform != "win32":
        pytest.skip("caminho específico do Windows (plataforma/windows.py)")
    import pywintypes
    from pestinha.plataforma import windows as win_mod
    monkeypatch.setattr(win_mod.win32gui, "GetForegroundWindow", lambda: 123)
    monkeypatch.setattr(win_mod.win32process, "GetWindowThreadProcessId",
                        Mock(side_effect=pywintypes.error(1400, "GetWindowThreadProcessId", "Janela inválida")))
    assert win_mod.processo_ativo() == "unknown.exe"
