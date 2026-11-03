"""Regressão dos 30 bugs encontrados na rodada de fuzzing e revisão (docs/auditorias/BUGS_30_RODADA.md)."""
import json
import math
import re
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402


@pytest.fixture
def mundo(monkeypatch):
    qt = QApplication.instance() or QApplication([])
    import pestinha.app as app_mod
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    monkeypatch.setattr(app_mod.senses, "list_windows", lambda exclude, escala=1.0: [])
    monkeypatch.setattr(app_mod.senses, "get_active_app", lambda: "explorer.exe")
    monkeypatch.setattr(app_mod.senses, "get_idle_seconds", lambda: 1.0)
    monkeypatch.setattr(app_mod.senses, "is_fullscreen", lambda: False)
    monkeypatch.setattr(QApplication, "quit", lambda *a: None)
    relogio = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: relogio[0])
    paths = Paths(root=Path(tempfile.mkdtemp()))
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, travessuras=True))
    b = app_mod.PestinhaApp(store, paths)
    for timer in b.findChildren(app_mod.QTimer):
        timer.stop()

    def rodar(segundos):
        for _ in range(max(1, int(segundos / 0.1))):
            relogio[0] += 0.1
            b.think()
            b.frame()
        qt.processEvents()

    def segurar():
        b.pet._dragging = True
        b.pet.body.held = True
        b.pet.drag_started.emit()

    def preso():
        b.castigo.toggle(b.bounds())
        g = b.castigo.plaquinha.geometry()
        segurar()
        b.pet.body.x, b.pet.body.y = g.center().x(), g.y() - 120
        rodar(0.1)
        b.pet._dragging, b.pet.body.held = False, False
        b.pet.drag_ended.emit()
        rodar(3.0)
        assert b.castigo.dentro

    return SimpleNamespace(b=b, rodar=rodar, segurar=segurar, preso=preso, relogio=relogio)


# 01
def test_01_ligar_cantinho_escondido_nao_mostra_placa(mundo):
    mundo.b.toggle_hidden()
    mundo.b.castigo.toggle(mundo.b.bounds())
    assert not mundo.b.castigo.plaquinha.isVisible()
    mundo.b.toggle_hidden()
    assert mundo.b.castigo.plaquinha.isVisible()


# 02
def test_02_esconder_notebook_pausado_levanta(mundo):
    b = mundo.b
    b.mesa.decisao.at_desk = True
    b.toggle_pause()
    b.menu_alternar_notebook()
    assert not b.mesa.sentado and b.pet_state.desk_top is None


# 03
def test_03_esconder_no_meio_do_arraste_solta(mundo):
    mundo.segurar()
    mundo.b.toggle_hidden()
    assert not mundo.b.pet.body.held and not mundo.b.senses.dragging


# 04
def test_04_panico_no_meio_do_arraste_desliga_sinal(mundo):
    mundo.segurar()
    mundo.b.panic()
    assert not mundo.b.senses.dragging


# 05
def test_05_guardar_bolinha_no_meio_do_arraste_larga(mundo):
    mundo.b.ball.dragging = True
    mundo.b.menu_store_ball()
    assert not mundo.b.ball.dragging


# 06
def test_06_abrir_painel_com_bandeja_escondida_fica_aberto(mundo):
    b = mundo.b
    b.toggle_floating()
    b.floats.open("neural")
    b.update_visibility()
    assert b.floats.window("neural").isVisible()


# 07
def test_07_pedido_impossivel_nao_e_recusa(mundo):
    b = mundo.b
    mundo.preso()
    b.menu_pedir_trabalho()
    pulsos = []
    for _ in range(70):
        mundo.rodar(1.0)
        pulsos.append(b.intensities.get("RECUSA", 0.0))
    assert max(pulsos) == 0


# 08
def test_08_travessura_forcada_vence(mundo):
    b = mundo.b
    mundo.preso()
    b.menu_mischief()
    mundo.rodar(15.0)
    b.castigo.toggle(b.bounds())
    r = b.mischief_ctl.maybe_act(time.monotonic(), 0.016, b.bounds(), (0, 0), b.pet.body,
                                 motores={"TRAVESSURA": 0}, activity="IDLE", emotion="curioso", perms=b.perms,
                                 prof=b.prof, fullscreen=False, asleep=False, protest_stage=0)
    assert r is None and not b.mischief_ctl.pedido_forcado


# 09
def test_09_queda_alta_ainda_ensina_a_placa():
    from pestinha.core.conditioning import Conditioning
    c = Conditioning(rate=0.5)
    c.set_cue("PLACA", True, 0.0)
    c.set_cue("PLACA", False, 1.0)
    c.outcome(3.5, cues=("PLACA",))
    c.tick(10.0)
    assert c.V["PLACA"] > 0


# 10
def test_10_apagar_dados_e_rodar_um_quadro_nao_recria_pasta(mundo):
    b = mundo.b
    b.castigo.toggle(b.bounds())
    b.castigo.fuga = time.monotonic()
    b.castigo.zona_fuga = (-1000, -900)
    b.wipe_all_data()
    b.frame()
    assert not b.paths.memory.exists()


# 11
def test_11_painel_so_solta_com_o_botao_que_arrastou(mundo):
    from pestinha.world.arrastavel import FloatingWidget
    w = FloatingWidget(mundo.b, "teste", "t", (100, 100), (50, 50), (10, 10))
    w._grab, w._botao = object(), Qt.LeftButton
    w.mouseReleaseEvent(SimpleNamespace(button=lambda: Qt.RightButton))
    assert w._grab is not None


# 12
def test_12_monitor_tem_rotulo_em_portugues_para_tudo():
    from pestinha.core.nervous_system import MOTOR_SPEC, SENSORY_SPEC
    from pestinha.ui.rotulos import CANAIS_SENSORIAIS, MOTORES
    assert all(c in CANAIS_SENSORIAIS for c in SENSORY_SPEC)
    assert all(m[0] in MOTORES for m in MOTOR_SPEC)


# 13
def test_13_foco_maximo_tem_uma_fonte_so():
    import pestinha.ajustes as aj
    import pestinha.mind.mesa as mesa
    assert mesa.FOCO_MAXIMO_HZ is aj.FOCO_MAXIMO_HZ


# 14
def test_14_ajustes_sem_constante_morta():
    texto = (ROOT / "pestinha" / "ajustes.py").read_text(encoding="utf-8")
    codigo = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "pestinha").rglob("*.py") if p.name != "ajustes.py")
    mortas = [n for n in re.findall(r"^([A-Z][A-Z_]*) = ", texto, flags=re.M) if n not in codigo]
    assert mortas == []


# 15-21: tudo integra pelo tempo real
def test_15_a_21_ciclo_lento_integra_o_mesmo_que_ciclos_rapidos(mundo, monkeypatch):
    b = mundo.b
    chamadas = {}
    for nome, alvo in (("tom", b.pet_state.tone), ("emoção", b.emotion)):
        original = alvo.update
        monkeypatch.setattr(alvo, "update", lambda *a, _o=original, _n=nome, **k: (chamadas.setdefault(_n, a[1]), _o(*a, **k))[1])
    for nome, alvo in (("protesto", b.protest_ctl), ("tristeza", b.sad_ctl)):
        original = alvo.tick
        monkeypatch.setattr(alvo, "tick", lambda *a, _o=original, _n=nome, **k: (chamadas.setdefault(_n, a[0]), _o(*a, **k))[1])
    original_learn = b.brain.learn
    monkeypatch.setattr(b.brain, "learn", lambda r, dt, rate: (chamadas.setdefault("aprendizado", dt), original_learn(r, dt, rate))[1])
    original_festa = b.festa.tick
    monkeypatch.setattr(b.festa, "tick", lambda *a: (chamadas.setdefault("euforia", a[5]), original_festa(*a))[1])
    b.think()
    mundo.relogio[0] += 1.0
    chamadas.clear()
    b.think()
    assert chamadas and all(v == pytest.approx(1.0) for v in chamadas.values()), chamadas


def test_18_carinho_estimula_por_segundo(mundo, monkeypatch):
    b = mundo.b
    escalas = []
    monkeypatch.setattr(b.drives, "stimulate", lambda kind, scale=1.0: escalas.append(scale))
    monkeypatch.setattr(b.pet_state, "caressing", lambda now=None: True)
    b.think()
    mundo.relogio[0] += 1.0
    escalas.clear()
    b.think()
    assert escalas and escalas[0] == pytest.approx(1.0)


# 22
def test_22_imagem_ilegivel_nao_vira_travessura(mundo, tmp_path):
    b = mundo.b
    pasta = b.conteudo.memes / "curioso"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "quebrado.png").write_text("não sou uma imagem", encoding="utf-8")
    assert b.mischief._make("meme", "curioso", small=False) is None


# 23/24
def test_23_tela_inicial_grava_a_escolha(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    import main as main_mod
    from pestinha.ui import ui as ui_mod
    paths = Paths(root=tmp_path)
    escolha = not config.DEFAULT_PERMISSIONS["fogos"]

    class Dialogo(ui_mod.SettingsDialog):
        def exec(self):
            self._set("fogos", escolha)
            return 1

    monkeypatch.setattr(main_mod, "SettingsDialog", Dialogo)
    monkeypatch.setattr(main_mod, "Paths", lambda: paths)
    monkeypatch.setattr(main_mod, "PestinhaApp", lambda store, p: None)
    monkeypatch.setattr(main_mod, "Onboarding", lambda nome: SimpleNamespace(exec=lambda: 1))
    monkeypatch.setattr(main_mod, "QApplication", lambda argv: SimpleNamespace(
        setQuitOnLastWindowClosed=lambda v: None, setWindowIcon=lambda i: None, exec=lambda: 0))
    monkeypatch.setattr(sys, "argv", ["main.py"])
    main_mod.main()
    assert json.loads(paths.permissions.read_text(encoding="utf-8"))["fogos"] is escolha


def test_24_tela_inicial_apagar_tudo_funciona(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    import main as main_mod
    from pestinha.ui import ui as ui_mod
    paths = Paths(root=tmp_path)
    paths.memory.mkdir(parents=True)
    (paths.memory / "algo.json").write_text("{}", encoding="utf-8")

    class Dialogo(ui_mod.SettingsDialog):
        def exec(self):
            self.wipe_all.emit()
            return 0

    monkeypatch.setattr(main_mod, "SettingsDialog", Dialogo)
    monkeypatch.setattr(main_mod, "Paths", lambda: paths)
    monkeypatch.setattr(main_mod, "Onboarding", lambda nome: SimpleNamespace(exec=lambda: 1))
    monkeypatch.setattr(main_mod, "QApplication", lambda argv: SimpleNamespace(
        setQuitOnLastWindowClosed=lambda v: None, setWindowIcon=lambda i: None, exec=lambda: 0))
    monkeypatch.setattr(sys, "argv", ["main.py"])
    assert main_mod.main() == 0
    assert not paths.memory.exists()


# 25
def test_25_interface_usa_o_nome_bryan():
    for arquivo in ("app.py", "ui/ui.py", "ui/onboarding.py", "ui/monitor.py", "ui/panel.py"):
        texto = (ROOT / "pestinha" / arquivo).read_text(encoding="utf-8")
        assert not re.search(r'"Pestinha', texto), arquivo


# 26
def test_26_resumo_conta_memes_de_trabalho_e_bilhetes_tristes(mundo):
    from pestinha.ui.ui import SettingsDialog
    b = mundo.b
    b.conteudo.memes_trabalho.mkdir(parents=True, exist_ok=True)
    (b.conteudo.memes_trabalho / "x.png").write_bytes(b"")
    b.conteudo.notes_sad.write_text("triste\n", encoding="utf-8")
    texto = SettingsDialog(b.perms, b.paths, first_run=False)._asset_summary().text()
    assert "1 de trabalho" in texto and "1 bilhetes tristes" in texto


# 27
def test_27_pausa_no_meio_da_fuga_nao_cancela(mundo):
    b = mundo.b
    mundo.preso()
    b.castigo._iniciar_fuga(time.monotonic(), b.bounds())
    b.toggle_pause()
    mundo.relogio[0] += 60
    b.toggle_pause()
    mundo.rodar(0.2)
    assert b.castigo.fuga is not None or b.castigo.vitorias["fugir"] > 0


# 28
def test_28_pausa_nao_vence_pedido(mundo):
    b = mundo.b
    b.menu_pedir_trabalho()
    b.toggle_pause()
    mundo.relogio[0] += 120
    b.toggle_pause()
    assert b.mesa.intensidade_pedido(time.monotonic()) > 0.9


# 29
def test_29_interacoes_pausadas_nao_mudam_estado(mundo):
    b = mundo.b
    b.toggle_pause()
    antes = (b.drives.stimulation, b.drives.contact, b.drives.energy, b.in_flight)
    b.pet.drag_started.emit()
    b.pet.thrown.emit(1500.0)
    b.menu_caress()
    b.menu_sleep()
    assert (b.drives.stimulation, b.drives.contact, b.drives.energy, b.in_flight) == antes


# 30
def test_30_cantinho_segue_a_placa_no_alto(mundo):
    b = mundo.b
    b.castigo.toggle(b.bounds())
    b.castigo.plaquinha.move(100, 200)                # placa no alto de uma janela
    g = b.castigo.plaquinha.geometry()
    corpo = SimpleNamespace(x=g.center().x(), y=g.bottom() - 20, grounded=True)
    assert b.castigo._no_canto(corpo, b.bounds())
    chao = SimpleNamespace(x=g.center().x(), y=b.bounds()[3] - 40, grounded=True)
    assert not b.castigo._no_canto(chao, b.bounds())
    assert math.isfinite(g.bottom())
