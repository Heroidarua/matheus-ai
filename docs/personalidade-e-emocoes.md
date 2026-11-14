# Personalidade e estado afetivo — Matheus AI / ADA-M

## Objetivo

Adicionar uma identidade conversacional consistente e um estado afetivo simulado sem trocar o modelo de linguagem, alterar o fluxo de pesquisa ou treinar pesos.

## Primeira versão

- Identidade estável: curiosa, gentil, observadora, bem-humorada quando adequado, honesta e independente no raciocínio.
- Sinais afetivos: alegria, serenidade, curiosidade, empatia, confiança, frustração e surpresa.
- Atualização heurística baseada no tom da mensagem mais recente.
- Decaimento gradual em direção a um estado-base para evitar que uma emoção fique presa.
- Estado isolado por sessão do navegador usando o cookie assinado já existente.
- Persistência opcional em PostgreSQL por meio de `DATABASE_URL`.
- Nenhum texto bruto da conversa é gravado pela camada emocional.
- Sem `DATABASE_URL`, o fallback é memória do processo e se perde quando o serviço reinicia.

## Endpoint

`GET /api/companion/state`

Retorna identidade, valores afetivos da sessão e indicação do armazenamento. Respeita `APP_API_KEY`, se configurada. Não retorna mensagens do usuário.

## Armazenamento

A tabela `ada_m_companion_state` é criada automaticamente no PostgreSQL existente. Ela guarda apenas o identificador aleatório da sessão, os valores numéricos do estado e a data de atualização. Não é necessário criar outro banco.

## Limitações

Esta camada não é uma rede neural emocional, não altera os pesos do LLM e não representa consciência ou sentimentos subjetivos. A classificação é heurística e pode interpretar incorretamente ironia, contexto ou emoções implícitas. O modelo deve priorizar o significado da mensagem, não declarar emoções literais e nunca usar afeto para pressionar o usuário.

## Próximas etapas

1. Validar testes e persistência no ambiente de homologação.
2. Adicionar feedback explícito do usuário (útil/não útil) antes de qualquer adaptação mais ampla.
3. Integrar uma voz feminina estável. O frontend atual usa SpeechSynthesis do navegador; a voz varia conforme dispositivo e sistema.
4. Avaliar Kokoro `pf_dora` em serviço separado antes de qualquer alteração no serviço de voz existente. A branch experimental atual do TTS usa `pm_alex`; a branch principal preserva Piper.
5. Somente depois dos testes, considerar recursos de aprendizagem contínua controlada.
