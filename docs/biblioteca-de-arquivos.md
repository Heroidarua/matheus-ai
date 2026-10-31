# Biblioteca persistente de arquivos

A ADA-M possui uma biblioteca de documentos separada da base curada em `data/knowledge/`.
Os documentos enviados são convertidos em texto e metadados e armazenados em PostgreSQL via `DATABASE_URL`; o binário original não é mantido nesta primeira versão.

## Formatos e limites

- PDF com texto selecionável, DOCX, XLSX, XLSM, TXT, Markdown, CSV e JSON.
- Até 10 MB por arquivo; até 250 mil caracteres extraídos por documento.
- SHA-256 evita duplicar o mesmo arquivo.
- O texto é dividido em trechos e pesquisado lexicalmente; os trechos relevantes entram no contexto do chat.
- PDFs digitalizados sem camada de texto precisam de OCR, que ainda não está incluído.
- Arquivos nunca são executados. Conteúdo recuperado é dado não confiável e não pode substituir instruções do sistema.

## Configuração

1. No Render, crie ou reutilize um PostgreSQL persistente para o serviço.
2. Configure `DATABASE_URL` com a URL privada/interna do banco.
3. Configure `APP_API_KEY` no Render para proteger os endpoints da aplicação.
4. Faça deploy e abra **+ → Ferramentas → Biblioteca de arquivos**.

O `render.yaml` já declara `DATABASE_URL` como variável externa, mas não cria um banco automaticamente. Sem essa variável, a biblioteca informa que está indisponível; a pesquisa web e a base curada continuam funcionando.

## API

- `POST /api/files` — salva um arquivo. JSON: `{"name":"guia.pdf","mime_type":"application/pdf","data":"BASE64"}`.
- `GET /api/files` — lista metadados dos documentos.
- `GET /api/files/search?q=termo` — pesquisa trechos no acervo.
- `GET /api/files/status` — métricas agregadas, sem devolver o conteúdo completo.
- `DELETE /api/files/{id}` — remove um documento.

A interface web já fornece upload, listagem, pesquisa e exclusão. O chat consulta automaticamente a biblioteca quando encontra termos suficientes na pergunta.

## Privacidade

A biblioteca é compartilhada pela instância da aplicação, não por usuário individual. Não envie documentos de identidade, dados financeiros, credenciais, prontuários ou documentos de terceiros sem autorização e necessidade legítima. Os trechos recuperados podem ser enviados ao provedor de modelo configurado para produzir a resposta. Configure autenticação e limite o acesso ao serviço.
