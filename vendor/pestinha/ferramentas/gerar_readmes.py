"""
Gera pestinha/README.md e o README de cada camada a partir das docstrings dos módulos.

    python ferramentas/gerar_readmes.py

A primeira linha da docstring de cada arquivo vira a descrição na tabela. Rode de novo ao criar,
renomear ou mudar o propósito de um módulo.
"""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "pestinha"

CAMADAS = [
    ("core", "Cérebro e regras puras: rede neural, emoção, homeostase, memória, condicionamento, física e protesto. "
             "Sem Qt e sem API do sistema, para ser testável em qualquer lugar.", "módulos compartilhados"),
    ("plataforma", "Tudo que depende do sistema operacional: programa em primeiro plano, tempo ocioso, janelas, "
                   "tela cheia, foco e o atalho de pânico. Um módulo por sistema (Windows, macOS, Linux). "
                   "Só nome de programa e geometria; nunca conteúdo nem título de janela.", "nada (só o sistema)"),
    ("sense", "Sentidos: o que as leituras da plataforma significam (atividade, tela cheia, janela para pousar) "
              "e registro da rotina. Nunca conteúdo nem título de janela.", "core, plataforma"),
    ("body", "O corpo do pet: a janela com o rosto, o estado que ele mostra, o comportamento (movimento) e a "
             "bolinha.", "core, sense"),
    ("world", "Objetos que aparecem na tela: post-its, memes, cartazes, notebook, fogos e a janela arrastável "
              "base.", "core, sense, body"),
    ("mind", "Controladores de decisão: ligam o que a rede decide à cena (sono, mesa, protesto, travessuras, "
             "festa, revolução, cantinho do castigo).", "core, sense, body, world"),
    ("ui", "Janelas de interface: tela de permissões, bandeja, passo a passo, monitor neural e painel de "
           "protesto.", "core, sense, body, world, mind"),
    ("controle", "Mixins de `PestinhaApp`: sessão (permissões, visibilidade, pausa, pânico, salvar, sair, apagar) e "
                 "interação (cutucar, arrastar, menus, notebook).", "todas as anteriores"),
]
COMPARTILHADOS = ["ajustes.py", "config.py", "paths.py", "store.py", "log.py", "mathutil.py", "settings_store.py"]


def descricao(arquivo):
    doc = ast.get_docstring(ast.parse(arquivo.read_text(encoding="utf-8"))) or ""
    primeiro = doc.strip().split(chr(10) * 2)[0] if doc.strip() else ""   # até a primeira linha em branco
    paragrafo = " ".join(primeiro.split())
    if " - " in paragrafo and paragrafo.split(" - ")[0].isupper():
        paragrafo = paragrafo.split(" - ", 1)[1]
    fim = paragrafo.find(". ")                     # só a primeira frase
    linha = paragrafo[: fim + 1] if fim > 0 else paragrafo
    return linha[0].upper() + linha[1:] if linha else ""


def tabela(arquivos):
    linhas = ["| Arquivo | O que faz |", "|---|---|"]
    linhas += [f"| `{a.name}` | {descricao(a)} |" for a in arquivos]
    return "\n".join(linhas)


def main():
    aviso = "> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.\n"
    for nome, papel, depende in CAMADAS:
        pasta = PACOTE / nome
        arquivos = sorted(p for p in pasta.glob("*.py") if p.name != "__init__.py")
        texto = (f"# `pestinha/{nome}/`\n\n{aviso}\n{papel}\n\n**Pode importar de:** {depende} "
                 f"(e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.\n\n"
                 f"{tabela(arquivos)}\n")
        (pasta / "README.md").write_text(texto, encoding="utf-8")

    mapa = "\n".join(f"| `{nome}/` | {papel} |" for nome, papel, _ in CAMADAS)
    raiz = f"""# Pacote `pestinha`

{aviso}
O código do pet, em camadas. Cada pasta tem o seu README com a lista de arquivos.

## Camadas

Cada camada só importa das que estão acima dela nesta tabela (verificado por `tests/test_arquitetura.py`):

```text
core  <  sense  <  body  <  world  <  mind  <  ui  <  controle  <  app.py
```

| Pasta | Papel |
|---|---|
{mapa}
| `app.py` | Composição: cria tudo, liga os relógios e roda os três ciclos (sentidos, pensamento e quadro). |

## Módulos compartilhados

Podem ser usados por qualquer camada.

{tabela([PACOTE / a for a in COMPARTILHADOS])}

Ver [docs/ARQUITETURA.md](../docs/ARQUITETURA.md) para o fluxo completo.
"""
    (PACOTE / "README.md").write_text(raiz, encoding="utf-8")

    for pasta, titulo, abertura in OUTRAS:
        arquivos = sorted(p for p in (RAIZ / pasta).glob("*.py") if p.name != "__init__.py")
        (RAIZ / pasta / "README.md").write_text(f"# `{pasta}/` — {titulo}\n\n{aviso}\n{abertura}\n\n{tabela(arquivos)}\n",
                                                encoding="utf-8")
    print("READMEs gerados:", ", ".join(n for n, _p, _d in CAMADAS), "pestinha/,", ", ".join(p for p, _t, _a in OUTRAS))


OUTRAS = [
    ("tests", "testes automáticos", """Rodam sem abrir janelas (o `conftest.py` da raiz liga o Qt em modo offscreen) e sempre numa pasta
temporária: nada aqui toca na `memory/` de verdade.

```bash
python -m pytest -q
```

O `python -m pytest` na raiz roda `tests/` (ver `pyproject.toml`). Testes que montam o
app inteiro usam um relógio virtual: avançam o tempo sem esperar."""),
    ("ferramentas", "geradores de documentação", """Rode depois de mudar módulos ou a rede, para a documentação não desatualizar:

```bash
python ferramentas/gerar_readmes.py
python ferramentas/gerar_doc_rede.py
```

- `fuzz_pestinha.py` roda o app com ações aleatórias e checa invariantes:
  `python -B ferramentas/fuzz_pestinha.py 150 80` (rodadas, ações por rodada).
- `medir_cartazes.py` confere se cada frase cabe na placa (rode no Windows, com as fontes reais)."""),
]


if __name__ == "__main__":
    main()
