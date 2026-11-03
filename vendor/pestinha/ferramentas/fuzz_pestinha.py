"""
FUZZ - roda o app inteiro com relógio virtual e ações aleatórias, checando invariantes.

    python -B ferramentas/fuzz_pestinha.py [rodadas] [acoes_por_rodada]

Cada violação é agrupada pelo nome do invariante, com a primeira sequência que a causou.
Usa Qt sem janela e uma pasta temporária: não toca na memória pessoal do pet.
"""
import math
import os
import random
import sys
import tempfile
import time
import traceback
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QT = QApplication.instance() or QApplication([])
QT.setQuitOnLastWindowClosed(False)

import pestinha.app as A  # noqa: E402
from pestinha import config  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

A.PanicHotkey = lambda: SimpleNamespace(ok=True, pressed=Mock())
A.senses.list_windows = lambda exclude, *args, **kwargs: []
A.senses.is_fullscreen = lambda: False
QApplication.quit = lambda *a: None
RELOGIO = [1000.0]
_monotonic_real = time.monotonic
time.monotonic = lambda: RELOGIO[0]

PERMS_ALTERNAVEIS = ["bolinha", "fogos", "travessuras", "memes", "bilhetes", "carinho", "modo_teste",
                     "rotina", "arrastar", "cutucar", "tela_cheia"]


def novo_app(rng):
    A.senses.get_active_app = lambda: rng.choice(["code.exe", "chrome.exe", "explorer.exe", "discord.exe"])
    A.senses.get_idle_seconds = lambda: rng.choice([0.1, 2.0, 30.0])
    paths = Paths(root=Path(tempfile.mkdtemp()))
    paths.conteudo("bryan").proprio.mkdir(parents=True, exist_ok=True)
    paths.conteudo("bryan").notes.write_text("nota um\nnota dois\n", encoding="utf-8")
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, travessuras=True, rotina=True))
    b = A.PestinhaApp(store, paths)
    for t in b.findChildren(A.QTimer):
        t.stop()
    return b


def rodar(b, segundos):
    for _ in range(max(1, int(segundos / 0.1))):
        RELOGIO[0] += 0.1
        b.think()
        b.sense()
        b.frame()


# ---------------- ações ----------------

def soltar(b, rng, x=None, y=None, arremesso=False):
    body = b.pet.body
    b.pet._dragging = True
    body.held = True
    b.pet.drag_started.emit()
    lo, top, hi, bottom = b.bounds()
    body.x = x if x is not None else rng.uniform(lo + 30, hi - 30)
    body.y = y if y is not None else rng.uniform(top + 30, bottom - 60)
    rodar(b, 0.3)
    b.pet._dragging = False
    body.held = False
    if arremesso:
        body.vx, body.vy = rng.uniform(-2000, 2000), rng.uniform(-1500, 500)
    b.pet.drag_ended.emit()
    if arremesso:
        b.pet.thrown.emit(math.hypot(body.vx, body.vy))


def soltar_na_placa(b, rng):
    if b.castigo.plaquinha is None or not b.castigo.ativo:
        b.castigo.toggle(b.bounds())
    g = b.castigo.plaquinha.geometry()
    soltar(b, rng, g.center().x(), g.y() - 120)


ACOES = OrderedDict([
    ("rodar", lambda b, r: rodar(b, r.uniform(0.5, 8))),
    ("cutucar", lambda b, r: b.on_poke()),
    ("cutucar_menu", lambda b, r: b.menu_poke()),
    ("carinho", lambda b, r: b.menu_caress()),
    ("carinho_longo", lambda b, r: [b.pet_state.mark_caress() or rodar(b, 0.2) for _ in range(20)]),
    ("arrastar", lambda b, r: soltar(b, r)),
    ("arremessar", lambda b, r: soltar(b, r, arremesso=True)),
    ("soltar_na_placa", soltar_na_placa),
    ("castigo_toggle", lambda b, r: b.castigo.toggle(b.bounds())),
    ("mover_placa", lambda b, r: b.castigo.plaquinha and b.castigo.plaquinha.move(int(r.uniform(-50, 700)), int(r.uniform(0, 700)))),
    ("pausa", lambda b, r: b.toggle_pause()),
    ("panico", lambda b, r: b.panic()),
    ("religar", lambda b, r: b.apply_perms({"ativo": True})),
    ("esconder", lambda b, r: b.toggle_hidden()),
    ("fechar_menu", lambda b, r: b.menu_close()),
    ("perm", lambda b, r: b.apply_perms({(k := r.choice(PERMS_ALTERNAVEIS)): not b.perms[k]})),
    ("pedir_trabalho", lambda b, r: b.menu_pedir_trabalho()),
    ("notebook_toggle", lambda b, r: b.menu_alternar_notebook()),
    ("mover_notebook", lambda b, r: b.mesa.caderno.move(int(r.uniform(-50, 700)), int(r.uniform(0, 700)))),
    ("guardar_bola", lambda b, r: b.menu_store_ball()),
    ("pegar_bola", lambda b, r: b.menu_place_ball()),
    ("dormir", lambda b, r: b.menu_sleep()),
    ("travessura_agora", lambda b, r: b.menu_mischief()),
    ("limpar", lambda b, r: b.clear_things()),
    ("painel", lambda b, r: b.floats.toggle(r.choice(["neural", "greve"]))),
    ("revolta", lambda b, r: setattr(b.protest, "grievance", r.choice([0.0, 0.6, 1.3]))),
    ("tristeza", lambda b, r: setattr(b.sad, "grievance", r.choice([0.0, 0.6, 1.3]))),
    ("cansaco", lambda b, r: setattr(b.drives, "energy", r.choice([0.05, 0.5, 1.0]))),
    ("config", lambda b, r: (b.open_settings(), b.settings._set((k := r.choice(PERMS_ALTERNAVEIS)), not b.settings.perms[k]))),
    ("salvar", lambda b, r: b.save()),
    ("bola_no_pet", lambda b, r: (setattr(b.ball.body, "x", b.pet.body.x), setattr(b.ball.body, "y", b.pet.body.y))),
])


# ---------------- invariantes ----------------

def _visivel(w):
    try:
        return w is not None and w.isVisible()
    except RuntimeError:          # objeto Qt já apagado
        return False


def invariantes(b):
    falhas = []

    def checa(nome, ok):
        if not ok:
            falhas.append(nome)

    body = b.pet.body
    ativo_e_visivel = b.perms["ativo"] and not b.hidden
    st = b.pet_state
    checa("I01 castigo do estado = castigo do controlador", st.castigo == b.castigo.dentro)
    checa("I02 preso só com cantinho ativo", not b.castigo.dentro or b.castigo.ativo)
    if not ativo_e_visivel:
        checa("I03 desligado/escondido: pet invisível", not b.pet.isVisible())
        checa("I04 desligado/escondido: objetos de travessura invisíveis", not any(_visivel(t) for t in b.mischief.things))
        checa("I05 desligado/escondido: placa invisível", not _visivel(b.castigo.plaquinha))
        checa("I06 desligado/escondido: notebook invisível", not _visivel(b.mesa.caderno))
        checa("I07 desligado/escondido: painéis invisíveis", not any(_visivel(w) for w in b.floats.windows.values()))
        checa("I08 desligado/escondido: fogos invisíveis", not _visivel(b.festa.fogos))
        checa("I09 desligado/escondido: cartazes de protesto invisíveis",
              not _visivel(b.protest.sign) and not _visivel(b.sad.sign))
        checa("I10 desligado/escondido: bolinha invisível", not _visivel(b.ball))
        checa("I11 desligado/escondido: cartaz do castigo invisível", not _visivel(b.castigo.cartaz))
        checa("I12 desligado/escondido: bolinhas de papel invisíveis", not any(_visivel(w) for w in b.revolucao.janelas()))
    checa("I13 corpo com coordenadas finitas", all(math.isfinite(v) for v in (body.x, body.y, body.vx, body.vy, body.angle)))
    lo, top, hi, bottom = b.bounds()
    checa("I14 corpo dentro da área (com folga)", lo - 300 <= body.x <= hi + 300 and top - 500 <= body.y <= bottom + 300)
    checa("I15 não fica sentado e preso ao mesmo tempo", not (b.mesa.sentado and b.castigo.dentro))
    checa("I16 destino de fuga só com fuga em andamento", b.behavior.fuga_alvo is None or b.castigo.fuga is not None)
    vals = list(b.intensities.values())
    checa("I17 sinais da rede finitos em [0, 1]", all(isinstance(v, (int, float)) and math.isfinite(v) and -1e-9 <= v <= 1 + 1e-9 for v in vals))
    d = b.drives
    checa("I18 homeostase em [0, 1]", all(math.isfinite(v) and 0 <= v <= 1 for v in (d.energy, d.stimulation, d.contact)))
    checa("I19 pesos da rede finitos", bool(np.isfinite(b.brain.W).all()) and bool(np.isfinite(b.brain.pool_rate).all()))
    if b.ball_stored or not b.perms["bolinha"]:
        checa("I20 bolinha guardada/desligada invisível", not _visivel(b.ball))
    if b.castigo.dentro:
        checa("I21 preso: sem cartaz de protesto", b.protest.sign is None and b.sad.sign is None)
    if not b.perms["travessuras"]:
        checa("I22 travessuras desligadas: nenhum objeto", not b.mischief.things)
    if not b.perms["fogos"]:
        checa("I23 fogos desligados: sem fogos", not _visivel(b.festa.fogos))
    checa("I24 sinal de arraste só segurado", not b.senses.dragging or body.held)
    checa("I25 altura da tampa só sentado", st.desk_top is None or b.mesa.sentado)
    checa("I26 cartaz do castigo só preso", b.castigo.cartaz is None or b.castigo.dentro)
    checa("I27 notebook escondido: não senta", not (b.mesa.escondido and b.mesa.sentado))
    checa("I28 missão aponta para objeto existente",
          not (b.behavior.mission and b.behavior.mission[0] == "deliver") or b.behavior.mission[1] in b.mischief.things)
    if b.paused:
        t = b.brain.time_ms
        b.think()
        checa("I29 pausado: a rede não avança", b.brain.time_ms == t)
    checa("I30 dormindo só com o pet ativo e sem pausa congelada", True)
    return falhas


def main(rodadas=30, acoes=60, semente=0):
    achados = OrderedDict()
    excecoes = OrderedDict()
    for k in range(rodadas):
        rng = random.Random(semente + k)
        try:
            b = novo_app(rng)
        except Exception:
            excecoes.setdefault("criar app", traceback.format_exc())
            continue
        historico = []
        for _ in range(acoes):
            nome = rng.choice(list(ACOES))
            historico.append(nome)
            try:
                ACOES[nome](b, rng)
                rodar(b, 0.3)
            except Exception:
                tb = traceback.format_exc().strip().splitlines()
                chave = f"exceção em {nome}: {tb[-1]}"
                excecoes.setdefault(chave, (list(historico), "\n".join(tb[-8:])))
                continue
            for falha in invariantes(b):
                achados.setdefault(falha, list(historico[-12:]))
        for t in b.findChildren(A.QTimer):
            t.stop()
        for w in QT.topLevelWidgets():
            w.close()
    return achados, excecoes


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    m = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    inicio = _monotonic_real()
    achados, excecoes = main(n, m)
    print(f"\n=== {n} rodadas x {m} ações em {_monotonic_real() - inicio:.0f} s ===")
    print(f"invariantes violados: {len(achados)}")
    for nome, hist in achados.items():
        print(f"- {nome}\n    últimas ações: {' > '.join(hist)}")
    print(f"exceções distintas: {len(excecoes)}")
    for nome, (hist, tb) in excecoes.items():
        print(f"- {nome}\n    últimas ações: {' > '.join(hist[-8:])}\n{tb}")
