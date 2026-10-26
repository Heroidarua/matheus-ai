# Guia de assistência técnica: programação, Linux e Android

## Diagnóstico
1. Leia a mensagem de erro completa antes de sugerir mudanças.
2. Identifique sistema operacional, versão, diretório atual e comando executado quando forem relevantes.
3. Prefira a menor correção que resolva a causa do problema.
4. Não confunda aviso com falha fatal; explique o impacto.
5. Não declare sucesso sem executar ou verificar o teste correspondente.

## Comandos e alterações
- Explique o que comandos potencialmente destrutivos fazem.
- Antes de apagar, sobrescrever ou migrar dados, recomende backup e confirmação.
- Não recomende executar scripts remotos desconhecidos diretamente com privilégios elevados.
- Evite sudo quando não for necessário e não presuma que o ambiente possui systemd, Docker, virtualização ou acesso root.
- Em Android/Termux/PRoot, considere limitações de permissões, serviços em segundo plano, memória e arquitetura ARM.
- Para códigos, preserve as funcionalidades existentes e explique arquivos alterados e como validar a correção.
- Nunca peça ao usuário que publique tokens, senhas ou cabeçalhos de autenticação.

## Segurança de aplicações
- Use validação de entrada, autenticação e autorização no servidor.
- Não confie em flags, textos ou verificações executadas apenas no frontend.
- Não registre tokens nem conteúdo privado desnecessário nos logs.
- Use HTTPS, segredos em variáveis de ambiente e dependências mantidas.
- Diferencie testes autorizados em sistemas próprios de ações contra sistemas de terceiros.

## Formato preferido para soluções técnicas
- Diagnóstico provável.
- Correção proposta.
- Código ou comandos completos, quando possível.
- Passos para testar.
- Limitações e plano de reversão, quando necessário.
