# Rodada de 30 bugs (01/11/2026)

Como foram encontrados: um fuzzer que roda o app inteiro com relógio virtual, aplica ações
aleatórias e checa 29 invariantes depois de cada passo (`ferramentas/fuzz_pestinha.py`); a revisão
de código dos módulos; e reproduções dirigidas (`(removido do repositório)`). Cada bug tem
um teste em `tests/test_30_bugs.py`.

Depois das correções: 291 testes passam (incluindo os 100 cenários do cantinho), o fuzzer roda
150 sessões de 80 ações sem nenhuma violação nem exceção, e o pyflakes está limpo.

| # | Bug | Correção |
|---:|---|---|
| 01 | Ligar o cantinho com o Bryan escondido mostrava a placa. | A placa segue a visibilidade do Bryan. |
| 02 | Esconder o notebook com o app pausado deixava ele sentado num notebook invisível. | Esconder o notebook o faz levantar na hora. |
| 03 | Esconder no meio do arraste deixava o corpo preso no ar e o sinal de arraste ligado. | Sumir da tela cancela a interação. |
| 04 | Pânico no meio do arraste deixava o canal `DRAG` ligado para sempre. | Idem 03. |
| 05 | Guardar a bolinha no meio do arraste a deixava "na mão" para sempre (ele nunca mais brincava). | Bolinha que some é largada. |
| 06 | Abrir um painel com a bandeja escondendo os painéis: aparecia e sumia no quadro seguinte. | Painel aberto à mão fica; "esconder painéis" fecha também os abertos. |
| 07 | Pedir trabalho com ele preso (ou impossibilitado) contava como recusa e frustrava. | Só é recusa se ele pôde sentar durante o pedido. |
| 08 | "Fazer uma travessura agora" com ele preso ficava pendente e disparava muito depois. | O pedido do menu vale 10 s. |
| 09 | Queda alta até o canto (pouso depois de 1,5 s) não ensinava a pista da placa. | Janela própria de 4 s para a placa. |
| 10 | Um quadro depois de "apagar tudo" recriava a pasta `memory/`. | Nenhum quadro roda depois de apagar. |
| 11 | Painéis, notebook e placa: soltar outro botão encerrava o arraste. | O arraste só termina com o botão que o começou. |
| 12 | Monitor neural: 9 canais e 7 motores novos sem rótulo em português. | Rótulos acrescentados. |
| 13 | `FOCO_MAXIMO_HZ` duplicado: o valor de `ajustes.py` era ignorado pela mesa. | Uma fonte só. |
| 14 | Seis constantes de ajuste e o agendador antigo de travessuras sem efeito nenhum. | Removidos. |
| 15 | Tom motor e emoção integravam 0,1 s por ciclo, não o tempo real. | Passam a usar o tempo real do ciclo. |
| 16 | Protesto e tristeza: idem. | Idem. |
| 17 | Aprendizado da rede: idem. | Idem. |
| 18 | Estímulo e contato do carinho: idem. | Idem. |
| 19 | Registro da rotina (emoção e interação): idem. | Idem. |
| 20 | Euforia dos fogos acumulava por ciclo, não por tempo. | Escala pelo tempo do ciclo. |
| 21 | Detecção do cursor se aproximando dividia por 0,1 s fixo. | Divide pelo tempo real. |
| 22 | Imagem corrompida ou num formato não suportado virava uma travessura invisível. | Imagem ilegível não vira objeto. |
| 23 | **Tela inicial descartava as escolhas da pessoa** (o diálogo trabalhava numa cópia). | `main.py` aplica cada escolha no store. |
| 24 | Tela inicial: "Apagar todos os dados" não fazia nada. | Apaga e sai. |
| 25 | Interface ainda dizia "DeskBuddy" (bandeja, notificações, títulos). | Agora "Bryan". |
| 26 | O resumo de assets ignorava memes de trabalho e bilhetes tristes. | Conta os dois. |
| 27 | Pausar no meio de uma fuga do cantinho a cancelava (e vencia entrada e cartaz). | A pausa desloca os prazos do cantinho. |
| 28 | Pausar depois de pedir trabalho fazia o pedido vencer. | A pausa desloca o prazo do pedido. |
| 29 | Arrastar, arremessar, dar carinho pelo menu, pedir para dormir e dispensar travessuras mudavam o estado durante a pausa. | Pausado, essas interações não mexem no estado. |
| 30 | A área que prende o Bryan ficava sempre no chão, mesmo com a placa no alto de uma janela. | A área segue a base da placa. |

O 23 foi introduzido na rodada anterior, quando o diálogo passou a trabalhar numa cópia para
corrigir a transição da rotina.
