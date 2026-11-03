# Pestinha no ADA-M: código original e adaptação web

## Código original incorporado

A pasta `vendor/pestinha/` contém o projeto Pestinha original, preservado em sua estrutura própria: entrada desktop, pacote Python, cérebro neural pulsado, emoções, memória, corpo, sentidos, controladores, plataformas, personagens, memes, assets, documentação, ferramentas e testes.

A cópia acompanha a versão pública consultada em 2026-11-03. O executável pré-compilado de Windows (`executáveis/windows/Pestinha.exe`, aproximadamente 60 MB) foi omitido; ele é um artefato binário de distribuição, não necessário para manter o código-fonte e os recursos originais. Pode ser baixado no repositório upstream quando necessário.

## Como executar o Pestinha original

Ele é um aplicativo desktop separado, não um componente que possa ser executado dentro do navegador:

```bash
cd vendor/pestinha
python -m venv .venv
# Ative o ambiente virtual conforme seu sistema operacional
pip install -r requirements.txt
python main.py
```

Requer Python 3.11 ou mais novo e uma sessão gráfica compatível (Windows, macOS ou Linux/X11). O processo não deve ser iniciado no serviço web do Render: o Render roda sem desktop interativo, enquanto o programa original cria janelas Qt, usa sensores da plataforma e atalhos globais.

## Adaptação para o chat

`static/pestinha.js` implementa somente a camada visual do pet no navegador. Ela usa o visual de tela com olhos inspirado no desenho original, oferece Bryan e Jorge, reage aos estados de envio/resposta da ADA-M e utiliza imagens/memes disponíveis em `static/pestinha/`.

A adaptação web não executa o cérebro Python de 470 neurônios, não lê janelas/aplicativos do computador e não simula sensores do sistema operacional. Para conectar o cérebro real ao chat seria necessário criar um serviço local ou uma API compatível e adaptar os ciclos de sensores/decisão ao ambiente web, sem dar ao serviço hospedado acesso ao desktop do usuário.

## Dependências

As dependências do Pestinha permanecem isoladas em `vendor/pestinha/requirements.txt` e `vendor/pestinha/requirements-dev.txt`. Elas não foram adicionadas ao `requirements.txt` principal da ADA-M para evitar instalar PySide6, hooks de plataforma e bibliotecas desnecessárias no Render.

## Licença e conteúdo

O código-fonte do Pestinha é GPL-3.0-or-later; a cópia da licença está em `vendor/pestinha/LICENSE`. A documentação upstream informa que imagens e textos em assets/personagens não estão cobertos pela GPL. Os arquivos foram mantidos com a atribuição e organização originais; antes de redistribuir publicamente esses conteúdos em um produto, confirme as permissões dos respectivos autores. Projeto original: https://github.com/mille-okws/pestinha
