"""
MISCHIEF CONTROLLER - quando e como ele apronta, e o que a dispensa causa.

As regras dizem o que PODE (permissões, tela cheia, limite de objetos, assets,
triste e dormindo não aprontam). A memória episódica escolhe o que FAZER,
pelo que deu certo antes naquele contexto. A dispensa alimenta a rede (raiva),
a memória (episódio negativo) e o aprendizado (penalidade de 1 s).
"""

from ..log import log
import random
from collections import deque

VALIDADE_PEDIDO_S = 10.0    # s: "fazer uma travessura agora" vale por este tempo

from ..core.emotion import PRIORITY
from ..ajustes import (DISPENSA_RAPIDA as QUICK_DISMISS, PENALIDADE_DISPENSA as PENALTY_SECONDS,
                       GANHO_TRAVESSURA)



class MischiefController:
    """Decide quando aprontar (memes, bilhetes, fotos) e reage quando você dispensa ou pega esses objetos."""
    def __init__(self, engine, memory, drives, senses, behavior, emotion, debug):
        """Guarda os colaboradores: o motor de travessuras, a memória, as necessidades e o corpo."""
        self.engine = engine
        self.memory = memory
        self.drives = drives
        self.senses = senses
        self.behavior = behavior
        self.emotion = emotion
        self.debug = debug
        self.dismiss_times = deque()
        self.postit_weight = 0.5     # quanto o pet gosta de colar post-its (ligado pelo app)
        self.penalty_until = 0.0
        self.pedido_forcado = False     # "fazer uma travessura agora": ignora o sorteio uma vez
        self.forcado_ate = 0.0

    def pedir(self, now):
        """O comando do menu: a próxima tentativa acontece, se as regras permitirem, nos próximos segundos."""
        self.pedido_forcado = True
        self.forcado_ate = now + VALIDADE_PEDIDO_S

    def penalty_active(self, now):
        """Diz se ainda está valendo a penalidade por ter sido dispensado (ele não apronta de novo logo)."""
        return now < self.penalty_until

    def maybe_act(self, now, dt, bounds, cursor, body, *, motores, activity, emotion, perms, prof,
                  fullscreen, asleep, protest_stage, working=False):
        """
        Tenta uma travessura neste quadro. A frequência é o disparo do neurônio TRAVESSURA:
        quanto mais ele dispara, mais travessuras por segundo. Devolve a ação escolhida, ou None.
        """
        if self.pedido_forcado and now > self.forcado_ate:
            self.pedido_forcado = False                # o pedido do menu venceu sem dar certo
        if not self.pedido_forcado and random.random() >= motores.get("TRAVESSURA", 0.0) * GANHO_TRAVESSURA * dt:
            return None
        if body.held or not body.grounded or self.behavior.mission:
            return None
        if asleep or protest_stage == 3 or not self.engine.allowed(perms, prof, fullscreen):   # greve para tudo; reclamação/manifestação não param os post-its
            return None

        ctx = self.memory.context(activity, emotion)
        options = self.engine.available(emotion, perms, working=working)
        if self.postit_weight <= 0:                  # peso zero: post-its (bilhetes) ficam desligados
            options = [o for o in options if not o.startswith("bilhete")]
        if protest_stage == 4:                       # revolução: só traz fotinhas bravas
            if "meme" not in options:
                return None
            action = "meme"
        else:
            action = self.memory.choose(ctx, options, prof["explore"])
        if action is None or action not in options:
            return None
        self.pedido_forcado = False
        # pet 'postit' prefere colar post-its quando pode
        boost = 1.8 if emotion == "feliz" else 1.0     # feliz cola mais post-its
        if self.postit_weight > 0 and random.random() < 0.5 * self.postit_weight * boost:
            for cand in (("bilhete_canto", "bilhete") if emotion == "bravo" else ("bilhete",)):
                if cand in options:
                    action = cand
                    break
        if self.debug() and self.memory.last_choice:
            log(f"[escolha] {ctx} -> {action} ({self.memory.last_choice[2]})")

        plan = self.engine.plan(action, emotion)
        thing = plan[1] if plan else None
        if plan and plan[0] == "corner":
            if not self.engine.show_in_corner(thing, bounds, cursor):
                return None
        elif plan:
            self.behavior.start_mission(plan, bounds, cursor, now)
        elif action != "nada":
            return None
        self.memory.start(ctx, action, thing)
        if action != "nada":
            self.drives.stimulate("mischief")
        return action

    def on_dismissed(self, thing, elapsed, prof, now):
        """Você dispensou uma travessura: vira frustração e entra na memória como aprendizado."""
        self.senses.dismissed()
        self.drives.touched("dismiss")
        self.memory.on_dismiss(thing, elapsed, prof["dismiss_patience"])
        self.penalty_until = now + PENALTY_SECONDS
        self.dismiss_times.append(now)
        while self.dismiss_times and now - self.dismiss_times[0] > prof["drama_window"]:
            self.dismiss_times.popleft()
        quick = elapsed < QUICK_DISMISS
        if len(self.dismiss_times) >= prof["drama_count"] or (quick and len(self.dismiss_times) >= 2):
            self.emotion.force("dramatico", 4.0, now, PRIORITY["dramatico"])
            self.dismiss_times.clear()

    def clear(self):
        """Tira todas as travessuras da tela e solta o que ele estava carregando."""
        self.behavior.drop_carried()
        self.memory.drop_open_things()
        self.engine.clear()
