# Deploy

Guias de deploy e configuracao de infraestrutura.

## Guias

| Arquivo | Descricao |
|---------|-----------|
| [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md) | Guia completo de deploy |
| [BACKUP_S3.md](BACKUP_S3.md) | Backup para S3 |
| [SECURITY_GROUPS.md](SECURITY_GROUPS.md) | Grupos de seguranca AWS |
| [SES_SANDBOX_EXIT.md](SES_SANDBOX_EXIT.md) | Sair do sandbox SES |

## Infraestrutura

- **Plataforma:** AWS EC2 (t3.small)
- **Container:** Docker Compose
- **Proxy:** Traefik v3.6
- **Dominio:** sslip.io (desenvolvimento)
