# Cantinho do castigo — resultado de 100 cenários

Data: **31/10/2026**. Projeto analisado: `<raiz do projeto>`.

## Resultado

**100 cenários executados: 86 passaram e 14 falharam.** Foram 80 casos de
controlador/comportamento e 20 de integração com BryanApp. A execução final
reportou **1,61 s**, sem XFAIL, sem testes ignorados e sem erros de fixture.

Os 14 cenários que falharam correspondem a **10 famílias de problema**; cinco
falhas têm a mesma causa de prioridade do comportamento sobre o castigo.
Os números não são uma estimativa da confiabilidade em uso: são os resultados
desta matriz dirigida de cenários, não cem sessões reais prolongadas.

## Distribuição por assunto

| Grupo | Cenários | Passaram | Falharam |
|---|---:|---:|---:|
| Entrada e limites da área | 10 | 9 | 1 |
| Saída e liberação | 10 | 10 | 0 |
| Olhar e raiva | 10 | 9 | 1 |
| Criação e atualização de cartazes | 10 | 9 | 1 |
| Início da fuga | 10 | 9 | 1 |
| Conclusão e contagem das fugas | 10 | 7 | 3 |
| Persistência e arquivo inválido | 10 | 9 | 1 |
| Pânico, pausa, esconder e sono | 10 | 9 | 1 |
| Prioridade de protestos, motores e missão | 10 | 5 | 5 |
| Integração dos canais neurais | 10 | 10 | 0 |
| **Total** | **100** | **86** | **14** |

## O que aconteceu nos casos que falharam

### 002 — Soltar no ar e depois pousar não entra no castigo

O controlador viu a soltura enquanto o corpo ainda não estava apoiado. Quando o
corpo pousou dentro da área, a informação de soltura já tinha sido consumida.
Resultado: `dentro=False` e `state.castigo=False`.

Isso difere do caso que passou: soltar já apoiado, dentro da região, ativa o
castigo. A implementação reconhece apenas a coincidência de soltura e apoio no
mesmo quadro; não conserva uma intenção de entrada até o pouso.

### 030 — No canto direito, a raiva ainda aponta para a esquerda

Com a placa à direita e o corpo em x=850, ANGRY acima do limiar produziu
`gaze=(-1,0)`. O critério do cenário era olhar para a parede direita, `(1,0)`.

O cálculo usa a borda direita da própria zona; estando dentro dela, o teste
`body.x < x1` é praticamente sempre verdadeiro. Não escolhe a parede da tela
mais próxima. Essa expectativa foi baseada na descrição de olhar para a parede.

### 037 — Cartaz aparece antes de ganhar a posição do pet

Na primeira criação, o cartaz ficou com posição lógica `(0,0)` enquanto o Bryan
estava em `(100,600)`. O posicionamento é chamado antes da criação do novo
cartaz, portanto só ocorre no próximo quadro.

O teste constatou o estado da janela/objeto em Qt offscreen, não uma captura de
um flash visível no desktop. O acompanhamento posterior do cartaz passou.

### 050 — A direção da fuga é substituída pelo comportamento normal

A fuga começou para a direita com velocidade positiva. Ao executar o ciclo de
comportamento com um destino de passeio anterior à esquerda, o corpo passou a
`vx=-20`. O comando de fuga define um impulso/direção momentânea, mas não instala
uma missão persistente que mantenha esse objetivo.

### 056 — Fuga depois do prazo ainda ganha vitória

Aos 31 segundos, fora da margem de saída, uma tentativa com limite de 30 segundos
foi contabilizada como vitória. A verificação de posição acontece antes da
verificação de timeout.

Resultado: uma vitória gravada e `LEMBRA_FUGA=0,2`, apesar do prazo vencido.

### 058 — O usuário carregar o Bryan para fora conta como fuga autônoma

Com uma tentativa pendente e o corpo sendo segurado (`held=True`), levar o corpo
para além da margem produziu uma vitória. O teste entrou pelo caminho público
`CastigoController.act`, não apenas pela função interna de contagem.

A contagem acontece antes da checagem de posse/arraste. A memória passa a
atribuir sucesso de fuga a um deslocamento realizado pelo usuário.

### 059 — Mover a placa pode gerar vitória sem mover o pet

O corpo permaneceu em `(100,600)`. A placa foi movida para a esquerda durante uma
tentativa pendente. A borda da zona mudou; o corpo passou a satisfazer a condição
de saída e ganhou uma vitória, embora não tenha caminhado.

### 070 — Falha de disco durante a vitória escapa do controlador

Uma tentativa bem-sucedida com escrita bloqueada levantou `PermissionError`.
O contador em RAM já tinha subido para 1 e a tentativa tinha sido limpa, mas o
arquivo não foi gravado.

Esse caso não demonstra travamento completo do aplicativo. Demonstra que a
exceção escapa do callback e deixa memória em RAM sem persistência correspondente.

### 080 — O Bryan inicia fuga mesmo dormindo

Na integração com BryanApp, o estado de sono foi ativado e o motor FUGIR recebeu
uma taxa controlada de 10 Hz. Um quadro liberou o castigo e definiu `vx=160`.

O comportamento de sono zera movimento, mas a decisão do cantinho executada
depois ainda pode iniciar fuga. O controlador não recebe uma condição de sono
para impedir essa decisão.

### 083–087 — O castigo perde prioridade para cinco comportamentos

O corpo estava dentro da área, marcado como preso, em x=150, sem tentativa de
fuga. A expectativa era manter velocidade horizontal zero. Foram observados:

| Cenário | Situação simultânea | Velocidade observada |
|---:|---|---:|
| 083 | Manifestação | +150 px/s |
| 084 | Greve | −130 px/s |
| 085 | Revolução | +105 px/s |
| 086 | Motor CANTO ativo | −110 px/s |
| 087 | Missão de atravessar pendente | +260 px/s |

Em `Behavior.tick`, essas decisões são processadas antes do ramo
`state.castigo`. A missão é um estado concorrente preparado pelo cenário; esta
rodada não afirma que uma missão específica sobreviveu a um gesto real de arraste.

São cinco falhas de cenário que compartilham uma causa de prioridade, não cinco
implementações independentes de um mesmo bug.

## O que funcionou nos cenários executados

- Soltar o corpo já apoiado no centro e nas bordas horizontais da zona entrou no
  castigo; andar para dentro sem soltura não o ativou.
- Sair pelos quatro lados, pegar o pet, desativar a opção e mover a placa para
  longe liberaram o estado de castigo nos casos preparados.
- Pânico, esconder, tela cheia e desativação geral removeram o estado e a placa
  nos cenários de integração. Mostrar de novo não puniu automaticamente o pet.
- Pausa e retomada preservaram o estado do cantinho e bloquearam o passo neural
  testado. `CastigoController.pausar`, usado para liberação ao esconder, foi
  testado separadamente de `BryanApp.toggle_pause`.
- WATCH direcionou o olhar para o cursor; ANGRY teve prioridade sobre WATCH.
- Motores abaixo do limiar não iniciaram fuga; o limiar e valores superiores
  iniciaram a tentativa nos estados permitidos.
- Cartazes obedeceram aos sorteios/limiares preparados, foram substituídos e
  removidos ao desligar; no quadro posterior acompanharam o pet.
- As cargas de contagens válidas e os fallbacks de arquivo ausente/inválido
  passaram nos nove casos de carga persistente.
- Os dez cenários neurais passaram: PRESO acompanhou o estado testado e a memória
  de fuga gerou 0,0 / 0,2 / 0,8 / 1,0, saturando em 1,0. Uma fuga válida foi
  gravada e refletida no sinal de memória.

## Reproduzir

Na raiz de v7:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -B -m pytest tests/test_cantinho_cenarios.py -q --tb=short -p no:cacheprovider
```

Selecionar apenas um cenário:

```powershell
python -B -m pytest tests/test_cantinho_cenarios.py -k 080 -q --tb=short
```

O retorno não zero é esperado enquanto os 14 cenários continuarem falhando. Essa
é uma bateria diagnóstica explícita em tests/, sem mascarar falhas com
XFAIL e sem alterar o código de produção para fazer os testes passarem.

## Evidências

- [Os 100 cenários e suas verificações](../../tests/test_cantinho_cenarios.py).
- [Resultado de cada cenário, observado, esperado e estado final](evidencias/cantinho_100/resultados.json).
- [JUnit com resultados e propriedades dos casos](evidencias/cantinho_100/execucao.xml).
- [Saída completa da execução final](evidencias/cantinho_100/execucao.txt).

As fontes de produção são identificadas por SHA-256 no JSON. Os sorteios são
controlados nos cenários probabilísticos; o restante recebe sementes definidas.
Leituras de Windows e atalho global são substituídos nos casos de integração.
Toda gravação de memória é feita em diretórios temporários.

Esta rodada não testa aprendizagem longitudinal, foco real entre aplicativos,
atalho global registrado no Windows ou renderização perceptível em monitores
reais. Não foi aplicada correção à lógica do cantinho; o objetivo foi executar
os cenários e registrar o que ocorreu.

## Estado das correções

Os 14 cenários que falhavam foram corrigidos. A bateria passa com **100 de 100**.

| Problema | Correção |
|---|---|
| 002 entrada no ar | Soltar no ar deixa uma entrada pendente por 3 s; se ele pousar no canto nesse tempo, fica preso. |
| 030 olhar de raiva | De costas para a parede da tela mais próxima, não para a borda da zona. |
| 037 cartaz em (0, 0) | O cartaz é posicionado em cima dele antes de aparecer. |
| 050 direção da fuga | A fuga vira um destino persistente no comportamento (`fuga_alvo`), com prioridade sobre os outros ramos; o primeiro passo é imediato. |
| 056 prazo | O prazo é verificado antes da posição. |
| 058 carregado pelo usuário | Ser segurado cancela a fuga sem vitória. |
| 059 placa movida | A zona é registrada quando a fuga começa; mover a placa depois não conta. |
| 055 lado da saída | Só conta sair para o lado de dentro da tela. |
| 070 falha de disco | A gravação das vitórias trata erro de disco e é repetida quando o app salva. |
| 080 fuga dormindo | Dormindo, ele não cola cartaz nem foge. |
| 083–087 prioridade | Castigo e fuga vêm antes de mesa, canto, missões e protesto; missões pendentes são canceladas no castigo. |

A bateria chamava métodos internos com a assinatura antiga (`_checar_fuga` com a borda
da zona e `_iniciar_fuga` com um destino). As quatro chamadas foram adaptadas à assinatura
nova, sem mudar o que cada cenário verifica.

Encontrados e corrigidos na busca seguinte, com testes em `tests/test_castigo_integracao.py`:

- Preso no canto, o neurônio `SENTAR` levava o Bryan para o notebook.
- Preso no canto, as travessuras criavam missões que o castigo cancelava, deixando objetos soltos.
- Pânico ou esconder durante uma fuga não cancelava a fuga; ao voltar, ele continuava andando.

## Correção: ele não ficava de castigo (01/11/2026)

No uso real, ao entrar no canto o canal `PRESO` gerava um pico de frustração, `FUGIR`
passava do limiar antigo (1,2 Hz) em meio segundo e ele fugia logo. A fuga passou a
depender da **vontade acumulada**: o disparo de `FUGIR` acima de 2 Hz enche uma carga
(120 Hz·s para encher) que vaza abaixo disso. Pico curto não solta; frustração
sustentada, tédio ou memória de fuga, sim.

Cenários atualizados para o contrato novo (sem afrouxar o que verificam):

- 043, 044, 049, 050: partem de vontade quase cheia; um tick acima do limiar completa a
  fuga, e exatamente no limiar não acumula (043 agora espera não fugir).
- 035: `GANHO_CARTAZ` passou de 0,05 para 0,5 (cartazes eram raros demais); o disparo
  do cenário caiu dez vezes para manter a mesma probabilidade.

Testes de ponta a ponta com relógio virtual em `tests/test_castigo_real.py`.
