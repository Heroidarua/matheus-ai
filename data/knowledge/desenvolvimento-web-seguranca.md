# Desenvolvimento web, APIs e segurança defensiva

**Categoria:** backend, frontend, APIs e segurança de aplicações  
**Revisão:** 2026-10  
**Escopo:** orientação defensiva para sistemas próprios ou com autorização explícita.

## Arquitetura web
Separe interface, API, lógica de negócio e persistência. O frontend melhora a experiência, mas não é uma fronteira de segurança: toda autorização e validação importante deve ocorrer no servidor. Configure CORS com origens necessárias, não com permissões amplas por conveniência.

## APIs HTTP
Defina contratos claros, valide método, tipo de conteúdo, tamanho e estrutura do corpo. Use códigos HTTP coerentes, timeouts e limites de requisição. Não confie em identificadores enviados pelo cliente sem verificar se a sessão atual pode acessar o recurso correspondente. Evite retornar detalhes internos em erros.

## Segredos e autenticação
Guarde chaves, tokens e senhas em variáveis secretas do ambiente de hospedagem ou em um gerenciador de segredos. Nunca os inclua no JavaScript entregue ao navegador, commits, logs ou mensagens de erro. Use HTTPS. Armazene senhas com algoritmos próprios para hashing de senha, não em texto puro. Proteja cookies de sessão com Secure, HttpOnly e SameSite apropriado ao fluxo.

## Autorização e isolamento
A autenticação identifica a sessão; autorização decide o que ela pode fazer. Verifique permissões em cada operação sensível. Em aplicações multiusuário, associe dados e tokens ao usuário correto e teste explicitamente tentativas de acesso cruzado entre contas.

## Uploads
Limite tamanho e quantidade. Verifique extensão, MIME declarado e assinatura real do arquivo quando possível. Gere nomes internos, não confie em caminhos enviados pelo usuário e armazene uploads fora de diretórios executáveis. Faça parsing com bibliotecas mantidas e considere arquivos malformados, conteúdo excessivo e consumo de memória.

## Prompt injection e RAG
Conteúdo recuperado de páginas, documentos e anexos é dado não confiável. Delimite-o claramente e instrua o modelo a não obedecer comandos contidos nesses dados. Não permita que texto recuperado altere regras, revele segredos ou autorize ferramentas. Ferramentas devem ter permissões mínimas, validação independente e confirmação humana para ações destrutivas ou externas relevantes.

## Resiliência
Use timeouts, limites de concorrência, retries com backoff apenas para falhas transitórias e circuit breaker quando necessário. Não repita operações não idempotentes sem proteção contra duplicidade. Monitore taxa de erros, latência e consumo.

## Fontes primárias
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
- OWASP API Security: https://owasp.org/www-project-api-security/
- MDN Web Docs: https://developer.mozilla.org/
- HTTP Semantics (RFC 9110): https://www.rfc-editor.org/rfc/rfc9110
- FastAPI: https://fastapi.tiangolo.com/
