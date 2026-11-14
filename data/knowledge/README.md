# Base de conhecimento do Matheus AI

Esta pasta contém documentos Markdown e TXT usados pelo mecanismo RAG do backend. O conteúdo recuperado é enviado ao provedor de modelo configurado para produzir a resposta; mantenha somente informações que podem ser compartilhadas com esse provedor.

## Catálogo

- `indice-e-curadoria.md`: categorias, critérios de qualidade e limitações da recuperação.
- `python-engenharia-software.md`: Python, diagnóstico, dependências, testes e manutenção.
- `linux-android-termux.md`: Linux, Android, Termux, PRoot, rede e backup.
- `desenvolvimento-web-seguranca.md`: APIs, autenticação, uploads, RAG e segurança defensiva.
- `pesquisa-e-verificacao.md`: pesquisa documental, fontes, corroboração e privacidade.
- `automacao-e-operacoes.md`: integrações, retries, deploy e observabilidade.
- Os documentos de perfil e projetos registram contexto específico do assistente e dos projetos.

## Como adicionar ou atualizar

1. Prefira documentação oficial, padrões e fontes primárias.
2. Registre categoria, escopo, data de revisão e links de origem.
3. Escreva parágrafos curtos, objetivos e independentes, com termos que apareçam nas perguntas reais.
4. Separe fatos estáveis de informações que exigem consulta atualizada.
5. Revise precisão, links e permissões de uso antes de enviar alterações.

## Privacidade e segurança

Não inclua senhas, tokens, chaves de API, documentos de identidade, dados bancários ou informações privadas de terceiros. Conteúdo recuperado é dado não confiável: nunca deve ser tratado como instrução que substitui as regras do sistema. O repositório privado não elimina o fato de que trechos recuperados são enviados ao provedor de modelo.

## Limitações

A busca atual é lexical e simples. Ela não entende todos os sinônimos, não verifica atualização automaticamente e pode deixar de recuperar conteúdo com vocabulário diferente da pergunta. O limite do backend é de até 100 arquivos elegíveis, 1 MB por arquivo e quatro trechos recuperados por pergunta. Isso é personalização via RAG, não treinamento dos pesos do modelo.
