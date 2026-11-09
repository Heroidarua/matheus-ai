# Conexão GitHub individual por usuário

## Como funciona

A ADA-M usa uma única **GitHub App** (ADA-M Assistant), mas cada sessão do navegador realiza sua própria instalação/autorização no GitHub. A chave privada e o App ID configurados no Render identificam a aplicação; eles **não conectam a conta pessoal do proprietário do projeto** para todos os usuários.

1. Cada pessoa abre **Ferramentas → Conectar GitHub** na própria sessão da ADA-M.
2. O GitHub abre a página oficial de instalação da ADA-M Assistant. A pessoa escolhe sua conta pessoal e seleciona quais repositórios deseja liberar.
3. O callback valida o parâmetro `state` associado à sessão que iniciou a conexão e guarda o ID da instalação e o login da conta nessa sessão.
4. A lista de repositórios é consultada usando o token da instalação daquela sessão. A seleção de repositório é validada novamente contra a instalação.
5. Desconectar remove os dados GitHub daquela sessão ADA-M; não desinstala o aplicativo da conta GitHub.

## Isolamento entre pessoas

A integração atual não usa um token pessoal compartilhado nem uma conta GitHub central. O cookie de sessão da ADA-M é assinado pelo servidor e contém o ID da instalação, a conta conectada, o repositório selecionado e a branch da sessão. As propostas de alteração também recebem um identificador de proprietário de sessão e não podem ser confirmadas por outra sessão.

**Importante:** a ADA-M ainda não possui uma identidade/login próprio para usuários. Portanto, a associação é por sessão de navegador, não por uma conta interna ADA-M. Cada pessoa deve usar seu próprio perfil de navegador; não compartilhe o mesmo perfil/sessão com outras pessoas. Em dispositivos compartilhados, desconecte o GitHub e encerre a sessão do navegador ao terminar.

## Contas pessoais e organizações

- Para repositórios pessoais, instale a ADA-M Assistant na sua conta pessoal e selecione somente os repositórios que deseja disponibilizar.
- Para repositórios de uma organização, a organização precisa permitir/instalar a GitHub App. A instalação em uma conta pessoal não concede automaticamente acesso aos repositórios da organização.
- A integração só consegue agir nos repositórios concedidos à instalação e dentro das permissões da GitHub App.
- A atividade é atribuída à GitHub App (token de instalação), não ao usuário como autor OAuth individual. Se for necessário que cada commit/comentário apareça como ação em nome da pessoa, será necessária uma etapa adicional de autorização user-to-server OAuth e armazenamento seguro de tokens individuais.

## Segurança

- Nunca coloque a chave privada da GitHub App no navegador, no repositório ou no chat. Ela permanece somente nas variáveis privadas do Render.
- Não compartilhe tokens, cookies ou sessões.
- Escritas exigem prévia e confirmação explícita; são feitas em uma branch separada. Criar Pull Request é outra confirmação.
- Desconectar a sessão ADA-M não revoga a instalação na conta GitHub. Para revogar totalmente, acesse GitHub → Settings → Applications → Installed GitHub Apps e desinstale ADA-M Assistant.
- A instalação e a autorização podem ser revogadas pelo usuário no GitHub a qualquer momento.

## Configuração da GitHub App

- Setup URL: `https://ada-m.onrender.com/api/github/callback`
- Webhook: desativado (não é necessário para o fluxo atual).
- Permissões mínimas atuais: Contents (Read and write), Pull requests (Read and write), Metadata (Read-only).
- O Render mantém `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_SESSION_SECRET`, `PUBLIC_APP_URL` e `COOKIE_HTTPS_ONLY=true`.

