# Análise técnica do Bryan / DeskBuddy v7

Revisão: 31/10/2026. Origem analisada: `<raiz do projeto>`.

Esta revisão considera o código novo do pacote `bryan`, não o projeto anterior
em `<projeto anterior>`. Nenhuma correção de lógica foi aplicada nesta etapa.

## Resultado geral

O produto ganhou uma interação de desktop muito mais ampla: PySide6, movimento
físico, pouso em janelas, arraste/arremesso, bolinha, notebook, pedidos de trabalho,
protesto, tristeza, cartazes, fogos e condicionamento antecipatório.

O núcleo padrão instanciado tem **430 neurônios, 14.162 sinapses, 25 canais
sensoriais e 14 populações motoras**. O número de sinapses descreve a matriz
inicial; a aprendizagem também altera conexões plásticas.

As pastas core/body/mind/world/sense/ui e a separação de Paths/SettingsStore
ajudam a localizar responsabilidades. Entretanto, os controles globais da sessão
não alcançam todos os caminhos de execução, e a validação persistente ainda
permite estado parcial ou numericamente inválido.

## Verificações executadas

- `QT_QPA_PLATFORM=offscreen`, `python -B -m pytest tests -q -p no:cacheprovider`:
  **80 testes passaram em 9,84 s** nesta máquina.
- `python -B -m pyflakes bryan tests main.py`: nenhuma ocorrência reportada.
- Sintaxe de 65 arquivos Python em main.py, bryan/ e tests/ verificada por AST.
- Reproduções adicionais em diretórios temporários e com Qt offscreen.
- Nas reproduções de BryanApp, o atalho global foi substituído por mock.

Os testes não equivalem a uma inspeção visual em desktop real, foco entre
janelas, vários monitores, DPI elevado ou executável PyInstaller.

## Problemas confirmados

### 1. Pânico e desligamento não alcançam todos os componentes — alta

Arquivos: `bryan/app.py` (think, sense, update_visibility e panic),
`bryan/ui/float_manager.py` (open).

`panic()` desativa a permissão e remove o cartaz de raiva, mas a atualização de
visibilidade não inclui `sad_ctl`. Um cartaz de tristeza já aberto permanece
visível. `think()` e `sense()` também não verificam o estado ativo: os timers
continuam executando lógica após desligamento. O monitor pode ser aberto pela
bandeja porque FloatManager.open não aplica a política de visibilidade.

Reprodução observada:

```text
Cartaz de tristeza antes do pânico: visível
Cartaz de tristeza depois do pânico: visível
Um think após pânico: cérebro avançou 100 ms e energia diminuiu
FloatManager.open('neural') com ativo=False: painel visível
```

Impacto: contradiz a regra do projeto de que o pânico desliga tudo e é respeitado.
O desligamento continua persistido corretamente; a falha está no alcance durante
a sessão corrente.

Correção indicada: uma política de sessão comum para execução, coleta e exibição;
um registro completo de janelas/controladores; aplicar a política também às
ações manuais da bandeja. Diferenciar explicitamente esconder de desligar.

### 2. Falha de carregamento deixa aprendizado parcialmente aplicado — alta

Arquivo: `bryan/core/nervous_system.py`, LIFBrain.load, a partir da linha 657.

O método altera learned e aplica a matriz antes de validar todos os canais de
eficácia. Também restaura p canal por canal. Um canal inválido posterior retorna
False, mas os valores anteriores já foram aplicados ao cérebro vivo.

Reprodução: arquivo com aprendizado 0,123, primeiro canal de eficácia 0,2 e
segundo canal com tamanho inválido. Resultado:

```text
load retornou False
learned[0,0] permaneceu 0,123
p[0] permaneceu aproximadamente 0,2
```

O construtor do app chama load sem reverter esse estado. A mensagem de que está
começando do zero, em caminhos de exceção, também não garante esse resultado.

Correção indicada: converter e validar o estado completo em estruturas temporárias,
incluindo shapes e domínio, e publicar tudo somente depois da validação integral.

### 3. NaN pode entrar na matriz neural por uma memória aceita — alta

Arquivos: `bryan/core/nervous_system.py` (load) e `bryan/store.py`.

O importador converte valores com float, mas não verifica finitude nem limita os
pesos restaurados ao domínio de aprendizagem. O JSON padrão usado pela camada de
arquivo também aceita e pode escrever valores não finitos.

Reprodução: um peso aprendido NaN e efficacy vazio foram aceitos por load; o
método retornou True e `np.isfinite(W_lif).all()` retornou False.

Impacto: a rede pode continuar com aritmética inválida e conservar o problema em
gravações posteriores, sem uma exceção imediata que identifique sua causa.

Correção indicada: rejeitar NaN, infinito e expoentes que transbordem na leitura;
escrever com allow_nan=False; validar limites, shapes, schema e compatibilidade
antes de aplicar pesos ou eficácia.

### 4. JSON válido com schema inválido derruba carga ou consolidação — alta

Arquivos: `bryan/core/homeostasis.py` (load) e `bryan/core/episodic.py`
(_read_episodes, load e consolidate).

read_json trata arquivo malformado, mas os modelos não validam consistentemente
o conteúdo de um JSON sintaticamente válido.

Reproduções:

```text
Drives.load com energy='erro': ValueError não tratado
episodes.jsonl contendo uma linha '{}': load aceita; consolidate levanta KeyError 'contexto'
```

O primeiro caso ocorre na construção de BryanApp e pode impedir a inicialização.
O segundo ocorre no fluxo de sono, depois que asleep já foi alterado.

Correção indicada: validar campos obrigatórios, tipos, finitude e limites por
modelo; tratar registros inválidos individualmente; conservar o estado anterior
até completar a operação. Incluir casos de JSON válido porém incompatível nos testes.

### 5. Pausa congela o quadro, mas não o estado interno — média

Arquivo: `bryan/app.py`, toggle_pause/frame/think.

O guard de paused existe em frame, mas não em think ou sense. Na reprodução,
após toggle_pause, uma chamada think avançou a rede em 100 ms. Energia, emoções,
protesto, condicionamento e episódios continuam seguindo seus caminhos.

Correção indicada: definir o contrato de pausa, aplicá-lo aos timers pertinentes
e reancorar os relógios na retomada. Se o recurso pretendido fosse somente
congelar movimento, o rótulo e sua documentação precisariam deixar isso explícito.

### 6. Apagar todos os dados recria a pasta de memória — média

Arquivos: `bryan/app.py`, wipe_all_data; `bryan/log.py`, log.

Depois de rmtree, wipe_all_data escreve uma mensagem de log. log cria novamente
o diretório pai. A reprodução terminou com memory/ existente e contendo
`logs/bryan.log`. O flag wiping protege save, mas não a gravação do log.

Além disso, ignore_errors=True suprime a informação de uma exclusão incompleta.

Correção indicada: suspender toda gravação antes da exclusão, inclusive logging
e timers; verificar o resultado e apresentar eventual falha em vez de afirmar
que tudo foi apagado.

### 7. Transição da permissão de rotina perde o valor anterior — média

Arquivos: `bryan/ui/ui.py`, SettingsDialog._set; `bryan/app.py`, apply_perms.

O diálogo recebe o mesmo dicionário compartilhado e o modifica antes de emitir
changed. Quando apply_perms lê was_routine, já recebe o valor novo. A condição
destinada a fechar/gravar o minuto em andamento ao desativar a rotina não ocorre
no caminho real da UI.

Reprodução do fluxo equivalente ao diálogo: alterar perms['rotina']=False e
chamar apply_perms com os novos valores deixou timeline.close com zero chamadas.

Correção indicada: a UI deve emitir a intenção de mudança sem alterar primeiro
o store; o app/store calcula a transição usando o estado antigo e aplica uma
única atualização. Evitar gravação duplicada em UI e SettingsStore.

### 8. Troca de modo não atualiza a taxa do condicionamento — média

Arquivo: `bryan/app.py`, construção de Conditioning e apply_perms.

Conditioning recebe cond_rate uma vez na inicialização. apply_perms troca prof,
mas não atualiza a taxa no objeto já criado.

Reprodução: início em modo normal com rate=0,03; ativação do modo teste manteve
rate=0,03, embora o novo perfil informe cond_rate=0,12. A troca inversa também
pode manter uma taxa acelerada no modo normal.

Correção indicada: aplicar a mudança de perfil a todos os objetos que conservam
cópias de parâmetros e testar as transições nas duas direções.

## Diferenças importantes frente ao Buddy anterior

| Tema | Projeto anterior | Código novo analisado |
|---|---|---|
| Interface | Tk, painel extenso e olhos | PySide6, criatura móvel e objetos de cena |
| Rede padrão | 266 neurônios e 6 motores | 430 neurônios e 14 motores |
| Estado afetivo | Quatro dimensões e traços persistentes evolutivos | Valência/excitação, classificação por motores, overrides e temperamento de arquivo |
| Aprendizado neural | Elegibilidade pré/pós com seleção de ação e reforço | Elegibilidade dos níveis sensoriais com sinais fixos por alvo emocional |
| Contexto/ações | Valores contextuais e erro temporal de previsão | Bandit contextual de travessuras e condicionamento Rescorla–Wagner |
| Reforço | Eventos de carinho com cooldown/saciedade; excesso de cutucadas punitivo | Carinho recompensado continuamente; dispensa produz penalidade |
| Persistência | Gerações completas com validação conjunta | Arquivos individuais substituídos atomicamente |
| Tempo | Clock injetável e TickContext | time.monotonic/time.time e integração fixa em callbacks |

Não é correto concluir que há menos qualidade porque a suíte nova tem 80 testes
e a antiga 104: os sistemas e casos são diferentes. Também não é correto tratar
a nova aprendizagem como uma preservação integral da regra anterior.

### O terceiro fator precisa ser descrito com precisão

Em LIFBrain.learn, a atualização utiliza:

```text
delta = rate × reward × dt × outer(eligibilidade_sensorial, post_sign)
```

post_sign é fixo para PLAYFUL/CALM/FRUSTRATION/GLOOM, não uma medição de atividade
pós-sináptica. Foi reproduzida alteração de quatro pesos depois de stimulate e
learn sem executar nenhum step: tempo neural zero e taxa de disparo zero.

Essa regra pode servir ao objetivo de aprender valência de estímulos. Contudo,
não implementa a mesma coatividade pré/pós e atribuição à ação que existia no
projeto anterior. Para retomar esse objetivo, é necessária uma decisão explícita
de modelo e testes que exijam atividade pós-sináptica e crédito temporal correto.

### Pontos de arquitetura a acompanhar

- BryanApp concentra composição, interação, ciclo, permissões e lifecycle em
  um arquivo de aproximadamente 750 linhas. Os bugs de pânico/pausa indicam uma
  política de sessão distribuída, mais do que uma necessidade de trocar as pastas.
- A integração de homeostase/rede usa 0,1 s fixo, enquanto deadlines e sensores
  usam tempo real. Sob atraso do event loop ou suspensão, os relógios podem divergir.
- O snapshot neural expõe arrays vivos à apresentação. A aplicação atual usa a
  mesma thread, mas a fronteira limita isolamento e futuras mudanças de concorrência.
- Gravação atômica por arquivo não representa uma transação de todos os estados.
  Falha entre saves pode deixar arquivos de momentos diferentes.
- Configurações e permissões persistidas também precisam de validação de tipos;
  o dicionário atual aceita valores salvos sem normalização de domínio.
- Documentação precisa ser reconciliada: AGENTS/CLAUDE citam 62 testes e a
  arquitetura cita 328 neurônios, enquanto esta execução encontrou 80 e 430.

## Ordem recomendada

1. Pânico/desligamento e visibilidade global, com testes de todas as janelas.
2. Restauração neural transacional e rejeição de dados não finitos.
3. Schemas de homeostase, episódios, preferências e permissões.
4. Pausa real e relógio consistente entre os callbacks.
5. Apagar dados sem regravação; atualização de permissões e perfis.
6. Decidir e documentar a regra de aprendizagem desejada.
7. Revisão visual real de foco, DPI, múltiplas telas e executável.

As reproduções comprovam os casos descritos, não a ausência de outros erros.
Esta etapa adiciona somente o relatório; a lógica do programa não foi alterada.

## Estado das correções

Corrigido, com testes que reproduzem cada caso em `tests/test_robustez_v2.py`:

1. **Pânico e desligamento:** o cartaz de tristeza some no pânico e na visibilidade. Pausa e desligado congelam pensamento e sentidos (`_congelado`). O painel não abre com o Bryan desligado (`FloatManager.open`).
2. **Carregamento tudo-ou-nada:** a rede valida tudo antes de publicar qualquer peso ou eficácia.
3. **NaN:** `write_json` recusa NaN; `read_json` rejeita NaN e infinito; a rede rejeita valores fora do domínio de aprendizagem.
4. **Schema:** homeostase, preferências e episódios validam tipos e domínio. Episódios inválidos são descartados um a um. Permissões com tipo errado são ignoradas.
5. **Pausa:** congela a rede e os sentidos; o movimento já parava.
6. **Apagar dados:** para a gravação do log antes de apagar, e não recria a pasta. Falhas são exibidas no terminal, em vez de dar o apagamento como concluído.
7. **Transição da rotina:** o diálogo trabalha com uma cópia e o app compara com o estado anterior.
8. **Taxa do condicionamento:** acompanha o perfil nos dois sentidos.

Ainda não tratado:

- **Aprendizado (terceiro fator):** o `post_sign` continua fixo por alvo. Falta a decisão de modelo que o relatório pede: atividade pós-sináptica e crédito temporal.
- **Revisão visual:** foco entre janelas, DPI, vários monitores e executável PyInstaller ainda não foram verificados.
- **Arquitetura:** `BryanApp` continua grande, e o relógio fixo de 0,1 s entre `think` e os sensores não foi alterado.
- **Atomicidade entre arquivos:** cada arquivo é gravado atomicamente, mas um estado de vários arquivos ainda pode ficar de momentos diferentes.
- **Documentação:** AGENTS/CLAUDE e a arquitetura ainda citam 62 e 328; a contagem atual é 95 testes e 430 neurônios.

## Auditoria adicional depois das correções

A revisão de 31/10/2026 reproduziu 30 casos adicionais no código corrigido.
Resultados, prioridades e testes estão em [AUDITORIA_30_BUGS.md](AUDITORIA_30_BUGS.md).
Os 95 testes existentes continuam passando; os 30 casos novos estão identificados
como falhas conhecidas (XFAIL), sem alterar o código de produção nesta etapa.
