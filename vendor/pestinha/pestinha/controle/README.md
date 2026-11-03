# `pestinha/controle/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Mixins de `PestinhaApp`: sessão (permissões, visibilidade, pausa, pânico, salvar, sair, apagar) e interação (cutucar, arrastar, menus, notebook).

**Pode importar de:** todas as anteriores (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `interacao.py` | O que você faz com o pet: cutucar, arrastar, arremessar, dispensar travessuras, os comandos do menu do botão direito e o notebook. |
| `sessao.py` | O que vale para a sessão inteira: permissões, visibilidade, pausa, pânico, esconder, salvar, sair e apagar os dados. |
