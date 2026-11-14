"""
Gera docs/REDE_NEURAL.md a partir do código (canais, interneurônios, motores, conexões e limiares).

    python ferramentas/gerar_doc_rede.py

Rode de novo sempre que mexer em pestinha/core/nervous_system.py ou nos limiares de pestinha/ajustes.py.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402

from pestinha import ajustes  # noqa: E402
from pestinha.core import nervous_system as ns  # noqa: E402
from pestinha.ui.rotulos import CANAIS_SENSORIAIS, INTERNEURONIOS, MOTORES  # noqa: E402

FONTE = (RAIZ / "pestinha" / "core" / "nervous_system.py").read_text(encoding="utf-8")


def comentarios_sensoriais():
    ini = FONTE.index("SENSORY_SPEC = {")
    bloco = FONTE[ini:FONTE.index("\n}", ini)]
    return dict(re.findall(r'"([A-Z_]+)":\s*\([^)]*\),\s*#\s*(.*)', bloco))


def comentarios_motores():
    ini = FONTE.index("MOTOR_SPEC = [")
    bloco = FONTE[ini:FONTE.index("\n]", ini)]
    return dict(re.findall(r'\("([A-Z_]+)",[^)]*\),\s*#\s*(.*)', bloco))


def entradas_de(pos):
    pares = [(pre, w) for pre, alvo, w, _d in ns.CONNECTIONS if alvo == pos]
    return ", ".join(f"{pre} ({'+' if w > 0 else '−'}{abs(w):.2f})" for pre, w in sorted(pares, key=lambda p: -abs(p[1])))


def main():
    brain = ns.LIFBrain(seed=7)
    com_s, com_m = comentarios_sensoriais(), comentarios_motores()
    linhas = [
        "# A rede neural do pet",
        "",
        "> Gerado por `ferramentas/gerar_doc_rede.py` a partir do código. Não edite à mão: rode o script.",
        "",
        f"A rede tem **{brain.N} neurônios** de integração e disparo com vazamento (LIF), "
        f"**{int(np.count_nonzero(brain.W))} sinapses**, **{len(ns.SENSORY_SPEC)} canais sensoriais**, "
        f"**{len(ns.INTER_SPEC)} populações de interneurônios** e **{len(ns.MOTOR_SPEC)} populações motoras**.",
        "",
        "## Como o sinal anda",
        "",
        "```text",
        "computador e você ──► sentidos (0..1) ──► neurônios sensoriais (Poisson, com habituação)",
        "                                               │",
        "                                               ▼",
        "                                   interneurônios (foco, curiosidade, raiva...)",
        "                                               │",
        "                                               ▼",
        "            motores de expressão (corpo, emoção)    motores de decisão (sentar, fugir...)",
        "                     │                                        │",
        "                     ▼                                        ▼",
        "          tom motor, olhar, emoção               limiares em Hz ou frequência = taxa × ganho",
        "```",
        "",
        "- **Habituação:** cada canal perde eficácia a cada disparo (`d`) e recupera em `tau_rec` segundos.",
        "- **Temperamento:** `pets/*.json` multiplica as sinapses que saem dos sentidos (o mesmo estímulo pesa diferente em cada pet).",
        "- **Inibição lateral:** motores competem só dentro do seu grupo (expressão com expressão, decisão com decisão).",
        "- **Aprendizado por carinho:** regra de três fatores entre canais sensoriais e PLAYFUL/CALM/FRUSTRATION/GLOOM, "
        "com recompensa (+ carinho, − dispensa e castigo).",
        "- **Condicionamento:** Rescorla–Wagner fora da rede (`core/conditioning.py`); a força prevista entra como "
        "`ANTICIPATE` (cutucada/arraste) e `ANTECIPA_PLACA` (cantinho).",
        "",
        "## Canais sensoriais",
        "",
        "| Canal | Nome no monitor | Habitua (d / tau_rec) | O que é |",
        "|---|---|---|---|",
    ]
    for nome, (_n, _taxa, d, tau) in ns.SENSORY_SPEC.items():
        hab = "não" if d == 0 else f"{d:g} / {tau:g} s"
        linhas.append(f"| `{nome}` | {CANAIS_SENSORIAIS.get(nome, '')} | {hab} | {com_s.get(nome, '')} |")
    linhas += ["", "## Interneurônios", "", "| População | Nome no monitor | Tipo | Neurônios | Entradas (peso) |",
               "|---|---|---|---:|---|"]
    for nome, tipo, n, *_ in ns.INTER_SPEC:
        linhas.append(f"| `{nome}` | {INTERNEURONIOS.get(nome, '')} | {'excitatória' if tipo == 'exc' else 'inibitória'} "
                      f"| {n} | {entradas_de(nome)} |")
    linhas += ["", "## Motores", "", "| Motor | Grupo | Nome no monitor | Entradas (peso) | Para que serve |",
               "|---|---|---|---|---|"]
    for nome, n, *_ in ns.MOTOR_SPEC:
        grupo = "decisão" if nome in ns.DECISION_MOTORS else "expressão"
        linhas.append(f"| `{nome}` | {grupo} | {MOTORES.get(nome, '')} | {entradas_de(nome)} | {com_m.get(nome, '')} |")
    linhas += [
        "",
        "## Decisões pela rede",
        "",
        "Os motores de decisão viram comportamento assim (valores em `pestinha/ajustes.py`):",
        "",
        "| Decisão | Regra |",
        "|---|---|",
        f"| Sentar no notebook | `SENTAR` ≥ {ajustes.LIMIAR_SENTAR_HZ:g} Hz senta; < {ajustes.LIMIAR_LEVANTAR_HZ:g} Hz levanta (histerese). |",
        f"| Fugir do cantinho | `FUGIR` acima de {ajustes.LIMIAR_FUGA_HZ:g} Hz enche a vontade; {ajustes.CARGA_FUGA_HZ_S:g} Hz·s a enchem (um pico não basta). |",
        "| Perdoar o castigo | `ACEITAR` acima do limiar em `mind/castigo_ctl.py` (`LIMIAR_PERDAO_HZ`): sai sozinho, sem contar fuga. |",
        f"| Ir para o cantinho | `CANTO` ≥ {ajustes.LIMIAR_CANTO_HZ:g} Hz. |",
        f"| Travessuras | por segundo: taxa de `TRAVESSURA` × {ajustes.GANHO_TRAVESSURA:g}. |",
        f"| Cartazes do castigo | por segundo: taxa de `CARTAZ` × {ajustes.GANHO_CARTAZ:g} (cada um fica ao menos 8 s). |",
        f"| Bolinhas de papel | por segundo: taxa de `PAPEL` × {ajustes.GANHO_PAPEL:g} (só na revolução). |",
        "",
        "Regras que ainda não são da rede: as condições do corpo (dormindo, segurado, no ar), os estágios do "
        "protesto (acúmulo com limiar), o sono pela energia e a escolha do tipo de travessura (memória episódica).",
        "",
    ]
    destino = RAIZ / "docs" / "REDE_NEURAL.md"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    print(f"escrito: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
