# Contribuindo com o Pestinha

Obrigado pelo interesse! Este guia explica como preparar o ambiente, como o código está organizado e o
que conferir antes de abrir um pull request.

## Ambiente

- Windows 10 ou 11, macOS ou Linux com X11. Toda a leitura do sistema fica em `pestinha/plataforma/` (um módulo por sistema).
- Python 3.11.

```bash
pip install -r requirements-dev.txt
```

## Rodando

```bash
python main.py
```

Ligue o **modo teste** em Configurações para os tempos ficarem curtos e ver o monitor neural e o painel
de protesto. O terminal mostra cada decisão (`[notebook]`, `[castigo]`, `[escolha]`...).

## Testes

```bash
python -m pytest -q
python -m pyflakes pestinha tests main.py ferramentas conftest.py
```

- Os testes não abrem janelas: o `conftest.py` da raiz liga o Qt em modo offscreen e isola cada teste.
- Tudo é gravado em pastas temporárias; a sua `memory/` nunca é tocada.
- Testes que montam o app inteiro usam relógio virtual (veja `tests/test_castigo_real.py`).
- Para procurar bugs de sequência, rode o fuzzer: `python -B ferramentas/fuzz_pestinha.py 150 80`.

O GitHub Actions roda pyflakes e pytest em Windows, macOS e Linux a cada push e pull request
(`.github/workflows/testes.yml`).

## Organização

O código fica em `pestinha/`, em camadas que só importam das que estão abaixo
(`core < sense < body < world < mind < ui < controle < app.py`). A regra é verificada por
`tests/test_arquitetura.py`. Leia [docs/ARQUITETURA.md](docs/ARQUITETURA.md) antes de mudanças grandes;
a seção "Como acrescentar um comportamento" tem o passo a passo.

## Convenções

- **Português** em código, comentários, mensagens e documentação. Os nomes internos da rede (`FOCUS`,
  `BOREDOM`...) ficam em inglês porque são sinais.
- **Números de comportamento** vão em `pestinha/ajustes.py`, com o intervalo válido em `_LIMITES`.
- **Arquivos** são lidos e gravados só por `pestinha/store.py`; caminhos só por `pestinha/paths.py`.
- **Janelas** usam `overlay_flags()` e `set_no_activate()` (nunca roubam o foco).
- **Estado salvo** precisa de validação ao carregar e de um teste com dados inválidos.
- **Comentários** explicam o porquê, não repetem o código.
- Cada módulo começa com uma docstring cuja primeira frase diz o que ele faz (ela vira a descrição no
  README da pasta).

## Regras que não mudam

- Nenhum pet move nem clica o cursor de verdade.
- Ele nunca tira o foco da janela que você está usando.
- Fechar, dispensar, pausar e o pânico (`Ctrl + Alt + Shift + B`) sempre funcionam.
- Nada de ler conteúdo ou título de janela; só nome de programa, tempo ocioso e geometria.
- Nada de culpar, pressionar ou bloquear a pessoa para ela usar mais o app.
- Nada vai para a internet.

## Antes do pull request

- [ ] `python -m pytest -q` passa.
- [ ] `python -m pyflakes pestinha tests main.py ferramentas conftest.py` não aponta nada.
- [ ] Há teste para o comportamento novo ou para o bug corrigido.
- [ ] Se criou ou mudou módulos, rodou `python ferramentas/gerar_readmes.py`.
- [ ] Se mexeu na rede ou nos limiares, rodou `python ferramentas/gerar_doc_rede.py`.
- [ ] Imagens novas em `assets/` são suas ou têm licença que permite redistribuir.
