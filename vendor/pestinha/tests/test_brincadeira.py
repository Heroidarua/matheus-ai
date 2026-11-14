"""Bolinha: colisão com post-its e estilos de brincadeira por pet. Rodar: python -m pytest tests -q"""
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.body.brincadeira import Play  # noqa: E402
from pestinha.core.physics import Body  # noqa: E402
from pestinha.body.toy import RADIUS, bounce_off  # noqa: E402


class FakeBall:
    def __init__(self, x, y):
        self.body = Body(x, y, RADIUS, RADIUS)

    def place(self):
        pass

    def isVisible(self):
        return True

    def kick(self, vx, vy):
        self.body.vx, self.body.vy = vx, vy
        self.body.grounded = False


def test_bolinha_bate_no_postit_e_volta():
    ball = FakeBall(90.0, 150.0)          # encostando na esquerda do post-it
    ball.body.vx = 400.0
    bounce_off(ball, [(100.0, 100.0, 200.0, 100.0)])
    assert ball.body.x < 90.0 + 1e-6 or ball.body.vx < 0    # rebateu para a esquerda
    assert ball.body.vx < 0


def test_bolinha_longe_do_postit_nao_colide():
    ball = FakeBall(10.0, 10.0)
    bounce_off(ball, [(500.0, 500.0, 100.0, 100.0)])
    assert (ball.body.x, ball.body.y) == (10.0, 10.0)


def test_estilo_bola_chuta_para_longe_dele():
    random.seed(1)
    p = Play("bola")
    ball = FakeBall(300.0, 300.0)
    body = Body(250.0, 300.0, 60, 45)
    act = None
    for t in range(200):
        act = p.tick(t * 3.0, body, ball, (0, 0), "feliz") or act
        if act:
            break
    assert act == "kick"
    assert ball.body.vx > 0                   # ele está à esquerda: chuta para a direita


def test_estilo_postit_e_quieto_nao_chutam():
    for style in ("postit", "quieto"):
        p = Play(style)
        ball = FakeBall(300.0, 300.0)
        body = Body(250.0, 300.0, 60, 45)
        assert p.tick(100.0, body, ball, (0, 0), "feliz") is None


def test_arremesso_no_bravo_chega_perto_do_cursor():
    random.seed(3)
    p = Play("arremesso")
    ball = FakeBall(300.0, 400.0)
    body = Body(250.0, 400.0, 60, 45)
    cursor = (600.0, 300.0)
    act = None
    for t in range(200):
        act = p.tick(t * 3.0, body, ball, cursor, "bravo") or act
        if act:
            break
    assert act == "throw"
    # simula o voo sem chão nem paredes e vê onde a bolinha passa
    from pestinha.core.physics import GRAVITY
    x, y, vx, vy, dt = ball.body.x, ball.body.y, ball.body.vx, ball.body.vy, 1 / 120
    closest = 1e9
    for _ in range(120):
        vy += GRAVITY * dt
        x += vx * dt
        y += vy * dt
        closest = min(closest, ((x - cursor[0]) ** 2 + (y - cursor[1]) ** 2) ** 0.5)
    assert closest < 60


def test_cursor_que_encosta_chuta_a_bolinha_para_longe():
    from pestinha.body.toy import push_from_cursor
    ball = FakeBall(300.0, 300.0)
    ball.dragging = False
    ball.place = lambda: None
    last = push_from_cursor(ball, (310.0, 300.0), (900.0, 0.0), now=10.0, last_push=-1e9)
    assert last == 10.0
    assert ball.body.vx > 0                 # o cursor vinha da esquerda para a direita
