# Atualização administrativa do executor ADA-M

Esta atualização adiciona duas operações autenticadas e somente leitura ao executor VPS:

- `GET /admin/diagnostics`: uso básico de CPU/memória/disco, estado dos serviços ADA-M e presença das ferramentas previstas.
- `GET /admin/install-tools/status`: estado e resultado do serviço systemd de instalação do conjunto padrão.

O script `ada-admin` mantém a operação existente `install-tools`, corrige o tratamento de operações inválidas e não aceita nomes de pacotes, serviços ou comandos fornecidos pelo modelo.

## Instalação

1. Copie esta pasta inteira para a VPS, preservando os três arquivos.
2. Entre na pasta copiada.
3. Execute como root:

```bash
bash install-admin-upgrade.sh
```

O instalador cria um backup em `/root/ada-executor-backups/`, valida a sintaxe Python/Bash, reinicia `ada-executor.service` e verifica `http://127.0.0.1:8000/health`. Se a validação ou o health check falhar, restaura os arquivos anteriores.

O instalador espera a instalação existente em `/opt/ada-executor`, o ambiente virtual em `/opt/ada-executor/venv` e o usuário de serviço `ada`. Não altera o token, o serviço systemd, o executor isolado `ada-exec` nem as regras sudoers.

## Uso pela ADA-M

Depois de atualizar a VPS e publicar a versão correspondente do backend:

- `ada-admin diagnostics`
- `ada-admin install-tools-status`
- `ada-admin install-tools` (inicia a instalação fixa já existente)

Os dois primeiros comandos são consultas. A instalação continua sendo uma operação administrativa separada e explicitamente solicitada. Não há endpoint de shell root nem nomes arbitrários de serviços/pacotes.
