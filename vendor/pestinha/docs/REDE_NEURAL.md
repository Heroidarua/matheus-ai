# A rede neural do pet

> Gerado por `ferramentas/gerar_doc_rede.py` a partir do código. Não edite à mão: rode o script.

A rede tem **470 neurônios** de integração e disparo com vazamento (LIF), **15939 sinapses**, **30 canais sensoriais**, **10 populações de interneurônios** e **15 populações motoras**.

## Como o sinal anda

```text
computador e você ──► sentidos (0..1) ──► neurônios sensoriais (Poisson, com habituação)
                                               │
                                               ▼
                                   interneurônios (foco, curiosidade, raiva...)
                                               │
                                               ▼
            motores de expressão (corpo, emoção)    motores de decisão (sentar, fugir...)
                     │                                        │
                     ▼                                        ▼
          tom motor, olhar, emoção               limiares em Hz ou frequência = taxa × ganho
```

- **Habituação:** cada canal perde eficácia a cada disparo (`d`) e recupera em `tau_rec` segundos.
- **Temperamento:** `pets/*.json` multiplica as sinapses que saem dos sentidos (o mesmo estímulo pesa diferente em cada pet).
- **Inibição lateral:** motores competem só dentro do seu grupo (expressão com expressão, decisão com decisão).
- **Aprendizado por carinho:** regra de três fatores entre canais sensoriais e PLAYFUL/CALM/FRUSTRATION/GLOOM, com recompensa (+ carinho, − dispensa e castigo).
- **Condicionamento:** Rescorla–Wagner fora da rede (`core/conditioning.py`); a força prevista entra como `ANTICIPATE` (cutucada/arraste) e `ANTECIPA_PLACA` (cantinho).

## Canais sensoriais

| Canal | Nome no monitor | Habitua (d / tau_rec) | O que é |
|---|---|---|---|
| `MOTION` | movimento | 0.0004 / 600 s | troca de janela |
| `TYPING` | digitação | 7e-05 / 1200 s | teclado / mouse |
| `NOVELTY` | novidade | 0.0004 / 900 s | mudança de atividade / volta |
| `SILENCE` | silêncio | não | ausência de input (não habitua) |
| `WORK` | trabalho | 7e-05 / 1200 s | programando / projetando |
| `PLAY` | jogo | 0.0001 / 900 s | jogando |
| `SOUND` | música | 7e-05 / 1200 s | música |
| `SOCIAL` | social | 8e-05 / 900 s | chats |
| `WEB` | navegador | 8e-05 / 900 s | navegador |
| `FATIGUE` | cansaço | não | interno: pouca energia (homeostase; não habitua) |
| `POKE` | cutucada | 0.0009 / 150 s | cutucada: habitua rápido e volta em minutos |
| `DRAG` | arraste | 0.0002 / 600 s | sendo arrastado |
| `DISMISS` | dispensa | 5e-05 / 1800 s | travessura dispensada |
| `LONELY` | solidão | não | interno: carente de contato (homeostase; não habitua) |
| `CARESS` | carinho | não | carinho (mouse esfregando nele; não enjoa) |
| `ANTICIPATE` | antecipação | não | previsão aprendida (condicionamento); não habitua |
| `TOY_NEAR` | bolinha perto | não | a bolinha está perto dele |
| `TOY_TAKEN` | bolinha levada | 0.0002 / 600 s | você levou a bolinha para longe |
| `THROW` | arremesso | 0.0008 / 300 s | foi arremessado (a graça enjoa se repetir) |
| `IMPACT` | batida | 0.0002 / 600 s | bateu forte na parede/chão |
| `BOREDOM` | tédio | não | interno: pouca estimulação (homeostase; não habitua) |
| `PEDIDO` | pedido de trabalho | não | você pediu para ele trabalhar (vale por um tempo) |
| `PRESO` | preso no canto | 0.0004 / 900 s | preso no cantinho do castigo (habitua: ele se acostuma) |
| `LEMBRA_FUGA` | lembra de fugas | não | memória: fugas que já deram certo |
| `RECUSA` | recusou pedido | não | você pediu e ele não quis (frustração pontual) |
| `PLACA` | placa do castigo | 0.0001 / 1200 s | a placa do castigo está à vista (aviso) |
| `ANTECIPA_PLACA` | antecipa o canto | não | previsão aprendida de ir para o canto (só a pista da placa) |
| `VISITA` | visita no canto | não | você está perto dele enquanto ele está preso |
| `RECEIO` | receio de fugir | não | interno: fugas que deram errado (devolvido ao canto) |
| `RANCOR` | rancor | não | interno: tempo de castigo acumulado, decai devagar |

## Interneurônios

| População | Nome no monitor | Tipo | Neurônios | Entradas (peso) |
|---|---|---|---:|---|
| `ALERT` | alerta | excitatória | 16 | MOTION (+0.14), ANTICIPATE (+0.12), ANTECIPA_PLACA (+0.12), IMPACT (+0.10), POKE (+0.08), NOVELTY (+0.06), DRAG (+0.06), TOY_TAKEN (+0.06), CALM (−0.06), THROW (+0.05), TIRED (−0.05), QUIET (−0.04), INHIB (−0.04), PRESO (+0.04), PLAY (+0.03), DISMISS (+0.03), TYPING (+0.02), PLACA (+0.02) |
| `FOCUS` | foco | excitatória | 16 | WORK (+0.14), PEDIDO (+0.12), QUIET (−0.08), TYPING (+0.05), INHIB (−0.03) |
| `CURIOUS` | curiosidade | excitatória | 16 | BOREDOM (+0.12), NOVELTY (+0.10), DRAG (+0.07), WEB (+0.06), TOY_NEAR (+0.06), POKE (+0.05), ALERT (+0.05), QUIET (−0.05), SOCIAL (+0.04), GLOOM (−0.04), TIRED (−0.04), THROW (+0.03), INHIB (−0.03) |
| `PLAYFUL` | brincadeira | excitatória | 12 | TOY_NEAR (+0.10), BOREDOM (+0.09), PLAY (+0.08), POKE (+0.08), THROW (+0.08), GLOOM (−0.06), DRAG (+0.05), CARESS (+0.05), FRUSTRATION (−0.05), TIRED (−0.05), INHIB (−0.03), SOUND (+0.02) |
| `CALM` | calma | excitatória | 12 | CARESS (+0.07), SOUND (+0.06), FRUSTRATION (−0.06), VISITA (+0.05), WORK (+0.03), SILENCE (+0.03) |
| `TIRED` | cansaço | excitatória | 12 | FATIGUE (+0.08), SILENCE (+0.06) |
| `QUIET` | quietude | inibitória | 12 | SILENCE (+0.08), FATIGUE (+0.03), LONELY (+0.03) |
| `INHIB` | inibição | inibitória | 20 | ALERT (+0.10), FOCUS (+0.06), CURIOUS (+0.06), PLAYFUL (+0.06), FRUSTRATION (+0.04) |
| `FRUSTRATION` | frustração | excitatória | 12 | RECUSA (+0.25), CARTAZ (−0.20), DISMISS (+0.12), TOY_TAKEN (+0.10), PRESO (+0.10), IMPACT (+0.06), RANCOR (+0.04), DRAG (+0.03), CALM (−0.03) |
| `GLOOM` | desânimo | excitatória | 12 | TOY_TAKEN (+0.10), VISITA (−0.10), LONELY (+0.08), PLAYFUL (−0.05), RECUSA (+0.05), RECEIO (+0.04), DISMISS (+0.03), TIRED (+0.03), IMPACT (+0.02) |

## Motores

| Motor | Grupo | Nome no monitor | Entradas (peso) | Para que serve |
|---|---|---|---|---|
| `STARTLE` | expressão | susto | ALERT (+0.50), INHIB (−0.08) |  |
| `WATCH` | expressão | observar | FOCUS (+0.35), ALERT (+0.20), VISITA (+0.20), CURIOUS (+0.12), INHIB (−0.08), ANTICIPATE (+0.05) |  |
| `WANDER` | expressão | passear | CURIOUS (+0.35), FOCUS (−0.20), INHIB (−0.08) |  |
| `CHEER` | expressão | alegria | PLAYFUL (+0.70), INHIB (−0.08) |  |
| `SETTLE` | expressão | sossego | CALM (+0.50) |  |
| `DROWSE` | expressão | sonolência | TIRED (+0.30), CALM (+0.05) |  |
| `ANGRY` | expressão | raiva | FRUSTRATION (+0.55), ALERT (+0.05), INHIB (−0.04) |  |
| `SAD` | expressão | tristeza | GLOOM (+0.45) |  |
| `SENTAR` | decisão | sentar no notebook | GLOOM (−0.60), PEDIDO (+0.55), FOCUS (+0.45), PLAYFUL (−0.40), FRUSTRATION (−0.35), PRESO (−0.30), RANCOR (−0.30), CURIOUS (−0.25), ALERT (−0.10) | quer trabalhar no notebook |
| `FUGIR` | decisão | fugir do canto | RECEIO (−0.40), FRUSTRATION (+0.35), LEMBRA_FUGA (+0.30), CALM (−0.30), ANTECIPA_PLACA (+0.15), BOREDOM (+0.15) | tenta escapar do cantinho |
| `CARTAZ` | decisão | colar cartaz | FRUSTRATION (+0.25), CALM (−0.20) | cola um cartaz de protesto |
| `CANTO` | decisão | ir para o cantinho | GLOOM (+0.50), TIRED (+0.05) | vai para o cantinho |
| `TRAVESSURA` | decisão | aprontar | PLACA (−0.60), GLOOM (−0.50), BOREDOM (+0.30), CALM (−0.30), CURIOUS (+0.20), RANCOR (+0.15), PLAYFUL (+0.12) | apronta uma travessura (a taxa vira a frequência) |
| `PAPEL` | decisão | atirar papel | FRUSTRATION (+0.40), CALM (−0.40) | atira bolinha de papel (na revolução) |
| `ACEITAR` | decisão | aceitar o castigo | CALM (+0.45), FRUSTRATION (−0.40), CARESS (+0.30), RANCOR (−0.20), VISITA (+0.08) | aceita o castigo e sai do canto por conta própria (perdão) |

## Decisões pela rede

Os motores de decisão viram comportamento assim (valores em `pestinha/ajustes.py`):

| Decisão | Regra |
|---|---|
| Sentar no notebook | `SENTAR` ≥ 6 Hz senta; < 3 Hz levanta (histerese). |
| Fugir do cantinho | `FUGIR` acima de 2 Hz enche a vontade; 300 Hz·s a enchem (um pico não basta). |
| Perdoar o castigo | `ACEITAR` acima do limiar em `mind/castigo_ctl.py` (`LIMIAR_PERDAO_HZ`): sai sozinho, sem contar fuga. |
| Ir para o cantinho | `CANTO` ≥ 3 Hz. |
| Travessuras | por segundo: taxa de `TRAVESSURA` × 0.002. |
| Cartazes do castigo | por segundo: taxa de `CARTAZ` × 0.5 (cada um fica ao menos 8 s). |
| Bolinhas de papel | por segundo: taxa de `PAPEL` × 0.05 (só na revolução). |

Regras que ainda não são da rede: as condições do corpo (dormindo, segurado, no ar), os estágios do protesto (acúmulo com limiar), o sono pela energia e a escolha do tipo de travessura (memória episódica).
