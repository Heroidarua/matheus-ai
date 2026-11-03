"""
SLEEP - quando ele dorme, quando acorda, e o que acontece ao adormecer.

Dormir é decisão da energia (homeostase), não de um horário. Ele só adormece
apoiado, sem ser segurado, sem voar, sem missão e fora de protesto ativo
(indignado não dorme). Ao adormecer, consolida a memória episódica.
"""

from ..log import log
from ..core.emotion import PRIORITY


class SleepController:
    """Quando ele dorme e acorda: dorme se estiver cansado, no chão e sem estar em protesto ou em missão."""
    def __init__(self, emotion, drives, memory, debug):
        """Guarda a emoção, as necessidades e a memória."""
        self.emotion = emotion
        self.drives = drives
        self.memory = memory
        self.debug = debug          # função -> bool: imprime no terminal só no modo teste
        self.asleep = False

    def can_sleep(self, body, in_flight, protest_stage, mission):
        """Diz se ele pode dormir agora (cansado, no chão, sem ser segurado, sem protesto forte e sem missão)."""
        return (self.drives.sleepy() and body.grounded and not body.held and not in_flight
                and protest_stage < 2 and not mission
                and self.emotion.current not in ("assustado", "dramatico"))

    def tick(self, now, body, in_flight, protest_stage, mission):
        """Um passo: dorme quando pode e acorda quando está descansado."""
        if self.asleep:
            if self.drives.rested():
                self.wake(startled=False)
            else:
                self.emotion.force("dormindo", 0.3, now, PRIORITY["dormindo"])
        elif self.can_sleep(body, in_flight, protest_stage, mission):
            self.fall_asleep()

    def fall_asleep(self):
        """Adormece e consolida: refaz as preferências a partir dos episódios."""
        self.asleep = True
        prefs = self.memory.consolidate()
        if self.debug():
            log(f"[sono] dormiu ({self.drives.describe()})")
            for ctx, action, mean, n in prefs:
                log(f"[sono]   {ctx} -> {action}: {mean:+.2f} ({n:.0f} episódios)")

    def wake(self, startled):
        """Acorda: se foi um susto, ele fica assustado; senão, acorda calmo."""
        self.asleep = False
        if startled:
            self.emotion.force("assustado", 1.2, priority=PRIORITY["assustado"])    # acordou no susto
        if self.debug():
            how = "no susto" if startled else "descansado"
            log(f"[sono] acordou {how} ({self.drives.describe()})")
