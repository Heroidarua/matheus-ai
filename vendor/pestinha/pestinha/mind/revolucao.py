"""
REVOLUÇÃO - as bolinhas de papel que o pet atira no cursor quando está em revolução.

Quem decide quando atira é o neurônio PAPEL da rede: a taxa de disparo dele é a
frequência das bolinhas (sem rajadas nem pausas fixas). Cada bolinha bate em post-its e
no cursor, e some depois de 10 s. Há no máximo 40 na tela.
"""

import random

from ..body.bolinha import Ball
from ..ajustes import GANHO_PAPEL
from ..body.toy import bounce_off, push_from_cursor

MAXIMO_PAPEIS = 40
VIDA_PAPEL = 10.0          # s


class RevolucaoController:
    """Revolução: na revolução, o pet atira bolinhas de papel no cursor."""
    def __init__(self, play, debug, sprite=None):
        """Guarda o gerador de trajetórias e a imagem da bolinha de papel."""
        self.play = play                 # Play: monta a trajetória até o cursor
        self.sprite = sprite             # foto da bolinha de papel (load_sprite) ou None
        self.papeis = []                 # dicts {bola, nascimento, ultimo_empurrao}
        self.debug = debug

    def tick(self, now, dt, limites, cursor, vel_cursor, corpo, visivel, revoltado, obstaculos, papel_hz):
        """Atira conforme o disparo do neurônio PAPEL e move as bolinhas que já estão no ar."""
        if revoltado and len(self.papeis) < MAXIMO_PAPEIS and random.random() < papel_hz * GANHO_PAPEL * dt:
            self._atirar(now, cursor, corpo, visivel)
        self._mover(now, dt, limites, cursor, vel_cursor, obstaculos)

    def _atirar(self, now, cursor, corpo, visivel):
        """Cria uma bolinha de papel saindo do pet e a lança na direção do cursor."""
        papel = Ball(corpo.x, corpo.y - 40, kind="papel", sprite=self.sprite)
        self.play.throw_at(papel, cursor, 0.8, corpo.x, corpo.y - 40)
        papel.setVisible(visivel)
        self.papeis.append({"bola": papel, "nascimento": now, "ultimo_empurrao": -1e9})

    def _mover(self, now, dt, limites, cursor, vel_cursor, obstaculos):
        """Move as bolinhas de papel; as que acertam algo ou saem da tela são removidas."""
        vivos = []
        for papel in self.papeis:
            bola = papel["bola"]
            if now - papel["nascimento"] > VIDA_PAPEL:
                bola.close()
                bola.deleteLater()
                continue
            bola.step(dt, limites)
            bounce_off(bola, obstaculos)
            papel["ultimo_empurrao"] = push_from_cursor(bola, cursor, vel_cursor, now, papel["ultimo_empurrao"])
            vivos.append(papel)
        self.papeis = vivos

    def janelas(self):
        """Janelas das bolinhas de papel agora (para o app não as contar como janelas de outros programas)."""
        return [p["bola"] for p in self.papeis]

    def esconder(self):
        """Esconde as bolinhas de papel (sem apagar)."""
        for papel in self.papeis:
            papel["bola"].setVisible(False)

    def fechar(self):
        """Fecha as janelas das bolinhas ao sair."""
        for papel in self.papeis:
            papel["bola"].close()
            papel["bola"].deleteLater()
        self.papeis = []
