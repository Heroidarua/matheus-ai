# Google Workspace: ações de produtividade

A ADA-M pode consultar Gmail, Drive e Calendar e, após autorização de escrita, criar/alterar/cancelar eventos e enviar e-mails.

## Configuração no Render

Configure:
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `DATABASE_URL` (PostgreSQL)
- `GOOGLE_TOKEN_ENCRYPTION_KEY` (chave Fernet)
- `PUBLIC_APP_URL` (URL HTTPS pública da ADA-M)
- `GITHUB_SESSION_SECRET` (estável entre deploys)

No Google Cloud Console, habilite Google Calendar API e Gmail API. Cadastre o redirect URI:
`https://SEU-DOMINIO/api/google/callback`

A autorização solicita os escopos de leitura existentes e também:
- `https://www.googleapis.com/auth/calendar.events`
- `https://www.googleapis.com/auth/gmail.send`

Depois de atualizar os escopos, a conta precisa ser desconectada e conectada novamente em `/api/google/connect`. Em apps OAuth em modo de teste, a conta precisa estar na lista de usuários de teste.

## Endpoints

- `GET /api/google/status`: status da conexão.
- `GET /api/google/calendar/events`: próximos eventos.
- `POST /api/google/calendar/events`: criar evento.
- `PATCH /api/google/calendar/events/{event_id}`: alterar evento.
- `DELETE /api/google/calendar/events/{event_id}?confirm=true`: cancelar evento.
- `GET /api/google/gmail/messages?q=...`: pesquisar mensagens.
- `POST /api/google/gmail/send`: enviar e-mail.

As operações de escrita exigem `confirm: true` no corpo (ou parâmetro na exclusão). Sem confirmação, a API retorna HTTP 428. A camada de interface/assistente deve apresentar os dados ao usuário e só enviar a confirmação depois do aceite explícito.

### Criar evento

```json
{
  "summary": "Reunião de projeto",
  "start": "2026-11-03T14:00:00-04:00",
  "end": "2026-11-03T15:00:00-04:00",
  "time_zone": "America/Manaus",
  "description": "Revisar o planejamento",
  "location": "",
  "attendees": [],
  "confirm": true
}
```

Datas precisam incluir fuso ou deslocamento UTC. O padrão sugerido para Manaus é `America/Manaus`.

### Enviar e-mail

```json
{
  "to": ["destinatario@exemplo.com"],
  "cc": [],
  "subject": "Confirmação da reunião",
  "body": "Olá! Confirmo nossa reunião.",
  "confirm": true
}
```

## Segurança e limites

- Tokens OAuth ficam criptografados no PostgreSQL; não coloque tokens no prompt nem no navegador.
- Não registre tokens, corpos de e-mail ou dados privados em logs.
- A confirmação é obrigatória para cada mutação. A aplicação deve mostrar destinatários, assunto e corpo antes do envio; para eventos, mostrar título, data, hora e fuso.
- A API executa ações apenas na conta Google conectada à sessão atual.
- O módulo disponibiliza endpoints de execução; a orquestração conversacional (ADA-M interpretar um pedido em linguagem natural, montar uma prévia e invocar o endpoint após aprovação) deve chamar esses endpoints no fluxo de ferramentas do chat. Não alegue conclusão até a API retornar sucesso.
