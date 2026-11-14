"""100 cenários explícitos do cantinho. Sem XFAIL e sem memória pessoal.

python -m pytest tests/test_cantinho_cenarios.py -q
Os atributos obtido/esperado ficam no JUnit via record_property.
"""
import os
import sys
import json
import math
import random
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from pestinha import config, log as log_module  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.body.behavior import Behavior  # noqa: E402
from pestinha.core.physics import Body  # noqa: E402
from pestinha.mind.castigo_ctl import CastigoController, LIMIAR_FUGA_HZ  # noqa: E402

BOUNDS = (0, 0, 1000, 700)
GROUPS = {
    "entrada": ["soltar_chao_centro", "soltar_no_ar_e_pousar", "andar_sem_soltar", "fora_esquerda", "fora_direita", "acima_zona", "abaixo_zona", "limite_esquerdo", "limite_direito", "opcao_desligada"],
    "saida": ["sair_esquerda", "sair_direita", "sair_acima", "sair_abaixo", "pegar_no_mouse", "desligar_opcao", "pausar_controlador", "permanecer_dentro", "mover_placa_para_longe", "ficar_no_ar"],
    "olhar": ["neutro", "watch_abaixo_limiar", "watch_no_limiar", "cursor_esquerda", "cursor_acima", "cursor_abaixo", "angry_abaixo_limiar", "angry_no_limiar", "raiva_prioritaria", "raiva_canto_direito"],
    "cartazes": ["motor_zero", "sorteio_sem_cartaz", "sorteio_com_cartaz", "motor_alto_com_cartaz", "motor_alto_sem_sorte", "intervalo_zero", "posicao_ao_nascer", "substituir_cartaz", "desligar_remove_cartaz", "acompanhar_pet"],
    "iniciar_fuga": ["motor_zero", "abaixo_limiar", "no_limiar", "acima_limiar", "opcao_desligada", "ainda_fora", "sendo_segurado", "pet_voando", "libera_estado", "direcao_sobrevive_ao_comportamento"],
    "concluir_fuga": ["ainda_dentro", "na_margem", "alem_margem", "muito_longe", "saida_esquerda", "prazo_expirado_fora", "prazo_expirado_dentro", "usuario_carregou", "placa_moveu_pet_parado", "nao_contar_duas_vezes"],
    "persistencia": ["sem_arquivo", "zero", "uma_fuga", "quatro_fugas", "cinco_fugas", "numero_negativo", "texto_invalido", "nan", "acima_dominio", "falha_de_disco_na_fuga"],
    "sessao": ["panico", "esconder", "tela_cheia", "desligar_app", "pausar", "retomar", "mostrar_de_novo", "desligar_cantinho", "modo_teste", "dormindo_nao_foge"],
    "prioridades": ["sem_protesto", "reclamacao", "manifestacao", "greve", "revolucao", "motor_canto", "missao_antiga", "dormindo", "carinho", "no_notebook"],
    "rede": ["preso_ativo", "livre", "opcao_desligada", "memoria_zero", "memoria_uma", "memoria_quatro", "memoria_cinco", "memoria_saturada", "apos_fuga_salva", "apos_esconder"],
}
SCENARIOS = [dict(id=i * 10 + j + 1, group=g, name=name, variant=j)
             for i, (g, names) in enumerate(GROUPS.items()) for j, name in enumerate(names)]
assert len(SCENARIOS) == 100


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def scene(qt_app, tmp_path, monkeypatch, request):
    case = request.param
    before = set(qt_app.topLevelWidgets())
    random.seed(1000 + case["id"])
    if case["group"] in ("sessao", "rede"):
        monkeypatch.setattr("pestinha.app.PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
        monkeypatch.setattr("pestinha.app.senses.get_active_app", lambda: "code.exe")
        monkeypatch.setattr("pestinha.app.senses.get_idle_seconds", lambda: 0.)
        monkeypatch.setattr("pestinha.app.senses.is_fullscreen", lambda: False)
        monkeypatch.setattr("pestinha.app.senses.list_windows", lambda exclude, *args, **kwargs: [])
        store = SettingsStore(Paths(tmp_path))
        store.update(dict(config.DEFAULT_PERMISSIONS, rotina=False, travessuras=False))
        app = PestinhaApp(store, Paths(tmp_path))
        app.bounds = lambda: BOUNDS
        app.brain.rng = np.random.default_rng(42)
        for timer in app.findChildren(QTimer):
            timer.stop()
        body, state, behavior = app.pet.body, app.pet_state, app.behavior
        c = app.castigo
    else:
        state = PetState()
        body = Body(100, 600, 30, 35)
        behavior = Behavior(body, state, Mock())
        app = SimpleNamespace(paths=Paths(tmp_path), pet_paths=Paths(tmp_path).pet("bryan"), conteudo=Paths(tmp_path).conteudo("bryan"),
                              behavior=behavior, pet=SimpleNamespace(raise_=Mock()))
        c = CastigoController(app, lambda: False)
    body.x, body.y = 100, 600
    body.vx = body.vy = 0.
    body.grounded, body.held = True, False
    body.angle = 0.
    behavior.next_roam = 1e12
    c.toggle(BOUNDS)
    c.plaquinha.move(0, 550)
    value = SimpleNamespace(c=c, app=app, body=body, state=state, behavior=behavior, case=case)
    yield value
    for widget in set(qt_app.topLevelWidgets()) - before:
        for timer in widget.findChildren(QTimer):
            timer.stop()
        widget.close()
    log_module.desligar_arquivo()


def enter(s, now=0.):
    s.body.held = True
    s.c.act(now, s.body, BOUNDS, (500, 500), s.state, {})
    s.body.held = False
    s.c.act(now + .1, s.body, BOUNDS, (500, 500), s.state, {})


def tick(s, now=1., motors=None):
    s.c.act(now, s.body, BOUNDS, (500, 500), s.state, motors or {})


def take(s):
    c = s.c
    return dict(dentro=c.dentro, marcado=s.state.castigo, ativo=c.ativo,
                fuga=c.fuga, vitorias=c.vitorias["fugir"], memoria=c.memoria_fuga(),
                vx=round(s.body.vx, 5), posicao=[round(s.body.x, 4), round(s.body.y, 4)],
                cartaz=c.cartaz is not None, placa_visivel=c.plaquinha.isVisible(),
                cartaz_posicao=[round(c.cartaz.x, 4), round(c.cartaz.y, 4)] if c.cartaz else None,
                memoria_gravada=c.path.exists())


def result(observed, expected):
    return observed, expected


def scenario_entry(s, i, monkeypatch):
    expected = i in (0, 1, 7, 8)
    if i == 2:
        tick(s)
    else:
        if i == 3: s.body.x = -1
        if i == 4: s.body.x = 191
        if i == 5: s.body.y = 459
        if i == 6: s.body.y = 701
        if i == 7: s.body.x = 0
        if i == 8: s.body.x = 190
        if i == 9: s.c.toggle(BOUNDS)
        if i == 1: s.body.grounded = False
        enter(s)
        if i == 1:
            s.body.grounded = True
            tick(s, .3)
    return result(s.c.dentro, expected)


def scenario_exit(s, i, monkeypatch):
    enter(s)
    if i == 0: s.body.x = -1
    if i == 1: s.body.x = 191
    if i == 2: s.body.y = 459
    if i == 3: s.body.y = 701
    if i == 4: s.body.held = True
    if i == 5: s.c.toggle(BOUNDS)
    if i == 6: s.c.pausar(s.state)
    if i == 8: s.c.plaquinha.move(500, 550)
    if i == 9: s.body.grounded = False
    if i not in (5, 6): tick(s)
    return result([s.c.dentro, s.state.castigo], [i == 7, i == 7])


def scenario_gaze(s, i, monkeypatch):
    cursor = (500, 500)
    motors = {}
    expected = (0., .9)
    if i == 1: motors = {"WATCH": 2.99}
    if i in (2, 3, 4, 5):
        motors = {"WATCH": 3. if i == 2 else 8.}
        cursor = {2: (500, 500), 3: (0, 600), 4: (100, 400), 5: (100, 700)}[i]
        dx, dy = cursor[0] - s.body.x, cursor[1] - s.body.y
        distance = math.hypot(dx, dy)
        expected = (dx / distance, dy / distance)
    if i == 6: motors = {"ANGRY": 2.99}
    if i in (7, 8, 9):
        motors = {"ANGRY": 3. if i == 7 else 7., "WATCH": 7. if i == 8 else 0.}
        expected = (-1., 0.)
    if i == 9:
        s.c.plaquinha.move(800, 550)
        s.body.x = 850
        expected = (1., 0.)
    s.c._aplicar(s.body, cursor, s.state, BOUNDS, motors)
    return result(tuple(round(x, 6) for x in s.state.gaze), tuple(round(x, 6) for x in expected))


def spawn(s, monkeypatch, now=1.):
    monkeypatch.setattr("pestinha.mind.castigo_ctl.random.random", lambda: 0.)
    tick(s, now, {"CARTAZ": 100})


def scenario_signs(s, i, monkeypatch):
    enter(s)
    if i < 6:
        hz, draw, now, expected = [(0, .5, 1, False), (2, .999, 1, False),
                                  (2, 0., 1, True), (10, .3, .2, True),
                                  (10, .9, .2, False), (100, 0., .1, False)][i]
        # GANHO_CARTAZ passou de 0,05 para 0,5: o disparo de 100 Hz virou 10 Hz para manter a mesma chance
        monkeypatch.setattr("pestinha.mind.castigo_ctl.random.random", lambda: draw)
        tick(s, now, {"CARTAZ": hz})
        return result(s.c.cartaz is not None, expected)
    spawn(s, monkeypatch)
    if i == 6:
        sign = s.c.cartaz
        return result([sign.x == s.body.x, sign.y < s.body.y and sign.y > 400], [True, True])
    if i == 7:
        first = s.c.cartaz
        spawn(s, monkeypatch, 10)        # contrato novo: cada cartaz fica pelo menos 8 s antes de trocar
        return result([s.c.cartaz is not first, first.isVisible()], [True, False])
    if i == 8:
        s.c.toggle(BOUNDS)
        return result(s.c.cartaz is None, True)
    s.body.x = 150
    tick(s, 1.1)
    return result(s.c.cartaz.x, 150)


def scenario_escape_start(s, i, monkeypatch):
    if i != 5: enter(s)
    if i == 4: s.c.toggle(BOUNDS)
    if i == 6: s.body.held = True
    if i == 7: s.body.grounded = False
    hz = 0 if i == 0 else LIMIAR_FUGA_HZ - .001 if i == 1 else LIMIAR_FUGA_HZ if i == 2 else 10.
    # contrato novo: a fuga sai da vontade acumulada (FUGIR acima do limiar ao longo do tempo).
    # Aqui a vontade já está quase cheia; um tick acima do limiar completa, no limiar não acumula.
    s.c.vontade_fuga = 0.999
    tick(s, 1., {"FUGIR": hz})
    if i == 8:
        return result([s.c.fuga is not None, s.c.dentro, s.state.castigo, s.body.vx > 0], [True, False, False, True])
    if i == 9:
        s.behavior.target_x = -500
        s.behavior.next_roam = 1e12
        s.behavior.tick(.016, 1.016, (500, 500), BOUNDS, config.PROFILES["normal"])
        return result(s.body.vx > 0, True)
    return result(s.c.fuga is not None, i == 3)


def scenario_escape_end(s, i, monkeypatch):
    s.c.fuga = 0.
    s.body.x = [100, 230, 231, 900, -100, 231, 100, 300, 100, 300][i]
    now = 31. if i in (5, 6) else 1.
    if i == 7: s.body.held = True
    if i == 8:
        s.c.plaquinha.move(-500, 550)
    # Exercita o caminho público do quadro, que verifica a fuga antes da posse.
    tick(s, now)
    if i == 9: s.c._checar_fuga(2, s.body)
    expected = 1. if i in (2, 3, 9) else 0.
    return result(s.c.vitorias["fugir"], expected)


def scenario_persistence(s, i, monkeypatch):
    if i == 9:
        monkeypatch.setattr("pestinha.mind.castigo_ctl.write_json", Mock(side_effect=PermissionError("disco indisponível")))
        s.c.fuga = 0.
        s.body.x = 300
        try:
            s.c._checar_fuga(1, s.body)
            error = None
        except OSError as exc:
            error = type(exc).__name__
        return result(error, None)
    values = [None, 0, 1, 4, 5, -1, "erro", float("nan"), 1e12]
    value = values[i]
    if i:
        s.c.path.parent.mkdir(parents=True, exist_ok=True)
        s.c.path.write_text(json.dumps({"vitorias": {"fugir": value}}), encoding="utf-8")
    restored = CastigoController(s.app, lambda: False)
    wanted = float(value) if i in (1, 2, 3, 4) else 0.
    return result([restored.vitorias["fugir"], restored.memoria_fuga()], [wanted, min(1., wanted * .2)])


def scenario_session(s, i, monkeypatch):
    b = s.app
    enter(s, time.monotonic())
    if i == 0: b.panic()
    if i == 1:
        b.hidden = True
        b.update_visibility()
    if i == 2:
        b.fullscreen = True
        b.update_visibility()
    if i == 3: b.apply_perms(dict(b.perms, ativo=False))
    if i == 4:
        b.toggle_pause()
        before = b.brain.time_ms
        b.think()
        return result([b.brain.time_ms == before, s.c.dentro], [True, True])
    if i == 5:
        b.toggle_pause()
        b.toggle_pause()
        return result([b.paused, s.c.dentro], [False, True])
    if i == 6:
        b.hidden = True
        b.update_visibility()
        b.hidden = False
        b.update_visibility()
        return result([s.c.dentro, s.c.plaquinha.isVisible()], [False, True])
    if i == 7: s.c.toggle(BOUNDS)
    if i == 8:
        b.apply_perms(dict(b.perms, modo_teste=True))
        return result(s.c.dentro, True)
    if i == 9:
        b.sleep.asleep = True
        b.pet_state.emotion = "dormindo"
        b.behavior.emotion = "dormindo"
        s.body.y = 700 - s.body.extents()[1]
        rates = {motor: 0. for motor in b.brain.motor_names}
        rates["FUGIR"] = 10.
        monkeypatch.setattr(b.brain, "motor_activity", lambda: rates)
        b.last_frame = time.monotonic() - .016
        b.frame()
        return result([s.c.dentro, s.body.vx], [True, 0.])
    return result([s.c.dentro, s.state.castigo, s.c.cartaz is None, s.c.plaquinha.isVisible()], [False, False, True, False])


def scenario_priority(s, i, monkeypatch):
    # Longe o bastante da borda para revelar movimento, ainda dentro da placa.
    s.body.x = 150
    enter(s)
    s.state.protest_stage = i if i < 5 else 0
    if i == 5: s.behavior.canto = True
    if i == 6: s.behavior.mission = ("cross", 900, 100)
    if i == 7: s.behavior.emotion = "dormindo"
    if i == 8: s.state.mark_caress(1.)
    if i == 9: s.state.at_desk = True
    s.behavior.tick(.016, 1., (500, 500), BOUNDS, config.PROFILES["normal"])
    return result(s.body.vx, 0.)


def scenario_neural(s, i, monkeypatch):
    b = s.app
    if i in (0, 2): enter(s, time.monotonic())
    if i == 2: s.c.toggle(BOUNDS)
    if i in (3, 4, 5, 6, 7): s.c.vitorias["fugir"] = [0, 1, 4, 5, 100][i - 3]
    if i == 8:
        enter(s, time.monotonic())
        s.c._iniciar_fuga(time.monotonic(), BOUNDS)
        s.body.x = 300
        s.c._checar_fuga(time.monotonic() + 1, s.body)
    if i == 9:
        enter(s, time.monotonic())
        b.hidden = True
        b.update_visibility()
    b.think()
    if i in (0, 1, 2, 9):
        return result(b.intensities["PRESO"], 1. if i == 0 else 0.)
    if i == 8:
        return result([b.intensities["PRESO"], b.intensities["LEMBRA_FUGA"], s.c.path.exists()], [0., .2, True])
    return result(b.intensities["LEMBRA_FUGA"], [0., .2, .8, 1., 1.][i - 3])


RUNNERS = dict(entrada=scenario_entry, saida=scenario_exit, olhar=scenario_gaze,
               cartazes=scenario_signs, iniciar_fuga=scenario_escape_start,
               concluir_fuga=scenario_escape_end, persistencia=scenario_persistence,
               sessao=scenario_session, prioridades=scenario_priority, rede=scenario_neural)


@pytest.mark.parametrize("scene", SCENARIOS,
                         ids=[f"{c['id']:03d}-{c['group']}-{c['name']}" for c in SCENARIOS], indirect=True)
def test_cenario_cantinho(scene, monkeypatch, record_property):
    case = scene.case
    observed, expected = RUNNERS[case["group"]](scene, case["variant"], monkeypatch)
    record_property("cenario", json.dumps(case, ensure_ascii=False))
    record_property("observado", json.dumps(observed, ensure_ascii=False))
    record_property("esperado", json.dumps(expected, ensure_ascii=False))
    record_property("estado_final", json.dumps(take(scene), ensure_ascii=False))
    assert observed == expected, dict(cenario=case, observado=observed, esperado=expected)
