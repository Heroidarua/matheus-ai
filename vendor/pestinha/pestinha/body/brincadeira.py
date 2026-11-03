"""
BRINCADEIRA - como o pet brinca: chuta a bolinha, arremessa no cursor, cola post-its.

Um pet só faz tudo. O que muda de um pet para outro são os PESOS, no campo
"brincadeira" de pets/*.json, por exemplo:

    "brincadeira": {"bola": 1.0, "arremesso": 0.6, "postit": 0.5}

Peso 0 desliga aquele jeito de brincar. Quem decide se ele brinca agora é a
emoção (vinda da rede): bola quando está feliz/curioso/contente, arremesso
quando está bravo, e tudo quando está em revolução.

Na revolução, além da bolinha, ele arremessa bolinhas de papel no cursor.
"""

import math
import random

from ..core.physics import GRAVITY
from ..ajustes import (
    ALCANCE_BRINCADEIRA as REACH,
    TEMPO_VOO_ARREMESSO as FLIGHT_TIME,
    INTERVALO_BRINCADEIRA as PLAY_EVERY,
    INTERVALO_PAPEL as PAPER_EVERY,
)

DEFAULT_WEIGHTS = {"bola": 1.0, "arremesso": 0.6, "postit": 0.5}


def weights_of(value):
    """Aceita o formato novo (dict) e o antigo (nome do estilo)."""
    if isinstance(value, dict):
        return {k: float(v) for k, v in value.items()}
    presets = {
        "bola": {"bola": 1.0},
        "arremesso": {"arremesso": 1.0},
        "postit": {"postit": 1.0},
        "quieto": {},
    }
    return presets.get(value, dict(DEFAULT_WEIGHTS))


class Play:
    """Escolhe as brincadeiras do pet (bola, arremesso, post-it) e quando cada uma pode acontecer, com os pesos do .json."""
    def __init__(self, weights):
        """Guarda os pesos de cada brincadeira (0 desliga) e o próximo instante permitido."""
        self.w = weights_of(weights)
        self.next_at = 0.0
        self.next_paper = 0.0

    def weight(self, key):
        """Peso de uma brincadeira pelo nome (0 se não existir)."""
        return self.w.get(key, 0.0)

    def tick(self, now, body, ball, cursor, emotion, pull=1.0):
        """
        Devolve 'kick' ou 'throw' quando brinca com a bolinha, senão None.
        pull (0..1): quanto a rede quer brincar agora (distração acima do foco). Zero, ele trabalha.
        """
        happy = emotion == "feliz"
        if ball is None or not ball.isVisible() or now < self.next_at or pull <= 0.0:
            return None
        if getattr(ball, "dragging", False):      # a bolinha está na mão do usuário: não é dele
            return None
        if math.hypot(ball.body.x - body.x, ball.body.y - body.y) > REACH * (1.4 if happy else 1.0):
            return None
        lo, hi = PLAY_EVERY
        self.next_at = now + random.uniform(lo * 0.5, hi * 0.5) if happy else now + random.uniform(lo, hi)

        if emotion in ("feliz", "curioso", "contente") and self.weight("bola") > 0 \
                and random.random() < 0.7 * self.weight("bola"):
            side = 1 if ball.body.x >= body.x else -1          # chuta para o lado oposto a ele
            ball.kick(side * random.uniform(380.0, 620.0), -random.uniform(300.0, 520.0))
            return "kick"

        if emotion == "bravo" and self.weight("arremesso") > 0 \
                and random.random() < 0.6 * self.weight("arremesso"):
            return self.throw_at(ball, cursor, FLIGHT_TIME, ball.body.x, ball.body.y) and "throw"
        return None

    def throw_at(self, ball, cursor, flight, x0, y0):
        """Arremessa algo de (x0, y0) para o cursor, com trajetória que chega até ele."""
        T = flight
        dx = cursor[0] - x0
        dy = cursor[1] - y0
        vx = max(-1400.0, min(1400.0, dx / T))
        vy = (dy - 0.5 * GRAVITY * T * T) / T
        ball.kick(vx, vy)
        return True

    def paper_due(self, now, revolution, body):
        """Na revolução, uma bolinha de papel a cada PAPER_EVERY s, se ele ainda tiver peso para isso."""
        if not revolution or self.weight("arremesso") <= 0 or now < self.next_paper:
            return False
        self.next_paper = now + PAPER_EVERY
        return True
