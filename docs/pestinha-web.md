# Pestinha na ADA-M

O repositório original foi incorporado em vendor/pestinha/, preservando sua estrutura, documentação, testes, personagens, dados de personalidade, licença GPL-3.0-or-later e recursos visuais. Os assets usados pela adaptação do navegador também estão disponíveis em static/pestinha/.

## Companheiro web

A interface em static/pestinha.js oferece Bryan e Jorge, alternância entre personagens, animações de humor, carinho, mensagens contextuais e imagens selecionadas dos memes originais. A escolha do personagem e a pontuação simples de carinho ficam no armazenamento local do navegador.

## Limites da adaptação

O aplicativo original é desktop e usa PySide6, APIs do sistema operacional e observação local de janelas/atividade. O navegador não oferece essas permissões. Portanto, a adaptação web não executa o processo desktop nem afirma executar a rede neural pulsada original de 470 neurônios. O código original permanece preservado em vendor/pestinha/ para execução desktop, estudo e evolução separada.

A ADA-M continua usando seu backend e seu modelo de conversa Gemma 4; o companheiro é uma camada visual isolada. Não há envio das mensagens do chat para o Pestinha nem leitura do conteúdo da conversa pelo pet.

## Privacidade

- Não monitora janelas, processos, teclado global ou outras abas.
- Não envia dados a serviços externos.
- Guarda apenas personagem selecionado e contagem de carinho no localStorage.
- O estado é local ao navegador e pode ser apagado limpando os dados do site.

## Licença e créditos

O código-fonte do Pestinha está sob GPL-3.0-or-later; consulte `vendor/pestinha/LICENSE`. O README upstream esclarece que imagens e textos de assets/personagens não estão cobertos por essa licença e têm condições próprias. Verifique essas permissões antes de redistribuir os conteúdos fora deste contexto.

Projeto original: https://github.com/mille-okws/pestinha
