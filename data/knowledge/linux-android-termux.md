# Linux, Android e Termux

**Categoria:** sistemas operacionais, terminal e ambientes móveis  
**Revisão:** 2026-10

## Primeiro diagnóstico
Antes de sugerir comandos, identifique distribuição, arquitetura, versão, shell, diretório atual, permissões disponíveis e se o ambiente é Linux nativo, contêiner, máquina virtual ou PRoot. Em Android, confirme se o usuário está no Termux e se o dispositivo tem root. Não presuma systemd, Docker daemon, KVM ou virtualização de hardware.

## Comandos e privilégios
Explique o efeito de comandos que apagam, sobrescrevem, alteram permissões ou modificam partições. Use privilégios elevados somente quando necessários. Não recomende baixar e executar scripts remotos diretamente com root. Prefira pacotes dos repositórios oficiais e verifique a origem dos binários.

## Termux e Android
Termux oferece ambiente Linux em espaço de usuário, não uma distribuição Linux com todos os recursos de um servidor convencional. Pacotes e caminhos diferem de Debian/Ubuntu. Serviços em segundo plano podem ser encerrados pelo Android; considere restrições de bateria, memória, armazenamento e permissões. Acesso a arquivos compartilhados depende de permissões Android e de configuração explícita.

## PRoot e contêineres
PRoot simula aspectos de um ambiente Linux sem fornecer kernel próprio nem privilégios reais de root. Recursos que exigem systemd, montagem especial, namespaces ou módulos de kernel podem não funcionar. Explique limitações e ofereça alternativa compatível com o ambiente, em vez de insistir em comandos de servidor tradicional.

## Rede e diagnóstico
Use ferramentas como ip, ss, ping, curl e dig quando disponíveis para separar falhas de DNS, rota, porta, TLS e aplicação. Não conclua que um serviço está acessível apenas porque o processo iniciou. Verifique o endpoint de saúde e os logs sem expor segredos.

## Backup e recuperação
Antes de alterar boot, armazenamento, permissões recursivas ou dados de aplicativos, faça backup verificável. Evite comandos recursivos sem limitar o caminho. Mostre como conferir o resultado e como reverter.

## Fontes primárias
- Documentação oficial do Termux: https://termux.dev/
- Wiki do Termux: https://github.com/termux/termux-packages/wiki
- Documentação Ubuntu: https://help.ubuntu.com/
- Manual GNU Coreutils: https://www.gnu.org/software/coreutils/manual/
- Documentação Linux man-pages: https://man7.org/linux/man-pages/
