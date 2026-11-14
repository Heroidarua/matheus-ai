# Auditoria: 30 bugs reproduzidos no Bryan

Data: **31/10/2026**. Projeto: `<raiz do projeto>`.

Esta rodada analisou o código **depois** das oito correções descritas em
ANALISE_TECNICA.md. Não presume que as falhas antigas continuem abertas: os 95
testes existentes passaram antes da adição desta suíte de auditoria.

## Resultado verificável

- **30 cenários distintos reproduzidos**, com um teste por contrato e inspeção das falhas reais.
- **10 de prioridade alta e 20 de prioridade média**. Prioridade alta aqui inclui bypass do controle de sessão, falha de saída e erros de dados que interrompem fluxos essenciais.
- Suíte integrada: **95 passaram + 30 XFAIL**, em 11,57 s.
- Com `--runxfail`: **30 falharam**, como esperado, em 1,10 s.
- Pyflakes limpo em `bryan`, `tests` e `main.py`.
- Não há erro de fixture contado como bug: o JUnit da execução sem XFAIL contém exatamente 30 falhas de teste e nenhum erro de preparação/limpeza.

**XFAIL significa falha conhecida aberta, não teste aprovado nem correção.** Os marcadores são
strict=True: se uma futura mudança atender ao contrato, o XPASS deverá ser revisado e o marcador removido.

Os testes usam Qt offscreen, diretórios temporários e mocks para atalho global,
processo ativo e cenários de erro. Os cenários físicos e de visibilidade são
reproduções de lógica/Qt; não substituem inspeção visual de foco, DPI ou telas reais.

Nenhum código de produção foi corrigido nesta tarefa. Foram adicionados testes,
este relatório e evidências. Não foram feitas alterações de comportamento nos
arquivos de `bryan/`.

## Índice dos 30 casos

| ID | Prioridade | Falha |
|---|---|---|
| BUG-01 | Alta | [Configuração antiga religa o Bryan depois do pânico](#bug-01) |
| BUG-02 | Alta | [Pânico depende de conseguir escrever as permissões](#bug-02) |
| BUG-03 | Alta | [Sair pode falhar porque um save de condicionamento falhou](#bug-03) |
| BUG-04 | Média | [Cartaz de fim aparece com o Bryan escondido](#bug-04) |
| BUG-05 | Média | [Cutucada ainda modifica o estado durante a pausa](#bug-05) |
| BUG-06 | Média | [Fogos continuam animando enquanto a sessão está pausada](#bug-06) |
| BUG-07 | Média | [Desativar a permissão de fogos não interrompe o efeito atual](#bug-07) |
| BUG-08 | Média | [Pausa não preserva o prazo dos episódios pendentes](#bug-08) |
| BUG-09 | Média | [Bolinha guardada continua estimulando a rede](#bug-09) |
| BUG-10 | Média | [Fazer uma travessura agora não força nenhuma tentativa](#bug-10) |
| BUG-11 | Média | [Peso de post-it igual a zero não desliga esse comportamento](#bug-11) |
| BUG-12 | Média | [Pet chuta a bolinha enquanto o usuário a segura](#bug-12) |
| BUG-13 | Média | [Soltar o botão direito encerra o arraste pelo esquerdo](#bug-13) |
| BUG-14 | Média | [Colisão não remove a bolinha de dentro de um objeto](#bug-14) |
| BUG-15 | Média | [Pouso escolhe plataforma inferior e atravessa a superior](#bug-15) |
| BUG-16 | Média | [Pânico durante arraste deixa o corpo preso ao religar](#bug-16) |
| BUG-17 | Média | [Posição antiga pode tornar um painel inacessível](#bug-17) |
| BUG-18 | Alta | [Schema inválido em panels.json causa TypeError na criação da janela](#bug-18) |
| BUG-19 | Alta | [Schema inválido do castigo impede construir o controlador](#bug-19) |
| BUG-20 | Alta | [Schema inválido do protesto ainda interrompe a carga](#bug-20) |
| BUG-21 | Alta | [Definição de pet inválida passa até quebrar a rede](#bug-21) |
| BUG-22 | Alta | [Bytes UTF-8 inválidos derrubam a leitura de episódios inteira](#bug-22) |
| BUG-23 | Alta | [Valência textual é validada, mas não normalizada](#bug-23) |
| BUG-24 | Alta | [Contagem infinita das preferências produz estimativa NaN](#bug-24) |
| BUG-25 | Média | [Atraso de callback perde tempo da dinâmica neural](#bug-25) |
| BUG-26 | Média | [Apagar histórico permite regravar o minuto apagado](#bug-26) |
| BUG-27 | Média | [Desligar Travessuras mantém objetos existentes na tela](#bug-27) |
| BUG-28 | Média | [Rotina desligada continua acumulando métricas para reuso](#bug-28) |
| BUG-29 | Média | [A leitura de janelas consulta títulos apesar do contrato de privacidade](#bug-29) |
| BUG-30 | Média | [Janela que desaparece durante a leitura gera exceção não tratada](#bug-30) |

## Como reproduzir

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -B -m pytest tests/test_auditoria_30.py -q -rx --tb=short
# Para observar as 30 falhas sem o marcador de falha conhecida:
python -B -m pytest tests/test_auditoria_30.py --runxfail -q --tb=short
# Para escolher somente um caso:
python -B -m pytest tests/test_auditoria_30.py -k test_01 --runxfail -q --tb=short
```

O retorno não zero de `--runxfail` é esperado enquanto os bugs estiverem abertos.
A execução normal de toda a suíte mantém a distinção entre os 95 contratos já
atendidos e os 30 contratos pendentes desta auditoria.

## Evidências preservadas

- [Resultados por caso e hashes das fontes](evidencias/auditoria_30/resultados.json).
- [JUnit das reproduções sem XFAIL](evidencias/auditoria_30/reproducoes.xml).
- [JUnit da suíte integrada](evidencias/auditoria_30/suite-integrada.xml).
- [Código dos 30 cenários](../../tests/test_auditoria_30.py).

As evidências preservam as mensagens observadas e a localização dos testes;
use --tb=short para obter o rastro detalhado na reprodução. O relatório
abaixo resume a condição, o efeito observado e a correção indicada, sem transformar
limitação de modelo ou preferência de arquitetura em item adicional da contagem.

<a id="bug-01"></a>

### BUG-01 — Configuração antiga religa o Bryan depois do pânico

**Prioridade:** alta. **Fonte:** [bryan/ui/ui.py:239](../../bryan/ui/ui.py#L239) — `set_active`.

**Reprodução:** Abrir Configurações com o Bryan ativo, acionar pânico e depois alterar somente a opção Memes nessa mesma janela.

**Observado:** A opção ativo volta a True. O checkbox foi desmarcado, mas a cópia interna do diálogo ainda contém ativo=True; _set emite novamente o dicionário inteiro.

**Correção indicada:** Sincronizar o estado do diálogo após mudanças externas ou emitir somente o campo alterado, sem sobrescrever campos de uma cópia antiga.

**Teste:** [test_01_configuracao_aberta_nao_reverte_panico](../../tests/test_auditoria_30.py#L79).

<a id="bug-02"></a>

### BUG-02 — Pânico depende de conseguir escrever as permissões

**Prioridade:** alta. **Fonte:** [bryan/app.py:692](../../bryan/app.py#L692) — `panic`.

**Reprodução:** Injetar OSError em SettingsStore.save e acionar o pânico com o pet visível.

**Observado:** A exceção interrompe panic antes de update_visibility. O pet permanece visível, apesar de ativo já ter sido colocado em False. frame verifica visibilidade e pausa, não esse flag.

**Correção indicada:** Executar desligamento visual e cancelamentos mesmo com falha de disco; persistir em bloco separado e registrar a falha.

**Teste:** [test_02_panico_ainda_esconde_tudo_se_disco_falhar](../../tests/test_auditoria_30.py#L88).

<a id="bug-03"></a>

### BUG-03 — Sair pode falhar porque um save de condicionamento falhou

**Prioridade:** alta. **Fonte:** [bryan/app.py:746](../../bryan/app.py#L746) — `quit`.

**Reprodução:** Injetar OSError em Conditioning.save e solicitar saída.

**Observado:** BryanApp.save chama conditioning.save sem proteção. A exceção impede quit de alcançar QApplication.quit e a limpeza dos objetos.

**Correção indicada:** Separar tentativa de salvar do encerramento; garantir limpeza e saída em finally, relatando quais estados não puderam ser gravados.

**Teste:** [test_03_sair_continua_se_condicionamento_nao_puder_salvar](../../tests/test_auditoria_30.py#L99).

<a id="bug-04"></a>

### BUG-04 — Cartaz de fim aparece com o Bryan escondido

**Prioridade:** média. **Fonte:** [bryan/mind/protest_ctl.py:83](../../bryan/mind/protest_ctl.py#L83) — `show`.

**Reprodução:** Esconder o Bryan e encerrar um estágio de tristeza, executando a transição de 1 para 0.

**Observado:** ProtestController.show chama sign.setVisible(True) sem consultar a visibilidade da sessão. O cartaz final fica visível mesmo com o pet oculto.

**Correção indicada:** Armazenar/aplicar a visibilidade desejada no controlador também na criação de novos cartazes, não apenas em update_visibility.

**Teste:** [test_04_fim_de_tristeza_nao_mostra_cartaz_quando_oculto](../../tests/test_auditoria_30.py#L111).

<a id="bug-05"></a>

### BUG-05 — Cutucada ainda modifica o estado durante a pausa

**Prioridade:** média. **Fonte:** [bryan/app.py:491](../../bryan/app.py#L491) — `on_poke`.

**Reprodução:** Pausar e clicar no pet, que permanece visível, ou chamar o handler que recebe esse clique.

**Observado:** A estimulação sobe de 0,60 para 0,75; condicionamento e memória também recebem a interação. _congelado protege think e sense, mas não esse caminho de eventos.

**Correção indicada:** Aplicar a política da sessão aos handlers de interação ou impedir esses eventos durante a pausa, de acordo com o contrato escolhido.

**Teste:** [test_05_cutucada_nao_altera_estado_durante_pausa](../../tests/test_auditoria_30.py#L121).

<a id="bug-06"></a>

### BUG-06 — Fogos continuam animando enquanto a sessão está pausada

**Prioridade:** média. **Fonte:** [bryan/world/fireworks.py:62](../../bryan/world/fireworks.py#L62) — `_step`.

**Reprodução:** Lançar um fogo e pausar o Bryan.

**Observado:** O QTimer próprio de Fireworks continua ativo. O guard em BryanApp.frame não controla esse timer independente.

**Correção indicada:** Adicionar pausa/retomada explícitas no controlador de efeitos e ligá-las ao lifecycle da sessão.

**Teste:** [test_06_pausa_para_timer_independente_dos_fogos](../../tests/test_auditoria_30.py#L130).

<a id="bug-07"></a>

### BUG-07 — Desativar a permissão de fogos não interrompe o efeito atual

**Prioridade:** média. **Fonte:** [bryan/app.py:581](../../bryan/app.py#L581) — `update_visibility`.

**Reprodução:** Lançar um fogo e desmarcar Fogos de artifício durante a animação.

**Observado:** A janela do efeito continua visível. A permissão é verificada para novos lançamentos, mas o efeito existente só é escondido quando o pet inteiro perde visibilidade.

**Correção indicada:** Revogar também a exibição/execução do efeito em andamento ao desativar sua permissão.

**Teste:** [test_07_desligar_fogos_recolhe_efeito_ja_aberto](../../tests/test_auditoria_30.py#L138).

<a id="bug-08"></a>

### BUG-08 — Pausa não preserva o prazo dos episódios pendentes

**Prioridade:** média. **Fonte:** [bryan/core/episodic.py:142](../../bryan/core/episodic.py#L142) — `tick`.

**Reprodução:** Iniciar um episódio nada, pausar por 120 segundos virtuais, retomar e executar um think.

**Observado:** O episódio é resolvido imediatamente como nada aconteceu, porque sua idade inclui o intervalo pausado. A lista de episódios abertos cai de 1 para 0.

**Correção indicada:** Usar tempo ativo de sessão ou deslocar timestamps/deadlines pendentes durante a retomada. A reprodução mostra expiração, não recompensa positiva.

**Teste:** [test_08_tempo_pausado_nao_expira_episodio_pendente](../../tests/test_auditoria_30.py#L146).

<a id="bug-09"></a>

### BUG-09 — Bolinha guardada continua estimulando a rede

**Prioridade:** média. **Fonte:** [bryan/app.py:286](../../bryan/app.py#L286) — `think`.

**Reprodução:** Colocar a bolinha perto do pet, usar Guardar a bolinha e executar um ciclo de pensamento.

**Observado:** TOY_NEAR permanece 1,0. O cálculo usa coordenadas da bolinha sem verificar ball_stored ou sua visibilidade; verifica somente a permissão bolinha.

**Correção indicada:** Não alimentar proximidade/retirada com um objeto ausente; redefinir o tracker ao guardar/desativar o brinquedo.

**Teste:** [test_09_bolinha_guardada_nao_estimula_rede](../../tests/test_auditoria_30.py#L158).

<a id="bug-10"></a>

### BUG-10 — Fazer uma travessura agora não força nenhuma tentativa

**Prioridade:** média. **Fonte:** [bryan/app.py:678](../../bryan/app.py#L678) — `menu_mischief`.

**Reprodução:** Disponibilizar um bilhete, pet apoiado e permissões válidas, zerar TRAVESSURA e usar o comando do menu.

**Observado:** O comando altera engine.next_time, mas maybe_act não consulta due/next_time e retorna None pelo gate probabilístico neural.

**Correção indicada:** Conectar o comando a uma solicitação explícita consumida pelo controlador, preservando permissões e limites de objetos.

**Teste:** [test_10_comando_agora_nao_depende_de_disparo_espontaneo](../../tests/test_auditoria_30.py#L167).

<a id="bug-11"></a>

### BUG-11 — Peso de post-it igual a zero não desliga esse comportamento

**Prioridade:** média. **Fonte:** [bryan/mind/mischief_ctl.py:36](../../bryan/mind/mischief_ctl.py#L36) — `maybe_act`.

**Reprodução:** Definir postit_weight=0, manter bilhetes permitidos e uma preferência aprendida que escolha bilhete.

**Observado:** A ação bilhete ainda é executada. O peso controla apenas um bônus de escolha, enquanto available e o bandit continuam oferecendo o comportamento. Isso contraria o contrato documentado de peso zero desligar.

**Correção indicada:** Filtrar as ações pelo estilo/pesos antes da escolha da memória, mantendo os pesos como restrições quando forem zero.

**Teste:** [test_11_peso_postit_zero_realmente_desliga_postit](../../tests/test_auditoria_30.py#L178).

<a id="bug-12"></a>

### BUG-12 — Pet chuta a bolinha enquanto o usuário a segura

**Prioridade:** média. **Fonte:** [bryan/body/brincadeira.py:52](../../bryan/body/brincadeira.py#L52) — `tick`.

**Reprodução:** Arrastar a bolinha perto de um pet feliz e executar a decisão de brincar com sorteio favorável.

**Observado:** Play.tick retorna kick mesmo com ball.dragging=True. O teste de posse existe em push_from_cursor, mas não na brincadeira do pet.

**Correção indicada:** Respeitar a posse pelo usuário antes de qualquer chute/arremesso autônomo e evitar acumular velocidade escondida durante o arraste.

**Teste:** [test_12_bryan_nao_chuta_bola_segurada_pelo_usuario](../../tests/test_auditoria_30.py#L190).

<a id="bug-13"></a>

### BUG-13 — Soltar o botão direito encerra o arraste pelo esquerdo

**Prioridade:** média. **Fonte:** [bryan/body/bolinha.py:133](../../bryan/body/bolinha.py#L133) — `mouseReleaseEvent`.

**Reprodução:** Durante um arraste esquerdo da bolinha, pressionar e soltar o botão direito mantendo o esquerdo.

**Observado:** mouseReleaseEvent não verifica qual botão foi solto; dragging vira False.

**Correção indicada:** Encerrar o arraste somente no release do botão que o iniciou.

**Teste:** [test_13_soltar_botao_direito_nao_encerra_arraste_esquerdo](../../tests/test_auditoria_30.py#L200).

<a id="bug-14"></a>

### BUG-14 — Colisão não remove a bolinha de dentro de um objeto

**Prioridade:** média. **Fonte:** [bryan/body/toy.py:44](../../bryan/body/toy.py#L44) — `bounce_off`.

**Reprodução:** Colocar o centro da bolinha em (150,150), dentro do retângulo (100,100,100,100), e resolver a colisão.

**Observado:** O centro termina em (133,150), ainda dentro do retângulo. O ramo de centro interno usa raio−1 em vez da distância até a face mais o raio.

**Correção indicada:** Calcular a penetração correta no ramo interno e projetar o círculo inteiro para fora da face mais próxima.

**Teste:** [test_14_colisao_retira_centro_do_interior_do_retangulo](../../tests/test_auditoria_30.py#L208).

<a id="bug-15"></a>

### BUG-15 — Pouso escolhe plataforma inferior e atravessa a superior

**Prioridade:** média. **Fonte:** [bryan/core/physics.py:57](../../bryan/core/physics.py#L57) — `step`.

**Reprodução:** Em uma queda que cruza plataformas y=120 e y=150 no mesmo passo, fornecer a inferior primeiro, como pode ocorrer numa lista ordenada por z.

**Observado:** Body registra surface=150, embora a primeira superfície cruzada esteja em 120.

**Correção indicada:** Selecionar a primeira colisão no trajeto da queda entre todas as candidatas, sem depender da ordem da lista de janelas.

**Teste:** [test_15_pouso_escolhe_primeira_superficie_cruzada_na_queda](../../tests/test_auditoria_30.py#L216).

<a id="bug-16"></a>

### BUG-16 — Pânico durante arraste deixa o corpo preso ao religar

**Prioridade:** média. **Fonte:** [bryan/app.py:692](../../bryan/app.py#L692) — `panic`.

**Reprodução:** Acionar pânico enquanto body.held e PetWindow.dragging estão ativos, e depois religar o pet.

**Observado:** Os flags de arraste permanecem ativos. Body.step retorna imediatamente quando held é True, deixando o corpo sem gravidade até um evento posterior de liberação.

**Correção indicada:** Cancelar e limpar a interação em andamento ao esconder/desligar, incluindo press, grab, held e estado sensorial de arraste.

**Teste:** [test_16_panico_cancela_arraste_para_permitir_gravidade_ao_religar](../../tests/test_auditoria_30.py#L224).

<a id="bug-17"></a>

### BUG-17 — Posição antiga pode tornar um painel inacessível

**Prioridade:** média. **Fonte:** [bryan/world/arrastavel.py:33](../../bryan/world/arrastavel.py#L33) — `__init__`.

**Reprodução:** Salvar a posição de um painel fora de todas as telas atuais, por exemplo após remover um monitor, e reabrir o painel.

**Observado:** A posição é usada literalmente; o frame do painel não intersecta nenhuma área disponível de tela.

**Correção indicada:** Validar posições contra as telas atuais e recuperar uma posição acessível quando a geometria mudou.

**Teste:** [test_17_posicao_antiga_fora_das_telas_e_recuperada](../../tests/test_auditoria_30.py#L235).

<a id="bug-18"></a>

### BUG-18 — Schema inválido em panels.json causa TypeError na criação da janela

**Prioridade:** alta. **Fonte:** [bryan/world/arrastavel.py:33](../../bryan/world/arrastavel.py#L33) — `__init__`.

**Reprodução:** Usar um panels.json válido como JSON, mas contendo notebook="x", e criar a janela correspondente.

**Observado:** O código desempacota o valor salvo e chama QWidget.move(str), que levanta TypeError. O notebook é criado no startup do app.

**Correção indicada:** Validar o par de coordenadas, seus tipos e intervalo antes de usar move; recorrer a posição padrão para entradas inválidas.

**Teste:** [test_18_posicao_com_schema_errado_usa_padrao](../../tests/test_auditoria_30.py#L244).

<a id="bug-19"></a>

### BUG-19 — Schema inválido do castigo impede construir o controlador

**Prioridade:** alta. **Fonte:** [bryan/mind/castigo_ctl.py:75](../../bryan/mind/castigo_ctl.py#L75) — `__init__`.

**Reprodução:** Gravar castigo.json com vitorias.fugir="erro" e construir CastigoController.

**Observado:** A conversão direta para float levanta ValueError, sem fallback. Esse controlador é construído na inicialização de BryanApp.

**Correção indicada:** Validar o estado persistente do castigo, com contagem finita não negativa e fallback sem aplicação parcial.

**Teste:** [test_19_estado_de_castigo_invalido_nao_impede_criacao](../../tests/test_auditoria_30.py#L252).

<a id="bug-20"></a>

### BUG-20 — Schema inválido do protesto ainda interrompe a carga

**Prioridade:** alta. **Fonte:** [bryan/core/protesto.py:156](../../bryan/core/protesto.py#L156) — `load`.

**Reprodução:** Gravar protest.json com grievance="erro" e carregar o estado.

**Observado:** Protesto.load levanta ValueError. A validação adicionada à homeostase e à memória não alcançou esse estado de protesto/tristeza.

**Correção indicada:** Converter/validar campos em temporários, rejeitar conteúdo incompatível e manter defaults válidos sem derrubar a inicialização.

**Teste:** [test_20_estado_de_protesto_invalido_nao_impede_carga](../../tests/test_auditoria_30.py#L260).

<a id="bug-21"></a>

### BUG-21 — Definição de pet inválida passa até quebrar a rede

**Prioridade:** alta. **Fonte:** [bryan/config.py:214](../../bryan/config.py#L214) — `load_pet`.

**Reprodução:** Criar um pets/ruim.json com seed="invalida" e selecionar esse pet.

**Observado:** load_pet publica o valor sem validar; a construção da rede falha com TypeError de SeedSequence.

**Correção indicada:** Validar definição do pet antes da montagem e informar o erro de configuração de forma recuperável, ou oferecer um perfil padrão seguro.

**Teste:** [test_21_definicao_de_pet_com_seed_invalida_usa_padrao](../../tests/test_auditoria_30.py#L269).

<a id="bug-22"></a>

### BUG-22 — Bytes UTF-8 inválidos derrubam a leitura de episódios inteira

**Prioridade:** alta. **Fonte:** [bryan/store.py:51](../../bryan/store.py#L51) — `read_lines`.

**Reprodução:** Introduzir uma linha com bytes inválidos para UTF-8 no arquivo de episódios e executar load.

**Observado:** UnicodeDecodeError escapa de read_lines, que captura somente OSError. O descarte de linhas JSON inválidas nem chega a executar.

**Correção indicada:** Tratar problemas de decodificação de forma explícita e preservar/recuperar os registros válidos quando possível.

**Teste:** [test_22_linha_com_utf8_invalido_nao_derruba_memoria](../../tests/test_auditoria_30.py#L279).

<a id="bug-23"></a>

### BUG-23 — Valência textual é validada, mas não normalizada

**Prioridade:** alta. **Fonte:** [bryan/core/episodic.py:41](../../bryan/core/episodic.py#L41) — `_episodio_valido`.

**Reprodução:** Ler episódio com contexto/ação válidos e valencia="0.5", e executar consolidate.

**Observado:** A validação aceita float("0.5"), mas devolve o registro original. consolidate tenta multiplicar peso float pela string e levanta TypeError.

**Correção indicada:** Rejeitar tipos textuais ou produzir um registro normalizado com valência numérica antes de armazenar e consolidar.

**Teste:** [test_23_valencia_textual_validada_e_normalizada_antes_de_consolidar](../../tests/test_auditoria_30.py#L288).

<a id="bug-24"></a>

### BUG-24 — Contagem infinita das preferências produz estimativa NaN

**Prioridade:** alta. **Fonte:** [bryan/core/episodic.py:50](../../bryan/core/episodic.py#L50) — `_estatistica_valida`.

**Reprodução:** Carregar preferencias com contagem 1e400 e média 0,5, e consultar estimate.

**Observado:** O parse padrão converte o expoente para infinito. A validação de contagem só verifica n<0, aceita infinito, e a estimativa resulta NaN.

**Correção indicada:** Validar math.isfinite para contagens e médias; rejeitar overflow de float na camada JSON e respeitar o domínio estatístico das preferências.

**Teste:** [test_24_contagem_infinita_nao_produz_estimativa_nan](../../tests/test_auditoria_30.py#L297).

<a id="bug-25"></a>

### BUG-25 — Atraso de callback perde tempo da dinâmica neural

**Prioridade:** média. **Fonte:** [bryan/app.py:286](../../bryan/app.py#L286) — `think`.

**Reprodução:** Executar um think, avançar monotonic em 1 segundo sem pausar e executar o próximo.

**Observado:** A rede avança apenas 100 ms. Homeostase, emoção e aprendizado também recebem 0,1 fixo, enquanto sensores e deadlines usam o tempo real.

**Correção indicada:** Medir dt ativo e integrar com subpassos limitados, distinguindo callback atrasado de suspensão longa. Esse risco já constava como pendência da análise anterior.

**Teste:** [test_25_integracao_nao_perde_tempo_em_callback_atrasado](../../tests/test_auditoria_30.py#L307).

<a id="bug-26"></a>

### BUG-26 — Apagar histórico permite regravar o minuto apagado

**Prioridade:** média. **Fonte:** [bryan/ui/ui.py:207](../../bryan/ui/ui.py#L207) — `_wipe_history`.

**Reprodução:** Acumular um minuto parcial válido em RAM, confirmar Apagar histórico e depois executar flush.

**Observado:** timeline.csv reaparece com os dados anteriores à exclusão, pois o botão remove só o arquivo e não limpa o acumulador do app.

**Correção indicada:** Fazer a exclusão passar pelo controlador da timeline, descartando o buffer anterior e iniciando uma janela nova de coleta.

**Teste:** [test_26_apagar_historico_descarta_minuto_anterior_em_ram](../../tests/test_auditoria_30.py#L318).

<a id="bug-27"></a>

### BUG-27 — Desligar Travessuras mantém objetos existentes na tela

**Prioridade:** média. **Fonte:** [bryan/app.py:581](../../bryan/app.py#L581) — `update_visibility`.

**Reprodução:** Exibir um post-it e desmarcar o interruptor mestre Travessuras.

**Observado:** O post-it permanece visível. As permissões bloqueiam novas decisões, mas mischief.set_visible recebe somente a visibilidade geral do pet.

**Correção indicada:** Definir e aplicar a revogação aos objetos já exibidos, recolhendo ou escondendo-os imediatamente ao desligar o interruptor mestre.

**Teste:** [test_27_revogar_travessuras_recolhe_objetos_ja_exibidos](../../tests/test_auditoria_30.py#L330).

<a id="bug-28"></a>

### BUG-28 — Rotina desligada continua acumulando métricas para reuso

**Prioridade:** média. **Fonte:** [bryan/app.py:286](../../bryan/app.py#L286) — `think`.

**Reprodução:** Manter rotina=False e executar pensamento, ainda no mesmo minuto da timeline.

**Observado:** O contador de emoções da timeline recebe 0,1. As chamadas note_emotion/note_interaction não usam a permissão; o buffer pode contaminar um minuto coletado após religar.

**Correção indicada:** Respeitar o opt-out também nos acumuladores e definir um reset na ativação de uma nova sessão de coleta.

**Teste:** [test_28_rotina_desligada_nao_acumula_emocoes_para_proximo_minuto](../../tests/test_auditoria_30.py#L340).

<a id="bug-29"></a>

### BUG-29 — A leitura de janelas consulta títulos apesar do contrato de privacidade

**Prioridade:** média. **Fonte:** [bryan/sense/senses.py:124](../../bryan/sense/senses.py#L124) — `list_windows`.

**Reprodução:** Enumerar uma janela visível com os adaptadores Win32 instrumentados.

**Observado:** GetWindowText é chamado para testar título não vazio. PRIVACIDADE.md e o README de sense declaram que títulos nunca são lidos.

**Correção indicada:** Retirar a leitura se a política continua sendo apenas processo/geometria, ou revisar explicitamente o contrato com o usuário. Não foi observado envio nem gravação de títulos.

**Teste:** [test_29_levantamento_de_janelas_nao_le_titulos](../../tests/test_auditoria_30.py#L348).

<a id="bug-30"></a>

### BUG-30 — Janela que desaparece durante a leitura gera exceção não tratada

**Prioridade:** média. **Fonte:** [bryan/sense/senses.py:64](../../bryan/sense/senses.py#L64) — `get_active_app`.

**Reprodução:** GetForegroundWindow devolve um handle, mas GetWindowThreadProcessId levanta erro Win32 1400 antes da consulta ao processo.

**Observado:** pywintypes.error escapa: o handler captura erros de processo e ValueError, não a corrida de validade do HWND.

**Correção indicada:** Tratar a corrida esperada no adaptador e produzir unknown.exe, preservando registro recuperável da falha.

**Teste:** [test_30_janela_que_sumiu_no_meio_da_leitura_degrada_para_desconhecida](../../tests/test_auditoria_30.py#L364).

## Ordem prática de correção

1. **Controle do usuário:** 01, 02, 03 e 16; garantir que pânico e saída não dependam de disco nem deixem interação presa.
2. **Integridade e recuperação de dados:** 18–24 e 26; impedir falhas de startup, consolidação inválida e regravação de histórico apagado.
3. **Lifecycle e permissões:** 04–08, 27 e 28; controlar objetos existentes, handlers e tempo ativo.
4. **Interação e física:** 09–15 e 17; corrigir contratos observáveis dos comandos, brinquedos e geometria.
5. **Tempo e adaptadores:** 25, 29 e 30; alinhar integração temporal, contrato de leitura e recuperação de corridas Win32.

Os IDs não representam trinta variações de uma única entrada inválida: há
contratos de estado, controladores, formatos de dados e caminhos de interação
diferentes. Algumas soluções transversais podem resolver mais de um item, mas
cada caso tem gatilho, consequência e regressão próprios.

A ausência de outras falhas nesta suíte não garante ausência de bugs adicionais.
A decisão sobre a regra de aprendizado permanece fora desta contagem, pois foi
explicitamente deixada como decisão de modelo pelo relatório anterior.

## Estado das correções

Todos os 30 casos foram corrigidos e os marcadores `XFAIL` foram removidos de
`tests/test_auditoria_30.py`. A suíte passa com **125 testes** e nenhum XFAIL.

Principais mudanças:

- **Controle do usuário (01, 02, 03, 16):** o diálogo envia só o campo alterado; o
  pânico marca o desligamento antes de gravar e não falha se o disco falhar; salvar
  o condicionamento não impede a saída; o pânico cancela arraste em andamento.
- **Dados (18–24, 26):** painéis, cantinho, protesto, pet, episódios e preferências
  validam tipo e domínio; bytes inválidos viram caractere de substituição e o JSON
  com `NaN` é recusado; o histórico apagado descarta o minuto que estava em RAM.
- **Ciclo de vida (04–08, 27, 28):** cartaz nasce com a visibilidade da sessão;
  cutucada e fogos respeitam a pausa; a pausa desconta o tempo dos episódios
  pendentes; desligar travessuras ou fogos recolhe o que está na tela; rotina desligada
  não acumula emoções.
- **Interação e física (09–15, 17):** bolinha guardada não estimula a rede; o comando
  do menu força uma tentativa; peso zero de post-it desliga bilhetes; o pet não chuta
  a bolinha que está sendo segurada; o arraste da bolinha termina só com o botão que
  o começou; a bolinha que cai dentro de um objeto sai inteira; o pouso usa a
  primeira superfície cruzada; painéis fora das telas voltam para uma posição visível.
- **Tempo e adaptadores (25, 29, 30):** a rede avança pelo tempo real, em passos de
  até 100 ms, com limite de 2 s por atraso; `list_windows` não lê títulos; janela que
  some durante a leitura vira "desconhecida".

Observação: a mudança de tempo (25) faz a rede avançar só o tempo real decorrido.
Testes que chamam `think()` em rajada, sem esperar, não integram a rede; isso é
esperado e não afeta o app, que chama a cada 100 ms.
