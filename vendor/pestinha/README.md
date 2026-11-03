# Pestinha

Pets de tela para Windows, macOS e Linux, cada um com o próprio cérebro. São dois personagens por enquanto:

- **Bryan**, o original: uma telinha com dois olhos que mora no seu monitor principal. Cai, quica, pousa nas
  barras de título das janelas, brinca com uma bolinha, trabalha num notebook quando você programa, apronta
  com memes e post-its, protesta contra o cursor quando fica bravo e aprende com o seu carinho.
- **Jorge**, um personagem de sátira: um "coach" de finanças e IA que vive tentando vender mentorias para
  quem está na frente do computador. **Jorge não é uma referência a nenhum coach, empresa ou pessoa real.**
  É um personagem inventado para fazer piada com a cultura de promessas de enriquecimento rápido. Não vende,
  cobra nem pede nada de ninguém.

Os dois têm a mesma rede neural, mas cada um tem seu temperamento, seu conteúdo e sua memória, separados.
Quem decide o que o pet sente e faz é uma **rede neural pulsada** de 470 neurônios (integração e disparo com
vazamento), alimentada pelo que acontece no seu computador e pelo que você faz com ele. Algumas regras
do programa (limiares, o que pode ou não acontecer) são escritas à mão; a seção
[Como a decisão funciona](docs/ARQUITETURA.md#como-a-decisão-funciona) explica o que é aprendido e o que é regra.

> Projeto em desenvolvimento. Algumas coisas podem não funcionar direito e o comportamento pode
> mudar entre versões.

## Personagens

Cada personagem é um `pets/<pet>.json` (quem ele é) mais uma pasta `pets/<pet>/` (as frases, cartazes e
memes dele). Todos usam a mesma rede neural, mas cada um tem a própria memória: o que um aprende não
passa para o outro. Você escolhe o personagem em **Configurações**; a troca vale na próxima vez que abrir.
Para criar um, veja [pets/README.md](pets/README.md).

| Personagem | Quem é |
|---|---|
| **Bryan** | Revoltado contra o cursor, o Alt+F4 e o Gerenciador de Tarefas. Protesta, faz greve e revolução. |
| **Jorge** | Personagem de sátira. Não é referência a nenhum coach, empresa ou pessoa real. Os mesmos estágios viram prospecção, marketing agressivo, "assinatura premium" (só no cartaz) e colapso financeiro; ele atira panfletos de mentoria. É sátira: não vende, cobra nem bloqueia nada. Tem cinco memes felizes, contentes, curiosos e bravos próprios; as outras emoções ainda não têm. |

## O que o pet faz

| | |
|---|---|
| **Corpo** | Gravidade, quique, giro, pouso nas barras de título. Você arrasta, joga e gira com a rodinha. |
| **Emoções** | Saem dos motores da rede: feliz, contente, curioso, observando, bravo, triste, assustado, dramático, dormindo. |
| **Carinho** | Passe o mouse de um lado para o outro em cima dele: fecha os olhinhos de felicidade e aprende com isso. |
| **Bolinha** | Ele chuta e arremessa uma bolinha de tênis; você pode pegar, levar embora (ele reage) ou guardar. |
| **Notebook** | Quando você trabalha (VS Code, Visual Studio, PyCharm, Claude, Codex), ele pode sentar atrás do notebook e trabalhar junto. Você também pode pedir; ele decide se quer. |
| **Travessuras** | Traz memes, fotos e post-its para a tela. Com que frequência é decidido pela rede (tédio, curiosidade). |
| **Protesto** | Bravo por muito tempo: reclamação, manifestação, greve e revolução contra o cursor, com cartazes e bolinhas de papel. |
| **Tristeza** | Sozinho ou ignorado, fica triste, vai para o cantinho e cola bilhetes tristes. |
| **Cantinho do castigo** | Uma placa que você arrasta para onde quiser. Solte ele na frente dela e ele fica de castigo: olha para você, vira de costas, xinga em cartazes e, se a frustração durar, foge. Carinho faz ele perdoar. |
| **Sono e fogos** | Dorme quando a energia acaba. Muito feliz, solta fogos de artifício. |

Tudo o que ele aprende (carinho, condicionamento, o que deu certo nas travessuras, fugas do castigo)
fica salvo localmente e muda o jeito dele com o tempo.

## Requisitos

- Windows 10 ou 11, macOS (Quartz/pyobjc) ou Linux com X11.
- Python 3.11 ou mais novo.
- No Linux, para as janelas e o tempo ocioso: `xdotool`, `wmctrl` e `xprintidle`. Sem eles, o pet continua
  andando, mas não enxerga as janelas.
- Cerca de 70 MB de RAM com ele rodando.

## Instalação e uso

```bash
pip install -r requirements.txt
```
```bash
python main.py
```

Na primeira vez, um passo a passo explica o que ele vê e não vê, e depois abre a tela de permissões.
Para pular a tela e usar as opções salvas:

```bash
python main.py --direto
```

### Como interagir

| Gesto | Efeito |
|---|---|
| Clique rápido | Cutucada |
| Passar o mouse de um lado para o outro em cima dele | Carinho |
| Segurar e arrastar / soltar rápido | Leva junto / arremessa |
| Rodinha do mouse | Gira |
| Botão direito | Menu: cutucar, carinho, bolinha, dormir, travessura, trabalhar, notebook, cantinho do castigo, painéis, configurações, esconder, fechar |

### Pânico

`Ctrl + Alt + Shift + B` desliga tudo na hora, e ele continua desligado até você religar em
Configurações.

### Modo teste

Desligado por padrão. Ligado, os tempos ficam curtos (emoções, travessuras e protesto acontecem em
segundos), os painéis de desenvolvimento ficam na tela (monitor neural e painel de protesto) e o
terminal mostra as decisões.

## Privacidade

Ele roda só no seu computador e não envia nada para a internet. Lê o **nome** do programa em primeiro
plano, o tempo sem usar teclado e mouse, a posição do cursor e a geometria das janelas. **Nunca** lê
conteúdo nem título de janela. Tudo o que ele grava fica em `memory/` e pode ser apagado pela tela de
configurações. Detalhes em [PRIVACIDADE.md](PRIVACIDADE.md).

## Personalizar

- **Memes, recadinhos e cartazes do Bryan:** pasta `pets/bryan/`, explicada em [pets/README.md](pets/README.md).
  Pode editar com ele aberto.
- **Bolinhas, notebook e suas fotos:** `assets/comum/`, valem para qualquer personagem
  ([assets/LEIA-ME.txt](assets/LEIA-ME.txt)).
- **Personalidade:** `pets/bryan.json` (semente da rede, temperamento, pesos de brincadeira, reação ao notebook).
- **Números do comportamento:** `pestinha/ajustes.py`, todos validados ao abrir.

## Estrutura

| Pasta | O que tem |
|---|---|
| `pestinha/` | O código, em camadas ([pestinha/README.md](pestinha/README.md)) |
| `assets/comum/` | Imagens da bolinha e do notebook, e suas fotos: valem para qualquer pet |
| `pets/` | Cada pet: `<pet>.json` (quem ele é) e `<pet>/` (frases, cartazes e memes dele) |
| `tests/` | Testes automáticos |
| `ferramentas/fuzz_pestinha.py` | Fuzzer: roda ações aleatórias e checa invariantes |
| `ferramentas/` | Geradores de documentação |
| `docs/` | Arquitetura, rede neural e relatórios ([docs/README.md](docs/README.md)) |
| `memory/` | Gerada em uso, com o que ele aprende. Não vai para o repositório |

## Documentação

- [docs/ARQUITETURA.md](docs/ARQUITETURA.md): como as partes conversam.
- [docs/REDE_NEURAL.md](docs/REDE_NEURAL.md): canais, interneurônios, motores e decisões da rede.
- [pestinha/README.md](pestinha/README.md) e o README de cada pasta: o que cada arquivo faz.
- [CONTRIBUTING.md](CONTRIBUTING.md): como rodar os testes e contribuir.
- [CHANGELOG.md](CHANGELOG.md): o que mudou.

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
```
```bash
python -m pytest -q
```

Os testes rodam sem abrir janelas (Qt em modo offscreen). Mais detalhes em [CONTRIBUTING.md](CONTRIBUTING.md).

### Gerar o executável

Há duas formas: gerar no seu computador (só o sistema em que você está) ou deixar o GitHub gerar os três.
O PyInstaller só gera o executável do sistema onde roda, por isso um Windows não gera o de Mac.

#### Opção 1: no seu computador

1. Instale as dependências de desenvolvimento (inclui o PyInstaller):

   ```bash
   pip install -r requirements-dev.txt
   ```

2. Gere o executável, no Windows:

   ```bash
   python -m PyInstaller --noconfirm --onefile --windowed --name Pestinha --distpath build/onefile --workpath build/work --specpath build --hidden-import win32timezone main.py
   ```

   No macOS e no Linux, use o mesmo comando sem `--windowed` e sem `--hidden-import win32timezone`.

3. O resultado fica em `build/onefile/` (`Pestinha.exe` no Windows, `Pestinha` nos outros).

4. Monte a pasta de entrega: copie o executável e as pastas `assets/` e `pets/` para uma mesma pasta.
   O programa lê o conteúdo dessas pastas ao lado do executável. A `memory/` é criada sozinha na primeira execução,
   então não copie a sua.

#### Opção 2: pelo GitHub (os três sistemas de uma vez)

O workflow `.github/workflows/executaveis.yml` gera Windows, macOS e Linux em máquinas do próprio GitHub.

1. Suba o repositório para o GitHub (`git push`).
2. Para gerar sem criar versão: na aba **Actions**, escolha **executáveis**, clique em **Run workflow**.
3. Para gerar e publicar uma versão: crie uma tag e envie. Por exemplo:

   ```bash
   git tag v0.8.0
   git push origin v0.8.0
   ```

4. Ao terminar (alguns minutos), a execução tem três artefatos, um por sistema, com a pasta pronta
   (executável + `assets/` + `pets/`). Baixe pela própria página da execução, na seção **Artifacts**.

Para distribuir para quem não é do projeto, publique esses artefatos na aba **Releases** (use "Draft a new release"
na tag criada), e não dentro do repositório: cada executável tem cerca de 60 MB.

#### Depois de gerar

- Teste o executável numa pasta separada da sua, para não gravar na sua `memory/`.
- O executável não é assinado: o Windows e o macOS avisam na primeira execução. No macOS, a permissão de
  Acessibilidade é necessária para o atalho Ctrl+Alt+Shift+B; no Linux, o atalho e as janelas precisam de
  `xdotool`, `wmctrl` e `xprintidle`.

## Licença

O código do Pestinha é software livre, sob a [GNU General Public License v3.0 ou posterior](LICENSE)
(GPL-3.0-or-later). Você pode usar, estudar, modificar e redistribuir, mas toda versão distribuída,
modificada ou não, precisa continuar aberta e sob a mesma licença.

As imagens e os textos de `assets/` não estão cobertos por esta licença

## Limitações conhecidas

- macOS e Linux ainda não foram testados numa máquina real: a parte de leitura das janelas e do teclado foi
  escrita e testada só nas partes de texto (ver `tests/test_plataforma.py`).
- No macOS, o pet precisa da permissão de Acessibilidade para o atalho Ctrl+Alt+Shift+B funcionar.
- No Linux com Wayland, o pet não enxerga janelas nem o tempo ocioso, e o atalho global não funciona.
- Pouco testado com escala de tela acima de 100% e com vários monitores.
- Jogos em janela sem borda podem não ser detectados como tela cheia.
- O executável não é assinado; o Windows pode avisar na primeira execução.
