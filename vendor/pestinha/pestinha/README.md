# Pacote `pestinha`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

O código do pet, em camadas. Cada pasta tem o seu README com a lista de arquivos.

## Camadas

Cada camada só importa das que estão acima dela nesta tabela (verificado por `tests/test_arquitetura.py`):

```text
core  <  sense  <  body  <  world  <  mind  <  ui  <  controle  <  app.py
```

| Pasta | Papel |
|---|---|
| `core/` | Cérebro e regras puras: rede neural, emoção, homeostase, memória, condicionamento, física e protesto. Sem Qt e sem API do sistema, para ser testável em qualquer lugar. |
| `plataforma/` | Tudo que depende do sistema operacional: programa em primeiro plano, tempo ocioso, janelas, tela cheia, foco e o atalho de pânico. Um módulo por sistema (Windows, macOS, Linux). Só nome de programa e geometria; nunca conteúdo nem título de janela. |
| `sense/` | Sentidos: o que as leituras da plataforma significam (atividade, tela cheia, janela para pousar) e registro da rotina. Nunca conteúdo nem título de janela. |
| `body/` | O corpo do pet: a janela com o rosto, o estado que ele mostra, o comportamento (movimento) e a bolinha. |
| `world/` | Objetos que aparecem na tela: post-its, memes, cartazes, notebook, fogos e a janela arrastável base. |
| `mind/` | Controladores de decisão: ligam o que a rede decide à cena (sono, mesa, protesto, travessuras, festa, revolução, cantinho do castigo). |
| `ui/` | Janelas de interface: tela de permissões, bandeja, passo a passo, monitor neural e painel de protesto. |
| `controle/` | Mixins de `PestinhaApp`: sessão (permissões, visibilidade, pausa, pânico, salvar, sair, apagar) e interação (cutucar, arrastar, menus, notebook). |
| `app.py` | Composição: cria tudo, liga os relógios e roda os três ciclos (sentidos, pensamento e quadro). |

## Módulos compartilhados

Podem ser usados por qualquer camada.

| Arquivo | O que faz |
|---|---|
| `ajustes.py` | Todos os números que dão o jeito do pet, em um lugar só. |
| `config.py` | Caminhos, permissões da sessão, perfis de tempo e pets. |
| `paths.py` | Onde ficam as coisas. |
| `store.py` | A única forma de gravar e ler arquivos de estado. |
| `log.py` | Um lugar só para mensagens do app: terminal e arquivo em memory/logs/. |
| `mathutil.py` | Funções matemáticas pequenas, sem dependências. |
| `settings_store.py` | As permissões da sessão, em um lugar só. |

Ver [docs/ARQUITETURA.md](../docs/ARQUITETURA.md) para o fluxo completo.
