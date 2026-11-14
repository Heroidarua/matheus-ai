"""
CONDICIONAMENTO - ele aprende a reagir ANTES do que costuma acontecer com ele.

Cue (sinal antecipador): algo que costuma vir antes de uma interação.
    PRESS      você apertou o botão do mouse em cima dele
    APPROACH   o cursor veio rápido na direção dele
    PLACA      você o carrega perto da placa do cantinho (desfecho: ficar preso)

Desfecho (o que aconteceu de fato): cutucada, arraste ou arremesso.

Regra (Rescorla-Wagner, por episódio):
    cada vez que um cue termina, V += taxa * (λ - V)
    λ = 1 se houve desfecho até WINDOW s depois do fim do cue, senão λ = 0
Então, se você sempre joga ele depois de apertar o mouse em cima, V(PRESS)
sobe, e ele reage ao PRESS sozinho. Se você apertar e soltar sem nada depois,
V cai: é a extinção, e ele volta a não se assustar.

A força antecipada (V do cue ativo) vai para a rede como o canal ANTICIPATE,
que liga em ALERT e STARTLE. Ou seja, o reflexo antecipado sai da rede, não
de um "se apertar, pule".
"""

import math

from ..store import read_json, write_json

WINDOW = 1.5                # s: desfecho até aqui depois do cue conta como consequência
JANELAS = {"PLACA": 4.0}    # s por pista: a placa espera a queda e o pouso no canto (até 3 s)
MIN_V = 0.0
MAX_V = 1.0


class Conditioning:
    """Condicionamento: aprende que um sinal (ex.: a placa do castigo) anuncia algo, e começa a reagir antes de acontecer."""
    def __init__(self, path=None, rate=0.12):
        """Guarda o arquivo e a taxa de aprendizado (quanto cada repetição muda a associação)."""
        self.path = path
        self.rate = rate
        self.V = {"PRESS": 0.0, "APPROACH": 0.0, "PLACA": 0.0}
        self.active = {}           # cue -> {"start": t, "hit": bool}
        self.ended = []            # [cue, fim, teve_desfecho]; viram aprendizado após WINDOW

    # ---------------- observação ----------------

    def set_cue(self, cue, on, now):
        """Liga ou desliga um sinal (cue); enquanto ele está ligado, espera-se o resultado."""
        if on and cue not in self.active:
            self.active[cue] = {"start": now, "hit": False}
        elif not on and cue in self.active:
            info = self.active.pop(cue)
            self.ended.append([cue, now, info["hit"]])

    def outcome(self, now, cues=("PRESS", "APPROACH")):
        """
        Algo aconteceu com ele: marca os cues desse tipo de desfecho que vieram antes.
        Cutucada, arraste e arremesso são desfechos de PRESS/APPROACH; ficar preso é o da PLACA.
        """
        for cue, info in self.active.items():
            if cue in cues:
                info["hit"] = True
        for ep in self.ended:
            if ep[0] in cues and now - ep[1] <= JANELAS.get(ep[0], WINDOW):
                ep[2] = True

    # ---------------- aprendizado ----------------

    def tick(self, now):
        """Fecha episódios vencidos e atualiza V (Rescorla-Wagner)."""
        still = []
        for ep in self.ended:
            cue, end, hit = ep
            if now - end < JANELAS.get(cue, WINDOW):
                still.append(ep)
                continue
            lam = 1.0 if hit else 0.0
            v = self.V.get(cue, 0.0)
            self.V[cue] = min(MAX_V, max(MIN_V, v + self.rate * (lam - v)))
        self.ended = still

    def deslocar(self, segundos):
        """Desconta uma pausa dos relógios das pistas e dos episódios ainda aguardando desfecho."""
        for info in self.active.values():
            info["start"] += segundos
        for ep in self.ended:
            ep[1] += segundos

    def expectancy(self):
        """Força antecipada agora: V de cada cue que está ativo."""
        return {cue: self.V.get(cue, 0.0) for cue in self.active}

    def strength(self, cues=("PRESS", "APPROACH")):
        """Força antecipada só das pistas pedidas: cada tipo de desfecho vai para o seu canal."""
        return max((v for cue, v in self.expectancy().items() if cue in cues), default=0.0)

    # ---------------- persistência ----------------

    def save(self):
        """Grava o aprendizado em conditioning.json (nada se não houver caminho)."""
        if self.path is None:
            return
        write_json(self.path, {"V": self.V})

    def load(self):
        """Lê o aprendizado salvo, validando os valores (valor inválido volta ao zero)."""
        if self.path is None:
            return
        data = read_json(self.path, default=None)
        if isinstance(data, dict) and isinstance(data.get("V"), dict):
            for cue, v in data["V"].items():
                if cue in self.V and isinstance(v, (int, float)) and math.isfinite(v):
                    self.V[cue] = min(MAX_V, max(MIN_V, float(v)))
