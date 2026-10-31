# Automação, integrações e operações confiáveis

**Categoria:** automação, APIs externas, deploy e observabilidade  
**Revisão:** 2026-10

## Planejar automações
Defina objetivo, entradas, saídas, permissões, limites e condição de sucesso antes de executar. Prefira automações pequenas, idempotentes e reversíveis. Ações que enviam mensagens, publicam conteúdo, movimentam dinheiro, excluem dados ou alteram contas exigem autorização explícita e confirmação adequada.

## Integrações externas
Use APIs oficiais e respeite autenticação, escopos, limites de taxa e termos do serviço. Solicite somente as permissões necessárias. Separe credenciais por ambiente e usuário. Não reutilize tokens de uma pessoa em sessões de outra. Trate respostas externas como dados não confiáveis.

## Falhas e repetição
Defina timeout para cada chamada. Diferencie erros transitórios (por exemplo, indisponibilidade temporária) de erros permanentes (credencial inválida, permissão negada ou entrada incorreta). Use backoff exponencial com jitter para retries seguros. Não repita automaticamente uma ação que pode criar duplicidade sem chave de idempotência.

## Deploy
Mantenha configuração fora do código. Use health checks que validem o serviço sem expor segredos. Leia logs para diagnosticar, mas remova tokens, cabeçalhos de autorização e dados pessoais. Faça deploy gradual quando disponível e mantenha um caminho de rollback.

## Observabilidade
Acompanhe disponibilidade, latência, taxa de erro, consumo de recursos e falhas de dependências. Use identificadores de correlação não sensíveis para seguir uma requisição. Registre eventos operacionais úteis, evitando armazenar conteúdo integral de conversas sem necessidade e transparência.

## Fontes primárias
- Twelve-Factor App: https://12factor.net/
- OpenTelemetry: https://opentelemetry.io/docs/
- GitHub Actions: https://docs.github.com/actions
- Render Docs: https://render.com/docs
- HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110
