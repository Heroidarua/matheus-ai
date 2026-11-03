"""
NERVOUS SYSTEM - a rede neural pulsada do pet (neurônios de integração e disparo com vazamento).

A tabela completa de canais, interneurônios, motores e conexões está em docs/REDE_NEURAL.md
(gerada deste arquivo por ferramentas/gerar_doc_rede.py).

Esta rede é PEQUENA e DESENHADA À MÃO (a topologia é nossa, não da mosca).
Ela existe para definir a interface que o conectoma do FlyWire vai usar depois.

Interface (classe Brain):
    stimulate({canal: intensidade 0..1})   entra o mundo (sensores do PC)
    step(dt_ms)                            avança a simulação
    motor_activity() -> {motor: Hz}        saída (neurônios "descendentes")
    snapshot()                             estado para desenhar na tela
    save(path) / load(path)                persistência das sinapses

Para trocar pelo conectoma: crie `FlyConnectomeBrain(Brain)` que mapeia
cada canal sensorial para IDs do FlyWire e cada motor para um grupo de
neurônios descendentes. O resto do pet não muda.

Mecanismos reais incluídos:
    - neurônios LIF (vazamento, limiar, período refratário)
    - ruído de membrana (comportamento não determinístico)
    - adaptação de limiar (a atividade se cansa sozinha)
    - inibição (global e lateral entre comportamentos)
    - HABITUAÇÃO: depressão sináptica nos receptores sensoriais, com
      recuperação lenta. Estímulo repetido enfraquece a sinapse; ausência
      longa a restaura (inclusive entre execuções do programa).

Simplificações assumidas:
    - sinapses instantâneas (salto de tensão), sem condutância
    - neurônios sensoriais são geradores de Poisson
    - inibição lateral entre motores é direta (sem interneurônio)

Dependência: numpy. Testes em tests/test_nucleo.py e tests/test_cantinho_rede.py.
"""

from ..log import log
import math
import time
from collections import deque
from abc import ABC, abstractmethod

import numpy as np

from ..mathutil import valor_real
from ..store import read_json, write_json

# ============================================================
# CANAIS SENSORIAIS: (neurônios, taxa máxima Hz, d, tau_rec s)
#   d       = fração da sinapse perdida a cada spike (habituação)
#   tau_rec = tempo de recuperação da sinapse (s)
# ============================================================

SENSORY_SPEC = {
    #            n   rate     d       tau_rec
    "MOTION":  (6, 120.0, 0.0004,   600.0),   # troca de janela
    "TYPING":  (6,  60.0, 0.00007, 1200.0),   # teclado / mouse
    "NOVELTY": (6, 100.0, 0.0004,   900.0),   # mudança de atividade / volta
    "SILENCE": (6,  40.0, 0.0,        1.0),   # ausência de input (não habitua)
    "WORK":    (6,  40.0, 0.00007, 1200.0),   # programando / projetando
    "PLAY":    (6,  60.0, 0.00010,  900.0),   # jogando
    "SOUND":   (6,  40.0, 0.00007, 1200.0),   # música
    "SOCIAL":  (6,  50.0, 0.00008,  900.0),   # chats
    "WEB":     (6,  50.0, 0.00008,  900.0),   # navegador
    "FATIGUE": (6,  40.0, 0.0,        1.0),   # interno: pouca energia (homeostase; não habitua)
    "POKE":    (6,  80.0, 0.0009,   150.0),   # cutucada: habitua rápido e volta em minutos
    "DRAG":    (6,  60.0, 0.0002,   600.0),   # sendo arrastado
    "DISMISS": (6,  80.0, 0.00005, 1800.0),   # travessura dispensada
    "LONELY":  (6,  40.0, 0.0,        1.0),   # interno: carente de contato (homeostase; não habitua)
    "CARESS":  (6,  60.0, 0.0,        1.0),   # carinho (mouse esfregando nele; não enjoa)
    "ANTICIPATE": (6, 80.0, 0.0,      1.0),   # previsão aprendida (condicionamento); não habitua
    "TOY_NEAR": (6,  40.0, 0.0,       1.0),   # a bolinha está perto dele
    "TOY_TAKEN": (6, 80.0, 0.0002,  600.0),   # você levou a bolinha para longe
    "THROW":   (6,  80.0, 0.0008,   300.0),   # foi arremessado (a graça enjoa se repetir)
    "IMPACT":  (6, 100.0, 0.0002,   600.0),   # bateu forte na parede/chão
    "BOREDOM": (6,  60.0, 0.0,        1.0),   # interno: pouca estimulação (homeostase; não habitua)
    "PEDIDO":  (6,  60.0, 0.0,        1.0),   # você pediu para ele trabalhar (vale por um tempo)
    "PRESO":   (6,  40.0, 0.0004,   900.0),   # preso no cantinho do castigo (habitua: ele se acostuma)
    "LEMBRA_FUGA": (6, 40.0, 0.0,     1.0),   # memória: fugas que já deram certo
    "RECUSA":  (6,  80.0, 0.0,        1.0),   # você pediu e ele não quis (frustração pontual)
    "PLACA":   (6,  30.0, 0.0001,  1200.0),   # a placa do castigo está à vista (aviso)
    "ANTECIPA_PLACA": (6, 80.0, 0.0,  1.0),   # previsão aprendida de ir para o canto (só a pista da placa)
    "VISITA":  (6,  60.0, 0.0,        1.0),   # você está perto dele enquanto ele está preso
    "RECEIO":  (6,  40.0, 0.0,        1.0),   # interno: fugas que deram errado (devolvido ao canto)
    "RANCOR":  (6,  40.0, 0.0,        1.0),   # interno: tempo de castigo acumulado, decai devagar
}

# ============================================================
# APRENDIZADO POR CARINHO (regra de três fatores)
#   pré-sináptico: o contexto ativo (canais sensoriais, traço de elegibilidade)
#   recompensa:    carinho (+), travessura dispensada (-)
#   pós-sináptico: SINAL emocional do interneurônio alvo
# O que estava acontecendo quando ele ganhou carinho passa a puxar para
# PLAYFUL/CALM e a se afastar de FRUSTRATION/GLOOM (condicionamento).
# ============================================================

PLASTIC_POSTS = {"PLAYFUL": 1.0, "CALM": 1.0, "FRUSTRATION": -1.0, "GLOOM": -1.0}
PLASTIC_DENSITY = 0.5
LEARN_MIN, LEARN_MAX = -0.05, 0.08     # peso aprendido (fração do limiar)
ELIGIBILITY_TAU = 4.0                  # s: quanto tempo um contexto "conta" para a recompensa
LEARNED_VERSION = 2                    # 2: TYPING passou a ser só teclado

# ============================================================
# INTERNEURÔNIOS: nome, tipo, n, tau_m (ms), adapt_b, adapt_tau (s), centro
# ============================================================

INTER_SPEC = [
    ("ALERT",   "exc", 16,  20.0, 0.030, 1.5, (0.32, 0.10)),
    ("FOCUS",   "exc", 16, 120.0, 0.020, 2.0, (0.32, 0.30)),
    ("CURIOUS", "exc", 16,  80.0, 0.020, 2.0, (0.32, 0.50)),
    ("PLAYFUL", "exc", 12,  60.0, 0.020, 2.0, (0.32, 0.70)),
    ("CALM",    "exc", 12, 300.0, 0.010, 3.0, (0.58, 0.28)),
    ("TIRED",   "exc", 12, 400.0, 0.010, 3.0, (0.58, 0.58)),
    ("QUIET",   "inh", 12,  30.0, 0.000, 1.0, (0.58, 0.82)),
    ("INHIB",   "inh", 20,  10.0, 0.000, 1.0, (0.45, 0.92)),
    ("FRUSTRATION", "exc", 12, 300.0, 0.010, 3.0, (0.70, 0.40)),
    ("GLOOM",   "exc", 12, 400.0, 0.010, 4.0, (0.70, 0.70)),
]

# ============================================================
# MOTORES: nome, n, tau_m (ms), adapt_b, adapt_tau (s)
# ============================================================

MOTOR_SPEC = [
    ("STARTLE", 10, 25.0, 0.060, 1.0),
    ("WATCH",   10, 50.0, 0.040, 3.0),
    ("WANDER",  10, 50.0, 0.050, 3.0),
    ("CHEER",   10, 50.0, 0.040, 3.0),
    ("SETTLE",  10, 60.0, 0.030, 4.0),
    ("DROWSE",  10, 80.0, 0.020, 5.0),
    ("ANGRY",   10, 50.0, 0.030, 4.0),
    ("SAD",     10, 80.0, 0.020, 5.0),
    ("SENTAR",  10, 60.0, 0.030, 4.0),      # quer trabalhar no notebook
    ("FUGIR",   10, 40.0, 0.030, 4.0),      # tenta escapar do cantinho
    ("CARTAZ",  10, 60.0, 0.030, 4.0),      # cola um cartaz de protesto
    ("CANTO",   10, 80.0, 0.020, 5.0),      # vai para o cantinho
    ("TRAVESSURA", 10, 60.0, 0.030, 4.0),   # apronta uma travessura (a taxa vira a frequência)
    ("PAPEL",   10, 60.0, 0.030, 4.0),      # atira bolinha de papel (na revolução)
    ("ACEITAR", 10, 80.0, 0.020, 4.0),      # aceita o castigo e sai do canto por conta própria (perdão)
]

# ============================================================
# CONEXÕES: (pré, pós, peso, densidade)
# peso = salto na tensão, como fração do limiar (limiar = 1.0)
# ============================================================

CONNECTIONS = [
    # sensores -> interneurônios
    ("MOTION",  "ALERT",   0.14, 0.6),
    ("NOVELTY", "ALERT",   0.06, 0.6),
    ("TYPING",  "ALERT",   0.02, 0.6),
    ("PLAY",    "ALERT",   0.03, 0.6),
    ("NOVELTY", "CURIOUS", 0.10, 0.6),
    ("WEB",     "CURIOUS", 0.06, 0.6),
    ("SOCIAL",  "CURIOUS", 0.04, 0.6),
    ("TYPING",  "FOCUS",   0.05, 0.6),
    ("WORK",    "FOCUS",   0.14, 0.6),
    ("WORK",    "CALM",    0.03, 0.6),
    ("PLAY",    "PLAYFUL", 0.08, 0.6),
    ("SOUND",   "PLAYFUL", 0.02, 0.6),
    ("SOUND",   "CALM",    0.06, 0.6),
    ("SILENCE", "CALM",    0.03, 0.6),
    ("SILENCE", "TIRED",   0.06, 0.6),
    ("SILENCE", "QUIET",   0.08, 0.6),
    ("FATIGUE", "TIRED",   0.08, 0.6),
    ("FATIGUE", "QUIET",   0.03, 0.6),
    ("POKE",    "ALERT",   0.08, 0.6),
    ("POKE",    "PLAYFUL", 0.08, 0.6),
    ("POKE",    "CURIOUS", 0.05, 0.6),
    ("DRAG",    "ALERT",   0.06, 0.6),
    ("DRAG",    "CURIOUS", 0.07, 0.6),
    ("DRAG",    "PLAYFUL", 0.05, 0.6),
    ("DRAG",    "FRUSTRATION", 0.03, 0.6),
    ("DISMISS", "FRUSTRATION", 0.12, 0.6),
    ("DISMISS", "ALERT",   0.03, 0.6),
    ("DISMISS", "GLOOM",   0.03, 0.6),
    ("LONELY",  "GLOOM",   0.08, 0.6),
    ("LONELY",  "QUIET",   0.03, 0.6),
    ("CARESS",  "CALM",    0.07, 0.6),
    ("ANTICIPATE", "ALERT",  0.12, 0.6),     # reage ao que costuma vir
    ("ANTICIPATE", "WATCH",  0.05, 0.6),
    ("TOY_NEAR", "PLAYFUL",  0.10, 0.6),     # brincar com a bolinha
    ("TOY_NEAR", "CURIOUS",  0.06, 0.6),
    ("TOY_TAKEN", "ALERT",   0.06, 0.6),     # levaram embora: alerta, e depois o humor
    ("TOY_TAKEN", "FRUSTRATION", 0.10, 0.6), # ...raiva (depende do temperamento)
    ("TOY_TAKEN", "GLOOM",   0.10, 0.6),     # ...ou tristeza (depende do temperamento)
    ("CARESS",  "PLAYFUL", 0.05, 0.6),
    ("THROW",   "PLAYFUL", 0.08, 0.6),
    ("THROW",   "ALERT",   0.05, 0.6),
    ("THROW",   "CURIOUS", 0.03, 0.6),
    ("IMPACT",  "ALERT",   0.10, 0.6),
    ("IMPACT",  "FRUSTRATION", 0.06, 0.6),
    ("IMPACT",  "GLOOM",   0.02, 0.6),
    ("BOREDOM", "CURIOUS", 0.12, 0.6),
    ("BOREDOM", "PLAYFUL", 0.09, 0.6),

    # interneurônios entre si
    ("TIRED",   "GLOOM",   0.03, 0.5),
    ("FRUSTRATION", "INHIB",   0.04, 0.5),
    ("FRUSTRATION", "CALM",   -0.06, 0.5),
    ("FRUSTRATION", "PLAYFUL", -0.05, 0.5),
    ("GLOOM",   "PLAYFUL", -0.06, 0.5),
    ("GLOOM",   "CURIOUS", -0.04, 0.5),
    ("PLAYFUL", "GLOOM",  -0.05, 0.5),
    ("CALM",    "FRUSTRATION", -0.03, 0.5),
    ("ALERT",   "CURIOUS", 0.05, 0.4),
    ("ALERT",   "INHIB",   0.10, 0.5),
    ("FOCUS",   "INHIB",   0.06, 0.5),
    ("CURIOUS", "INHIB",   0.06, 0.5),
    ("PLAYFUL", "INHIB",   0.06, 0.5),
    ("CALM",    "ALERT",  -0.06, 0.5),
    ("TIRED",   "ALERT",  -0.05, 0.5),
    ("TIRED",   "PLAYFUL", -0.05, 0.5),
    ("TIRED",   "CURIOUS", -0.04, 0.5),
    ("QUIET",   "FOCUS",  -0.08, 0.5),
    ("QUIET",   "ALERT",  -0.04, 0.5),
    ("QUIET",   "CURIOUS", -0.05, 0.5),
    ("INHIB",   "ALERT",  -0.04, 0.5),
    ("INHIB",   "FOCUS",  -0.03, 0.5),
    ("INHIB",   "CURIOUS", -0.03, 0.5),
    ("INHIB",   "PLAYFUL", -0.03, 0.5),

    # interneurônios -> motores
    ("ALERT",   "STARTLE", 0.50, 0.6),
    ("ALERT",   "WATCH",   0.20, 0.6),
    ("FOCUS",   "WATCH",   0.35, 0.6),
    ("FOCUS",   "WANDER", -0.20, 0.5),
    ("CURIOUS", "WANDER",  0.35, 0.6),
    ("CURIOUS", "WATCH",   0.12, 0.6),
    ("PLAYFUL", "CHEER",   0.70, 0.6),
    ("CALM",    "SETTLE",  0.50, 0.6),
    ("TIRED",   "DROWSE",  0.30, 0.6),
    ("CALM",    "DROWSE",  0.05, 0.6),
    ("INHIB",   "STARTLE", -0.08, 0.5),
    ("INHIB",   "WATCH",   -0.08, 0.5),
    ("INHIB",   "WANDER",  -0.08, 0.5),
    ("INHIB",   "CHEER",   -0.08, 0.5),
    ("FRUSTRATION", "ANGRY", 0.55, 0.6),
    ("ALERT",   "ANGRY",   0.05, 0.6),
    ("GLOOM",   "SAD",     0.45, 0.6),
    ("INHIB",   "ANGRY",  -0.04, 0.5),

    # ---- decisões: sentar, fugir, cartaz, canto, travessura, papel ----
    ("PEDIDO",  "SENTAR",  0.55, 0.6),      # você pediu: a vontade de trabalhar sobe
    ("PEDIDO",  "FOCUS",   0.12, 0.6),
    ("FOCUS",   "SENTAR",  0.45, 0.6),      # quer trabalhar: foco puxa para sentar
    ("PLAYFUL", "SENTAR", -0.40, 0.6),      # quer brincar: brincadeira tira da mesa
    ("CURIOUS", "SENTAR", -0.25, 0.6),
    ("FRUSTRATION", "SENTAR", -0.35, 0.6),  # frustrado não quer trabalhar
    ("GLOOM",   "SENTAR", -0.60, 0.6),      # triste não senta
    ("ALERT",   "SENTAR", -0.10, 0.5),
    ("RECUSA",  "FRUSTRATION", 0.25, 0.6),  # recusou um pedido: frustra
    ("RECUSA",  "GLOOM",   0.05, 0.5),
    ("PRESO",   "FRUSTRATION", 0.10, 0.6),  # preso no canto: frustra com o tempo
    ("PRESO",   "ALERT",   0.04, 0.6),
    ("PRESO",   "SENTAR",  -0.30, 0.6),
    ("FRUSTRATION", "FUGIR", 0.35, 0.6),    # quanto mais frustrado, mais tenta fugir
    ("LEMBRA_FUGA", "FUGIR", 0.30, 0.6),    # fuga que deu certo fica na memória
    ("CALM",    "FUGIR",  -0.30, 0.5),
    ("FRUSTRATION", "CARTAZ", 0.25, 0.6),
    ("CALM",    "CARTAZ", -0.20, 0.5),
    ("GLOOM",   "CANTO",   0.50, 0.6),      # triste: vai para o cantinho
    ("TIRED",   "CANTO",   0.05, 0.5),
    ("BOREDOM", "TRAVESSURA", 0.30, 0.6),   # entediado apronta
    ("CURIOUS", "TRAVESSURA", 0.20, 0.6),
    ("PLAYFUL", "TRAVESSURA", 0.12, 0.6),
    ("CALM",    "TRAVESSURA", -0.30, 0.5),
    ("GLOOM",   "TRAVESSURA", -0.50, 0.5),  # triste não apronta
    ("FRUSTRATION", "PAPEL", 0.40, 0.6),    # na revolução, atira papel
    ("CALM",    "PAPEL",  -0.40, 0.5),

    # ---- cantinho do castigo ----
    ("PLACA",   "TRAVESSURA", -0.60, 0.6),  # 3) a placa à vista desencoraja travessuras
    ("PLACA",   "ALERT",   0.02, 0.6),
    ("ANTECIPA_PLACA", "FUGIR", 0.15, 0.6), # 2) antecipar o canto (condicionamento) dá vontade de fugir
    ("ANTECIPA_PLACA", "ALERT", 0.12, 0.6),
    ("RANCOR",  "SENTAR", -0.30, 0.6),      # 5) rancor: trabalha menos
    ("RANCOR",  "TRAVESSURA", 0.15, 0.6),   #    ...e apronta mais
    ("RANCOR",  "FRUSTRATION", 0.04, 0.6),
    ("CALM",    "ACEITAR", 0.45, 0.6),      # 6) calmo, aceita o castigo
    ("CARESS",  "ACEITAR", 0.30, 0.6),      #    carinho ajuda a perdoar
    ("VISITA",  "ACEITAR", 0.08, 0.6),
    ("FRUSTRATION", "ACEITAR", -0.40, 0.6),
    ("RANCOR",  "ACEITAR", -0.20, 0.6),
    ("VISITA",  "WATCH",   0.20, 0.6),      # 7) visitado: olha para você
    ("VISITA",  "CALM",    0.05, 0.6),
    ("VISITA",  "GLOOM",  -0.10, 0.6),      #    ...e fica menos triste
    ("RECEIO",  "FUGIR",  -0.40, 0.6),      # 8) fugas que deram errado inibem a fuga
    ("RECEIO",  "GLOOM",   0.04, 0.6),
    ("CARTAZ",  "FRUSTRATION", -0.20, 0.6), # 9) colar cartaz é desabafo
    ("BOREDOM", "FUGIR",   0.15, 0.6),      # 10) entediado no canto, foge do tédio
]

DECISION_MOTORS = {"SENTAR", "FUGIR", "CARTAZ", "CANTO", "TRAVESSURA", "PAPEL", "ACEITAR"}   # decisões, não expressão
LATERAL_INHIBITION = 0.05      # cada motor inibe os outros
STARTLE_INHIBITION = 0.10      # o susto inibe mais forte

T_REF = 3                      # período refratário (passos de 1 ms)
NOISE_SIGMA = 0.025
READ_TAU = 0.5                 # s: suavização da taxa motora
TRACE_DECAY = math.exp(-1.0 / 120.0)
RASTER_BIN_MS = 10             # raster do monitor: uma coluna a cada 10 ms
RASTER_BINS = 300               # 3 s de história


# ============================================================
# INTERFACE
# ============================================================


class Brain(ABC):
    """Interface de um cérebro: recebe sensações, devolve a atividade de cada motor. Trocar a rede = criar outra classe com esta interface."""
    sensory_names = []
    motor_names = []

    @abstractmethod
    def stimulate(self, intensities):
        """intensities: {canal: 0..1}. Canais ausentes valem 0."""

    @abstractmethod
    def step(self, dt_ms):
        """Avança a simulação por dt_ms milissegundos."""

    @abstractmethod
    def motor_activity(self):
        """{motor: taxa de disparo suavizada, em Hz por neurônio}"""

    @abstractmethod
    def snapshot(self):
        """Dados para visualização."""

    def save(self, path):
        """Grava o estado do cérebro no arquivo (a rede implementa)."""
        pass

    def load(self, path):
        """Lê o estado salvo. Devolve False se não há estado válido (começa do zero)."""
        return False

    def describe(self):
        """Texto curto que descreve a rede (para o log e o monitor)."""
        return ""


# ============================================================
# BACKEND: LIF PEQUENO
# ============================================================


class LIFBrain(Brain):
    """Rede neural pulsada (neurônios de integração e disparo com vazamento). A mesma estrutura para todos os pets; a semente e o temperamento dão o 'indivíduo'."""
    SEED = 7                    # outra semente = outro "indivíduo"

    def __init__(self, seed=None, temperament=None):
        """
        temperament: {interneurônio: ganho} ou {"PRE->POS": ganho}.
        Multiplica as sinapses que saem dos SENSORES, então o mesmo
        estímulo (ex.: DRAG) pesa diferente em cada pet.
        """
        self.seed = self.SEED if seed is None else seed
        self.temperament = dict(temperament or {})
        rng = np.random.default_rng(self.seed)
        self.rng = np.random.default_rng()          # ruído: sempre diferente

        # ---------------- populações ----------------
        self.pools = []                             # dicts com start/n/group
        self._pool_index = {}
        cursor = 0

        def add_pool(name, group, n, kind, center):
            """Cria um grupo de neurônios (pool) de tamanho `n` e registra onde ele começa na lista geral."""
            nonlocal cursor
            pool = {
                "name": name, "group": group, "kind": kind,
                "start": cursor, "n": n, "center": center,
            }
            self._pool_index[name] = len(self.pools)
            self.pools.append(pool)
            cursor += n
            return pool

        for i, (name, (n, *_rest)) in enumerate(SENSORY_SPEC.items()):
            add_pool(name, "sensory", n, "sens", (0.05, 0.06 + i * 0.0933))

        for name, kind, n, _tau, _b, _bt, center in INTER_SPEC:
            add_pool(name, "inter", n, kind, center)

        for i, (name, n, *_rest) in enumerate(MOTOR_SPEC):
            add_pool(name, "motor", n, "exc", (0.95, 0.10 + i * 0.16))

        self.N = cursor
        self.Ns = sum(p["n"] for p in self.pools if p["group"] == "sensory")
        self.Nl = self.N - self.Ns

        self.sensory_names = list(SENSORY_SPEC.keys())
        self.motor_names = [m[0] for m in MOTOR_SPEC]

        # ---------------- parâmetros por neurônio ----------------
        tau_m = np.full(self.N, 20.0)
        adapt_b = np.zeros(self.N)
        adapt_tau = np.full(self.N, 1.0)

        s_rate = np.zeros(self.Ns)
        s_d = np.zeros(self.Ns)
        s_tau_rec = np.ones(self.Ns)

        for name, kind, n, tau, b, bt, _c in INTER_SPEC:
            p = self.pool(name)
            sl = slice(p["start"], p["start"] + p["n"])
            tau_m[sl], adapt_b[sl], adapt_tau[sl] = tau, b, bt

        for name, n, tau, b, bt in MOTOR_SPEC:
            p = self.pool(name)
            sl = slice(p["start"], p["start"] + p["n"])
            tau_m[sl], adapt_b[sl], adapt_tau[sl] = tau, b, bt

        for name, (n, rate, d, rec) in SENSORY_SPEC.items():
            p = self.pool(name)
            sl = slice(p["start"], p["start"] + p["n"])
            s_rate[sl], s_d[sl], s_tau_rec[sl] = rate, d, rec

        tau_m *= rng.uniform(0.9, 1.1, self.N)       # heterogeneidade

        Ns = self.Ns
        self.decay = np.exp(-1.0 / tau_m[Ns:])
        self.adapt_b = adapt_b[Ns:]
        self.adapt_decay = np.exp(-1.0 / (adapt_tau[Ns:] * 1000.0))

        self.s_rate = s_rate
        self.s_d = s_d
        self.s_rec = 0.001 / s_tau_rec               # dt = 1 ms
        self.s_tau_rec = s_tau_rec
        self.s_prob = np.zeros(Ns)

        # ---------------- sinapses ----------------
        W = np.zeros((self.N, self.N))

        def connect(pre, post, weight, density):
            """Liga dois pools com peso e densidade; o peso de cada ligação varia um pouco (lognormal, média 1)."""
            a, b = self.pool(pre), self.pool(post)
            mask = rng.random((a["n"], b["n"])) < density
            strength = rng.lognormal(0.0, 0.25, (a["n"], b["n"]))
            strength /= np.exp(0.25 ** 2 / 2)         # média 1
            block = weight * strength * mask
            W[a["start"]:a["start"] + a["n"], b["start"]:b["start"] + b["n"]] += block

        for pre, post, weight, density in CONNECTIONS:
            if pre in SENSORY_SPEC:
                weight *= self.temperament.get(f"{pre}->{post}", self.temperament.get(post, 1.0))
            connect(pre, post, weight, density)

        motors = [m[0] for m in MOTOR_SPEC]
        for a in motors:
            for b in motors:
                # motores de expressão (corpo) e de decisão (sentar, fugir...) competem só dentro do seu grupo
                if a != b and (a in DECISION_MOTORS) == (b in DECISION_MOTORS):
                    connect(a, b, -(STARTLE_INHIBITION if a == "STARTLE" else LATERAL_INHIBITION), 0.7)

        self.W = W
        self.W_base = W.copy()

        # sinapses plásticas sensor -> PLASTIC_POSTS (rng próprio: não muda o resto da rede)
        plastic_rng = np.random.default_rng(self.seed + 1)
        self.plastic_posts = list(PLASTIC_POSTS)
        self.post_sign = np.array([PLASTIC_POSTS[name] for name in self.plastic_posts])
        self.plastic_masks = {}
        for c in self.sensory_names:
            a = self.pool(c)
            for post in self.plastic_posts:
                b = self.pool(post)
                mask = plastic_rng.random((a["n"], b["n"])) < PLASTIC_DENSITY
                strength = plastic_rng.lognormal(0.0, 0.25, (a["n"], b["n"])) / np.exp(0.25 ** 2 / 2)
                self.plastic_masks[(c, post)] = mask * strength
        self.learned = np.zeros((len(self.sensory_names), len(self.plastic_posts)))
        self.eligibility = np.zeros(len(self.sensory_names))
        self._levels = np.zeros(len(self.sensory_names))

        self.W_lif = np.ascontiguousarray(W[:, Ns:])
        self.n_synapses = int((W != 0).sum())

        # ---------------- estado ----------------
        self.v = np.zeros(self.Nl)
        self.a = np.zeros(self.Nl)
        self.ref = np.zeros(self.Nl, dtype=int)
        self.spikes = np.zeros(self.N)

        self.pre_gain = np.ones(self.N)             # eficácia sináptica de saída
        self.p = self.pre_gain[:Ns]                 # view: p dos receptores

        self.trace = np.zeros(self.N)

        onehot = np.zeros((self.N, len(self.pools)))
        for i, p in enumerate(self.pools):
            onehot[p["start"]:p["start"] + p["n"], i] = 1.0
        self.onehot = onehot
        self.pool_sizes = np.array([p["n"] for p in self.pools], dtype=float)
        self.pool_counts = np.zeros(len(self.pools))
        self.pool_rate = np.zeros(len(self.pools))

        # ---------------- posições para a UI ----------------
        pos = np.zeros((self.N, 2))
        for p in self.pools:
            cx, cy = p["center"]
            idx = np.arange(p["start"], p["start"] + p["n"])
            if p["group"] == "sensory":
                for k, i in enumerate(idx):
                    pos[i] = (cx + (k % 2) * 0.022, cy - 0.028 + (k // 2) * 0.028)
            else:
                pos[idx, 0] = cx + rng.normal(0, 0.022, p["n"])
                pos[idx, 1] = cy + rng.normal(0, 0.026, p["n"])
        self.pos = np.clip(pos, 0.01, 0.99)

        kind = np.zeros(self.N, dtype=int)          # 0 sens 1 exc 2 inh 3 motor
        for p in self.pools:
            sl = slice(p["start"], p["start"] + p["n"])
            if p["group"] == "sensory":
                kind[sl] = 0
            elif p["group"] == "motor":
                kind[sl] = 3
            else:
                kind[sl] = 2 if p["kind"] == "inh" else 1
        self.kind = kind

        self.time_ms = 0.0

        # raster para o Neural Monitor (só grava quando alguém está olhando)
        self.recording = False
        self.raster = deque(maxlen=RASTER_BINS)
        self._bin = np.zeros(self.N, dtype=bool)

    # ----------------------------------------------------------

    def pool(self, name):
        """Devolve o grupo de neurônios pelo nome."""
        return self.pools[self._pool_index[name]]

    # ---------------- interface ----------------

    def stimulate(self, intensities):
        """Recebe a intensidade (0 a 1) de cada canal sensorial e converte em probabilidade de disparo, com habituação."""
        self.s_prob[:] = 0.0
        for k, name in enumerate(self.sensory_names):
            level = float(intensities.get(name, 0.0))
            level = 0.0 if level < 0 else 1.0 if level > 1 else level
            self._levels[k] = level
            p = self.pool(name)
            sl = slice(p["start"], p["start"] + p["n"])
            self.s_prob[sl] = self.s_rate[sl] * level * 0.001

    def _substep(self):
        """Um passo de 1 ms da rede: integra as entradas, dispara os neurônios que passaram do limiar e atualiza a habituação."""
        rng = self.rng
        Ns = self.Ns

        drive = (self.spikes * self.pre_gain) @ self.W_lif

        v = self.v
        v *= self.decay
        v += drive
        v += NOISE_SIGMA * rng.standard_normal(self.Nl)

        in_ref = self.ref > 0
        v[in_ref] = 0.0
        self.ref[in_ref] -= 1
        np.maximum(v, -0.5, out=v)

        fired = v >= (1.0 + self.a)
        v[fired] = 0.0
        self.ref[fired] = T_REF
        self.a *= self.adapt_decay
        self.a[fired] += self.adapt_b[fired]

        s_fired = rng.random(Ns) < self.s_prob

        # HABITUAÇÃO: depressão sináptica + recuperação lenta
        self.p[s_fired] *= (1.0 - self.s_d[s_fired])
        self.p += (1.0 - self.p) * self.s_rec

        self.spikes[:Ns] = s_fired
        self.spikes[Ns:] = fired

        self.trace *= TRACE_DECAY
        self.trace[self.spikes > 0] = 1.0
        self.pool_counts += self.spikes @ self.onehot

    def step(self, dt_ms):
        """Avança a rede `dt_ms` milissegundos (em passos de 1 ms, no máximo 400 por chamada)."""
        n = int(max(1, min(400, round(dt_ms))))
        for i in range(n):
            self._substep()
            if self.recording:
                self._bin |= self.spikes > 0
                if (self.time_ms + i + 1) % RASTER_BIN_MS == 0:
                    self.raster.append(self._bin)
                    self._bin = np.zeros(self.N, dtype=bool)

        dt_s = n * 0.001
        rate = self.pool_counts / (dt_s * self.pool_sizes)
        alpha = 1.0 - math.exp(-dt_s / READ_TAU)
        self.pool_rate += alpha * (rate - self.pool_rate)
        self.pool_counts[:] = 0.0
        self.time_ms += n

    def motor_activity(self):
        """Atividade atual (Hz) de cada motor: o que a rede está 'querendo' fazer agora."""
        return {name: float(self.pool_rate[self._pool_index[name]]) for name in self.motor_names}

    def pool_rates(self):
        """Atividade atual (Hz) de cada pool, para o monitor neural."""
        return {p["name"]: float(self.pool_rate[i]) for i, p in enumerate(self.pools)}

    def efficacy(self):
        """Eficácia média (1 = sem habituação) por canal sensorial."""
        out = {}
        for name in self.sensory_names:
            p = self.pool(name)
            out[name] = float(self.p[p["start"]:p["start"] + p["n"]].mean())
        return out

    def reset_habituation(self):
        """Zera a habituação: todo estímulo volta a ser novidade."""
        self.p[:] = 1.0

    # ---------------- aprendizado ----------------

    def learn(self, reward, dt_s, rate):
        """
        Chamar a cada passo: atualiza a elegibilidade (o que estava ativo nos
        últimos segundos) e, se houver recompensa, ajusta as sinapses plásticas.
        reward: + carinho, - rejeição. rate: velocidade de aprendizado.
        """
        k = 1.0 - math.exp(-dt_s / ELIGIBILITY_TAU)
        self.eligibility += (self._levels - self.eligibility) * k
        if reward == 0.0:
            return
        delta = rate * reward * dt_s * np.outer(self.eligibility, self.post_sign)
        self.learned = np.clip(self.learned + delta, LEARN_MIN, LEARN_MAX)
        self._apply_learning()

    def _apply_learning(self):
        """Recalcula as sinapses que aprendem, a partir do rastro (trace) de atividade recente."""
        W = self.W_base.copy()
        for i, c in enumerate(self.sensory_names):
            a = self.pool(c)
            for j, post in enumerate(self.plastic_posts):
                if self.learned[i, j] == 0.0:
                    continue
                b = self.pool(post)
                W[a["start"]:a["start"] + a["n"], b["start"]:b["start"] + b["n"]] += (
                    self.learned[i, j] * self.plastic_masks[(c, post)]
                )
        self.W = W
        self.W_lif = np.ascontiguousarray(W[:, self.Ns:])

    def learned_summary(self, top=5):
        """As associações mais fortes que ele aprendeu: [(canal, alvo, peso)]."""
        pairs = [
            (c, post, float(self.learned[i, j]))
            for i, c in enumerate(self.sensory_names)
            for j, post in enumerate(self.plastic_posts)
            if abs(self.learned[i, j]) > 1e-4
        ]
        return sorted(pairs, key=lambda x: -abs(x[2]))[:top]

    def snapshot(self):
        """Foto do estado da rede (posições, rastro, tipos) para o monitor e para testes."""
        return {
            "pos": self.pos,
            "trace": self.trace,
            "kind": self.kind,
            "pools": self.pools,
            "motor": self.motor_activity(),
            "efficacy": self.efficacy(),
            "pool_rate": self.pool_rates(),
        }

    def describe(self):
        """Resumo da rede: quantos neurônios e sinapses."""
        return f"LIF {self.N} neurônios, {self.n_synapses} sinapses (desenhada à mão)"

    # ---------------- persistência ----------------

    def save(self, path):
        """Grava pesos, habituação e aprendizado no arquivo JSON (escrita atômica)."""
        data = {
            "version": 1,
            "seed": self.seed,
            "saved_at": time.time(),
            "efficacy": {
                name: [round(float(x), 5) for x in
                       self.p[self.pool(name)["start"]:self.pool(name)["start"] + self.pool(name)["n"]]]
                for name in self.sensory_names
            },
            "learned_version": LEARNED_VERSION,
            "learned": {
                c: {post: round(float(self.learned[i, j]), 6) for j, post in enumerate(self.plastic_posts)}
                for i, c in enumerate(self.sensory_names)
            },
        }
        write_json(path, data)

    def load(self, path):
        """
        Restaura a habituação e o aprendizado. Tudo é validado antes de aplicar: versão,
        forma das matrizes, valores finitos e dentro do domínio. Se algo falhar, nada é
        alterado e a rede segue como estava.
        """
        data = read_json(path, default=None)
        if not isinstance(data, dict):
            return False
        try:
            if data.get("version") != 1 or data.get("seed") != self.seed:
                return False
            elapsed = max(0.0, time.time() - valor_real(data["saved_at"], 0.0, 1e13))

            saved_learned = data.get("learned", {})
            if not isinstance(saved_learned, dict):
                return False
            learned = np.array(self.learned, copy=True)
            for i, c in enumerate(self.sensory_names):
                por_canal = saved_learned.get(c, {})
                if not isinstance(por_canal, dict):
                    return False
                for j, post in enumerate(self.plastic_posts):
                    learned[i, j] = valor_real(por_canal.get(post, 0.0), LEARN_MIN, LEARN_MAX)
            if data.get("learned_version", 1) < 2:
                # v1: o sensor TYPING contava o mouse, então o carinho ensinou "digitar é bom"
                learned[self.sensory_names.index("TYPING"), :] = 0.0
                log("[nervous] aprendizado de TYPING zerado (vinha do mouse do carinho)")

            saved_eff = data.get("efficacy", {})
            if not isinstance(saved_eff, dict):
                return False
            recuperado = {}
            for name in self.sensory_names:
                if name not in saved_eff:
                    continue                    # canal novo: começa sem habituação
                p = self.pool(name)
                sl = slice(p["start"], p["start"] + p["n"])
                saved = np.array(saved_eff[name], dtype=float)
                if saved.shape != (p["n"],) or not np.isfinite(saved).all() or ((saved < 0) | (saved > 1)).any():
                    return False
                recuperado[name] = np.clip(1.0 - (1.0 - saved) * np.exp(-elapsed / self.s_tau_rec[sl]), 0.0, 1.0)

            # tudo validado: agora publica de uma vez
            self.learned[:] = learned
            self._apply_learning()
            for name, valores in recuperado.items():
                p = self.pool(name)
                self.p[p["start"]:p["start"] + p["n"]] = valores
            self.restored_after = elapsed
            return True
        except Exception as error:
            log(f"[nervous] estado ilegível ({error}); começando do zero")
            return False

# ============================================================
# DECODIFICADOR MOTOR
# ============================================================


class MotorDecoder:
    """
    Transforma as taxas motoras em UM comportamento atual.
    Sem motor acima do limiar = None (repouso). Histerese e tempo mínimo
    evitam tremer entre comportamentos; o susto interrompe qualquer coisa.
    """

    def __init__(self, threshold=6.0, margin=1.3, min_dwell=1.2, exit_ratio=0.5):
        """Guarda os limiares: força mínima, folga sobre o segundo e tempo mínimo de cada comportamento."""
        self.threshold = threshold
        self.exit_ratio = exit_ratio        # sai do comportamento abaixo de threshold*exit_ratio
        self.margin = margin
        self.min_dwell = min_dwell
        self.current = None
        self.since = float("-inf")      # primeira decisão não espera

    def update(self, activity, now=None):
        """Atualiza o comportamento atual a partir da atividade dos motores; respeita o tempo mínimo antes de trocar."""
        now = time.monotonic() if now is None else now

        top = max(activity, key=activity.get)
        candidate = top if activity[top] >= self.threshold else None
        exit_level = self.threshold * self.exit_ratio

        # Histerese: o comportamento atual só termina quando cai abaixo do limiar de saída
        if candidate is None and self.current is not None and activity[self.current] >= exit_level:
            candidate = self.current
        if activity.get("STARTLE", 0.0) >= self.threshold:
            candidate = "STARTLE"            # o susto tem prioridade

        if candidate == self.current:
            return self.current, False

        dwell = now - self.since
        urgent = candidate == "STARTLE"

        if not urgent:
            if dwell < self.min_dwell:
                return self.current, False
            if (
                candidate is not None
                and self.current is not None
                and activity[self.current] >= exit_level
                and activity[candidate] < self.margin * activity[self.current]
            ):
                return self.current, False

        self.current = candidate
        self.since = now
        return self.current, True


# ============================================================
# TESTE HEADLESS
# ============================================================


def _run(brain, intensities, seconds):
    """Roda a rede com estímulos fixos por alguns segundos e devolve o pico de cada motor (usado na demonstração)."""
    peak = {m: 0.0 for m in brain.motor_names}
    for _ in range(int(seconds * 10)):
        brain.stimulate(intensities)
        brain.step(100)
        for m, hz in brain.motor_activity().items():
            peak[m] = max(peak[m], hz)
    return peak


def _fmt(activity):
    """Formata a atividade dos motores numa linha curta, para imprimir."""
    return " ".join(f"{m[:4]}={hz:4.1f}" for m, hz in activity.items())


def demo():
    """Demonstração: roda a rede com alguns estímulos e imprime o que cada motor faz. Rode com `python -m pestinha.core.nervous_system`."""
    brain = LIFBrain()
    log(brain.describe())
    log()

    scenarios = [
        ("repouso", {}, 8),
        ("MOTION forte", {"MOTION": 1.0}, 3),
        ("NOVELTY", {"NOVELTY": 1.0}, 3),
        ("WORK + TYPING", {"WORK": 1.0, "TYPING": 0.8}, 10),
        ("PLAY", {"PLAY": 1.0}, 10),
        ("SOUND", {"SOUND": 1.0}, 10),
        ("WEB + NOVELTY", {"WEB": 1.0, "NOVELTY": 0.5}, 8),
        ("SILENCE 60s", {"SILENCE": 1.0}, 60),
        ("FATIGUE + SILENCE", {"FATIGUE": 0.8, "SILENCE": 1.0}, 20),
        ("POKE", {"POKE": 1.0}, 3),
        ("DRAG", {"DRAG": 1.0}, 4),
        ("DISMISS", {"DISMISS": 1.0}, 8),
        ("LONELY", {"LONELY": 1.0, "SILENCE": 0.5}, 20),
    ]

    for label, stim, secs in scenarios:
        fresh = LIFBrain()
        _run(fresh, {}, 2)
        peak = _run(fresh, stim, secs)
        log(f"{label:<20} {_fmt(peak)}")

    log("\nHABITUAÇÃO: o mesmo susto repetido (MOTION 1.5 s, pausa 6 s)")
    brain = LIFBrain()
    for trial in range(1, 13):
        peak = _run(brain, {"MOTION": 1.0}, 1.5)
        _run(brain, {}, 6)
        eff = brain.efficacy()["MOTION"]
        log(f"  #{trial:<2} STARTLE={peak['STARTLE']:5.1f} Hz   eficácia MOTION={eff:.2f}")

    log("\nDISHABITUAÇÃO: depois de ficar ausente (sem estímulo)")
    brain.p[:] = brain.p * 0 + np.array(brain.p)
    for secs in (60, 300, 600):
        for _ in range(int(secs * 10)):
            brain.stimulate({})
            brain.step(100)
        log(f"  +{secs:>3}s  eficácia MOTION={brain.efficacy()['MOTION']:.2f}")


if __name__ == "__main__":
    demo()