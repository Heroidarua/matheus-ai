"""
RÓTULOS - os nomes que aparecem na tela, em português.

Os nomes internos da rede (MOTION, TYPING, FOCUS...) ficam no código como estão.
Aqui fica só a tradução que o usuário vê, no monitor neural e nos textos.
"""

CANAIS_SENSORIAIS = {
    "MOTION": "movimento",
    "TYPING": "digitação",
    "NOVELTY": "novidade",
    "SILENCE": "silêncio",
    "WORK": "trabalho",
    "PLAY": "jogo",
    "SOUND": "música",
    "SOCIAL": "social",
    "WEB": "navegador",
    "FATIGUE": "cansaço",
    "POKE": "cutucada",
    "DRAG": "arraste",
    "DISMISS": "dispensa",
    "LONELY": "solidão",
    "CARESS": "carinho",
    "THROW": "arremesso",
    "IMPACT": "batida",
    "ANTICIPATE": "antecipação",
    "TOY_NEAR": "bolinha perto",
    "TOY_TAKEN": "bolinha levada",
    "BOREDOM": "tédio",
    "PEDIDO": "pedido de trabalho",
    "PRESO": "preso no canto",
    "LEMBRA_FUGA": "lembra de fugas",
    "RECUSA": "recusou pedido",
    "PLACA": "placa do castigo",
    "ANTECIPA_PLACA": "antecipa o canto",
    "VISITA": "visita no canto",
    "RECEIO": "receio de fugir",
    "RANCOR": "rancor",
}

INTERNEURONIOS = {
    "ALERT": "alerta",
    "FOCUS": "foco",
    "CURIOUS": "curiosidade",
    "PLAYFUL": "brincadeira",
    "CALM": "calma",
    "TIRED": "cansaço",
    "QUIET": "quietude",
    "INHIB": "inibição",
    "FRUSTRATION": "frustração",
    "GLOOM": "desânimo",
}

MOTORES = {
    "STARTLE": "susto",
    "WATCH": "observar",
    "WANDER": "passear",
    "CHEER": "alegria",
    "SETTLE": "sossego",
    "DROWSE": "sonolência",
    "ANGRY": "raiva",
    "SAD": "tristeza",
    "SENTAR": "sentar no notebook",
    "FUGIR": "fugir do canto",
    "CARTAZ": "colar cartaz",
    "CANTO": "ir para o cantinho",
    "TRAVESSURA": "aprontar",
    "PAPEL": "atirar papel",
    "ACEITAR": "aceitar o castigo",
}

GRUPOS = {"sensory": "sentido", "inter": "interneurônio", "motor": "motor"}


def nome_canal(nome):
    """Nome de exibição de qualquer população da rede."""
    return CANAIS_SENSORIAIS.get(nome) or INTERNEURONIOS.get(nome) or MOTORES.get(nome) or nome.lower()
