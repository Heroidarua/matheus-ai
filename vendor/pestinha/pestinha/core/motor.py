"""
MOTOR - a atividade dos neurônios motores controla o corpo DIRETAMENTE.

Antes (v7.0): motores -> emoção -> tabela fixa (feliz = 170 px/s).
Agora (v7.1): cada população motora regula um parâmetro contínuo do
movimento. Dois momentos "felizes" com redes em estados diferentes se
movem diferente. A emoção continua decidindo o alto nível (para onde ir,
se apronta); a rede decide o COMO.

    WANDER   velocidade e frequência dos passeios, vontade de subir em janelas
    WATCH    quanto ele fixa o olhar no cursor (baixo: olha em volta)
    CHEER    chance e altura dos pulinhos, giros
    STARTLE  força do pulo de susto
    DROWSE   lentidão, pálpebras caídas, hesitação
    ANGRY    tremor
    SAD      menos exploração
    SETTLE   balanço suave do corpo

r = 1 - exp(-Hz / referência): 0 = população quieta, ~0,63 na referência,
satura perto de 1. As referências vêm das taxas medidas da rede (em regime
os motores ficam em 2-7 Hz; picos de 10-25 Hz).
"""

import math

REFERENCE_HZ = {
    "WANDER": 4.0, "WATCH": 6.0, "CHEER": 6.0, "STARTLE": 6.0,
    "DROWSE": 2.0, "ANGRY": 8.0, "SAD": 6.0, "SETTLE": 3.0,
}
SMOOTH_TAU = 0.3            # s: o corpo segue a rede com esse atraso


class MotorTone:
    """Tom dos motores: suaviza a atividade de cada motor e transforma em chances de gestos (pular, girar, balançar)."""
    def __init__(self):
        """Começa todos os motores em zero."""
        self.r = {m: 0.0 for m in REFERENCE_HZ}

    def update(self, motor_activity, dt):
        """Suaviza a atividade dos motores (sobe e desce aos poucos, sem saltos)."""
        k = 1.0 - math.exp(-dt / SMOOTH_TAU)
        for m, ref in REFERENCE_HZ.items():
            target = 1.0 - math.exp(-max(0.0, motor_activity.get(m, 0.0)) / ref)
            self.r[m] += (target - self.r[m]) * k

    # ---------------- parâmetros do corpo ----------------

    def vigor(self):
        """Multiplicador geral: sono e tristeza deixam tudo mais lento."""
        return (1.0 - 0.7 * self.r["DROWSE"]) * (1.0 - 0.6 * self.r["SAD"])

    def drive(self):
        """
        Vontade de se deslocar (0..1). Curiosidade é o motor principal, mas
        alegria (CHEER, ex.: jogando) e estar à vontade (SETTLE, ex.: música)
        também movem; antes só WANDER movia, e ele ficava parado em 3 de 4 contextos.
        """
        r = self.r
        return min(1.0, r["WANDER"] + 0.5 * r["CHEER"] + 0.35 * r["SETTLE"])

    def speed(self):
        """px/s do deslize: v = v_min + k * vontade, freado por sono/tristeza."""
        r = self.r
        return (20.0 + 260.0 * r["WANDER"] + 140.0 * r["CHEER"] + 60.0 * r["SETTLE"]) * self.vigor()

    def roam_scale(self):
        """Multiplica o intervalo entre passeios: mais vontade, decide mais vezes."""
        return 1.6 - 1.0 * self.drive()

    def hop_chance(self):
        """Chance de pular: mais alegria e raiva, e mais forte quando ele está vigoroso."""
        return (0.03 + 0.6 * self.r["CHEER"] + 0.3 * self.r["ANGRY"]) * self.vigor()

    def hop_power(self):
        """Velocidade vertical do pulinho (px/s, para cima)."""
        return 250.0 + 550.0 * self.r["CHEER"] + 200.0 * self.r["ANGRY"]

    def spin_chance(self):
        """Chance de girar, com a alegria."""
        return 0.4 * self.r["CHEER"]

    def climb_chance(self):
        """Chance de subir na janela: com passeio e sem tristeza."""
        return (0.03 + 0.5 * self.r["WANDER"]) * (1.0 - self.r["SAD"])

    def startle_power(self):
        """Força do susto (quanto ele pula para trás ao se assustar)."""
        return 300.0 + 800.0 * self.r["STARTLE"]

    def shake(self):
        """Intensidade do tremor, com a raiva."""
        return 3.0 * self.r["ANGRY"]

    def sway(self):
        """Intensidade do balanço, com o sossego."""
        return 6.0 * self.r["SETTLE"]

    def lid_droop(self):
        """Fração extra das pálpebras fechada pelo sono."""
        return 0.45 * self.r["DROWSE"]

    def watch(self):
        """Chance de, a cada olhada, fixar o cursor em vez de olhar em volta."""
        return 0.25 + 0.75 * self.r["WATCH"]

    def hesitation(self):
        """Chance por segundo de parar no meio do passeio (curioso, mas com sono)."""
        return 1.5 * self.r["DROWSE"] * self.r["WANDER"]
