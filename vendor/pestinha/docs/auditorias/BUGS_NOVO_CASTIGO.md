# Revisão das dez mudanças do cantinho

Revisão em 31/10/2026. Cinco falhas reproduzidas por testes dirigidos em
`tests/test_castigo_bugs_rede.py`. As asserções descrevem o resultado
esperado, portanto os cinco testes falham enquanto os defeitos permanecerem.
Nenhum código de produção foi alterado. Qt offscreen, memória temporária.

## 1. Castigo pode punir o episódio errado — P1

`EpisodicMemory.punir` guarda o início da última ação, mas procura o primeiro
episódio aberto com o mesmo contexto e nome. Havendo dois memes no mesmo
contexto, resolve o mais antigo, deixando o mais recente aberto para receber
um resultado positivo depois. Reprodução: abrir dois episódios iguais e punir
um segundo após o segundo; o primeiro é removido.

Correção proposta: guardar a identidade do episódio e resolver exatamente ele.

## 2. Sono apaga a punição de ações já resolvidas — P1

Quando a última ação já foi resolvida, `punir` chama somente `_learn`, sem
registrar a punição no histórico. `consolidate` reconstrói tudo a partir desse
histórico e restaura o resultado anterior. Reprodução: resolver uma ação com
valência +0,5, puni-la dentro de 20 s, consolidar. A média passa a -0,15 após
a punição e volta a +0,5 no sono.

Correção proposta: persistir a revisão do resultado, com uma identidade estável
para evitar contar a mesma experiência duas vezes.

## 3. Pausa consome a janela de aprendizado — P2

`deslocar` ajusta o início dos episódios abertos, mas não ajusta `ultima_acao`.
É essa segunda referência que `punir` usa para decidir se passaram 20 s.
Uma pausa de 100 s faz um castigo aplicado após apenas 1 s de atividade ser
ignorado. `BryanApp.toggle_pause` chama exatamente esse método na retomada.

Correção proposta: deslocar também a referência temporal da última ação.

## 4. Liberar não encerra a recompensa negativa — P2

`_soltar` limpa o estado e o cartaz, mas mantém `punicao_ate`. Tirar o Bryan
do canto ou desativá-lo imediatamente após prendê-lo mantém a penalidade na
rede até vencer o segundo original, inclusive sobre experiências após a saída.
Reprodução: entrar em t=10, liberar, consultar `punicao(10.5)`; retorna -1.

Correção proposta: encerrar o pulso ao liberar ou definir explicitamente um
evento de punição independente da permanência. O comportamento atual não faz
essa distinção e soma o pulso a recompensas posteriores em `BryanApp.think`.

## 5. Recaptura não cancela uma fuga ainda pendente — P2

Uma tentativa pode continuar em andamento antes de cruzar a margem de vitória.
Se o usuário pegar e soltar o pet entre duas chamadas de `act`, o controlador
não observa `held=True`. Ao entrar novamente, `_entrar` mantém tanto `fuga`
quanto `behavior.fuga_alvo`. Isso deixa uma tentativa anterior associada ao
novo castigo. A recaptura com receio só cobre fugas já vitoriosas.
Reprodução: iniciar tentativa, registrar zona e alvo, chamar `_entrar`; os
dois continuam ativos. O método de entrada é usado para isolar a transição;
não foi simulado um arraste real do Windows.

Correção proposta: cancelar a tentativa na entrada e avaliar separadamente se
essa tentativa interrompida deve aumentar receio.

## Observação de arquitetura a validar

`Conditioning.strength` agrega PRESS, APPROACH e PLACA no mesmo ANTICIPATE.
A nova conexão ANTICIPATE → FUGIR também transmite as associações antigas de
cutucada e arremesso ao motor de fuga. Portanto, separar os desfechos em
`outcome(cues=...)` não isola os efeitos motores. Isso não foi contado entre
os cinco defeitos reproduzidos; requer decidir se a generalização é desejada
e comparar taxas em simulações com diferentes pistas.

## Execução

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -B -m pytest tests/test_castigo_bugs_rede.py tests/test_cantinho_rede.py -q --tb=short -p no:cacheprovider
```

A bateria dirigida tem cinco casos; os 19 testes existentes das dez funções
também foram executados. O resultado final está registrado na resposta desta
revisão. Os testes não verificam aparência em tela real nem uso prolongado.

## Estado das correções

Os cinco defeitos foram corrigidos; os testes de `tests/test_castigo_bugs_rede.py` passam.

1. `punir` guarda o próprio episódio (com `id`) e resolve exatamente ele.
2. Punir uma travessura já resolvida revisa o registro dela (na tabela e no arquivo), em vez de só mexer na memória temporária. O sono reconstrói o mesmo valor, sem contar a experiência duas vezes.
3. `deslocar` também desloca o início da última travessura, mesmo resolvida: a pausa não consome a janela.
4. Soltar o Bryan encerra a recompensa negativa.
5. Recaptura cancela a tentativa de fuga pendente e o destino; a tentativa interrompida conta como fuga que deu errado (aumenta o receio).

A observação de arquitetura também foi tratada: a pista da placa ganhou um canal próprio, `ANTECIPA_PLACA`, ligado a `FUGIR` e `ALERT`. O `ANTICIPATE` recebe só PRESS e APPROACH e não tem mais ligação com `FUGIR`. Um teste de simulação confirma que só a antecipação da placa aumenta a fuga.
