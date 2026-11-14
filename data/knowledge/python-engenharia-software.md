# Python e engenharia de software

**Categoria:** programação, Python, testes e manutenção  
**Revisão:** 2026-10  
**Escopo:** fundamentos estáveis; consulte a documentação da versão instalada para detalhes recentes.

## Diagnóstico de problemas
Ao investigar um erro, reúna a mensagem completa, traceback, versão do Python, sistema operacional, comando executado e menor trecho de código que reproduz o problema. Localize a primeira linha do traceback pertencente ao projeto. Não presuma que a última linha, isoladamente, explica toda a causa.

## Ambientes e dependências
Use ambientes virtuais por projeto para isolar dependências. Registre dependências diretas e versões compatíveis; evite instalar pacotes globalmente sem necessidade. Antes de atualizar bibliotecas, consulte notas de versão e execute os testes. Arquivos de lock ajudam a reproduzir instalações quando a ferramenta utilizada oferece esse recurso.

## Exceções e validação
Capture exceções específicas quando for possível tratar a falha. Não use blocos genéricos que escondam erros silenciosamente. Valide dados externos na fronteira do sistema: tipo, tamanho, formato e intervalo. Mensagens para o usuário devem ser claras, mas não revelar stack traces, caminhos internos, tokens ou detalhes de infraestrutura.

## Testes
Use testes unitários para funções isoladas, testes de integração para componentes conectados e testes de ponta a ponta para fluxos essenciais. Cubra o caminho normal, entradas inválidas, limites, falhas de dependências e regressões. Um teste deve verificar comportamento observável, não apenas repetir a implementação. Não declare que algo foi testado sem executar a suíte correspondente.

## Manutenção segura
Prefira mudanças pequenas e revisáveis. Preserve interfaces e funcionalidades existentes, crie backup antes de migrações destrutivas e inclua instruções de validação e reversão. Não misture refatoração ampla com correção urgente sem necessidade.

## Concorrência e operações assíncronas
Em aplicações assíncronas, não bloqueie o event loop com operações demoradas síncronas. Defina timeouts, limite concorrência e trate cancelamento e indisponibilidade. Reutilize clientes HTTP quando apropriado e feche recursos corretamente.

## Fontes primárias
- Tutorial oficial do Python: https://docs.python.org/3/tutorial/
- Biblioteca padrão: https://docs.python.org/3/library/
- Guia oficial de packaging: https://packaging.python.org/
- Documentação pytest: https://docs.pytest.org/
- PEPs (propostas e padrões da linguagem): https://peps.python.org/
