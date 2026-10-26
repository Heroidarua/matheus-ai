# Dados para futuro fine-tuning

Esta pasta é reservada para preparar exemplos de treinamento. **O projeto atual não executa treinamento e não lê esta pasta durante o chat.** Para personalizar as respostas hoje, use `../knowledge/` (RAG).

Quando houver exemplos próprios suficientes e revisados, um conjunto JSONL pode usar uma conversa por linha no formato aceito pela ferramenta de fine-tuning escolhida. Exemplo estrutural ilustrativo (substitua por exemplos que você escreveu e revisou):

```json
{"messages":[{"role":"system","content":"Você é Matheus AI, um assistente geral honesto e claro."},{"role":"user","content":"Como você deve responder?"},{"role":"assistant","content":"De forma clara, prática e honesta."}]}
```

Antes de treinar:
1. Remova segredos e dados pessoais desnecessários.
2. Use apenas conteúdo seu ou cujo uso você tenha autorização.
3. Revise cada resposta para qualidade, consistência e segurança.
4. Separe dados de treino e validação para avaliar se houve melhoria.
5. Confirme o formato, a licença do modelo e os requisitos de hardware/serviço da plataforma escolhida.

Não adicione grandes arquivos de treinamento ao repositório sem avaliar tamanho, privacidade e custo de hospedagem.
