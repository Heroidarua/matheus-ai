# Auditorias

Relatórios das rodadas de revisão do Bryan, na ordem em que aconteceram. Cada um termina com a seção
**Estado das correções**, e cada bug corrigido tem um teste que o reproduz.

| Relatório | O que encontrou | Testes |
|---|---|---|
| [ANALISE_TECNICA.md](ANALISE_TECNICA.md) | 8 falhas: pânico incompleto, carga parcial, `NaN` na rede, schemas, pausa, apagar dados, rotina, condicionamento | `tests/test_robustez_v2.py` |
| [AUDITORIA_30_BUGS.md](AUDITORIA_30_BUGS.md) | 30 bugs de controle, dados, ciclo de vida, física e adaptadores | `tests/test_auditoria_30.py` |
| [TESTE_100_CANTINHO.md](TESTE_100_CANTINHO.md) | 100 cenários do cantinho do castigo | `tests/test_cantinho_cenarios.py` |
| [BUGS_NOVO_CASTIGO.md](BUGS_NOVO_CASTIGO.md) | 5 falhas nas funções do cantinho ligadas à rede | `tests/test_castigo_bugs_rede.py` |
| [BUGS_30_RODADA.md](BUGS_30_RODADA.md) | 30 bugs achados por fuzzing e revisão | `tests/test_30_bugs.py` |

As evidências (resultados em JSON, JUnit e saída das execuções) ficam em `evidencias/`. Os caminhos de
máquina foram trocados por `<raiz do projeto>` e `<temp>`.
