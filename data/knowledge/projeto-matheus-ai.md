# Projeto Matheus AI

## Objetivo
Construir um assistente pessoal de IA configurável e útil, com personalidade própria, base de conhecimento personalizada e capacidade de evoluir para um modelo ajustado com dados selecionados pelo proprietário.

## Repositório e implantação
- Repositório GitHub: https://github.com/Heroidarua/matheus-ai
- Branch principal: main
- Aplicação web hospedada/planejada no Render.
- Backend: Python e FastAPI.
- Interface: HTML estático em static/index.html.
- O backend conversa com um endpoint compatível com a API de chat da OpenAI.
- Configurações relevantes: MODEL_BASE_URL, MODEL_NAME e OPENAI_API_KEY.
- KNOWLEDGE_DIR indica a pasta da base de conhecimento.
- APP_API_KEY pode proteger endpoints por cabeçalho, quando configurada.
- A edição de imagens é uma integração separada e pode depender de token e créditos de um provedor externo.

## Personalização atual
O projeto tem uma base RAG que busca trechos de arquivos Markdown e TXT e os inclui no contexto de cada pergunta. Isso adiciona conhecimento contextual, mas não modifica os pesos do modelo. A recuperação atual é lexical e leve; não é uma busca semântica baseada em embeddings.

## Próximas etapas sugeridas
1. Adicionar documentos próprios, revisados e não sensíveis à pasta data/knowledge/.
2. Testar a recuperação com perguntas que correspondam aos documentos e perguntas que não correspondam.
3. Confirmar o build e o deploy do Render antes de anunciar que uma alteração está funcionando.
4. Escolher um modelo aberto considerando idioma português, qualidade, licença, memória, velocidade e custo.
5. Preparar exemplos de treinamento de qualidade para avaliar um possível fine-tuning.
6. Separar e proteger segredos por variáveis de ambiente.
7. Antes de disponibilizar publicamente, configurar autenticação adequada, limites de uso, monitoramento e política de privacidade.

## Limitações conhecidas
- A aplicação depende de um endpoint de inferência válido e acessível.
- Um erro HTTP 402 do provedor indica falta de créditos/cota e não é corrigido apenas por mudanças no código da aplicação.
- A hospedagem web não implica que os pesos de um modelo grande estejam sendo executados dentro do Render.
- Não declare testes, deploys ou resultados sem evidência observável.
