# Pestinha web — companheiro visual da ADA-M

A ADA-M inclui uma adaptação independente de pet virtual para navegador em `static/pestinha.js`.

## O que faz

- Mostra um personagem animado no canto inferior direito do chat.
- Reage à digitação, ao envio de mensagens e ao estado de geração da resposta.
- Permite carinho por clique/toque e guarda apenas uma contagem simples de afeto no armazenamento local do navegador.
- Respeita a preferência do sistema por movimento reduzido.

## Limites desta adaptação

Esta versão é um companheiro visual de navegador. Ela não executa o aplicativo desktop do Pestinha, não incorpora a rede neural pulsada de 470 neurônios e não reproduz a física de janelas, bolinha, memes, notebook ou leitura do ambiente do sistema operacional. O navegador não tem acesso a esses recursos de desktop e esta integração não tenta contornar essas limitações.

O pet não lê mensagens para criar perfil, não inspeciona outras abas/aplicativos, não acessa teclado global e não envia dados para serviços externos. A única persistência própria é a pontuação de carinho no `localStorage` do navegador.

## Referência e licenciamento

Projeto de referência: https://github.com/mille-okws/pestinha

O Pestinha original declara licença GPL-3.0-or-later para seu código. Esta integração foi escrita como implementação web independente e não copia código-fonte, imagens, memes, textos, pesos neurais ou outros assets do projeto original. A referência é creditada pela inspiração no conceito de pet virtual.
