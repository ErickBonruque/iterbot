# Backup PostgreSQL para S3 - IterBot

## Pre-requisitos

1. Conta AWS com bucket S3 criado
2. IAM Role attached a instancia EC2
3. AWS CLI instalado na EC2 (via `setup-ec2.sh`)

## 1. Criar Bucket S3

```bash
aws s3 mb s3://iterbot-backups
```

## 2. Configurar Lifecycle Policy

A lifecycle policy expira backups apos 28 dias no prefixo `weekly/`:

```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket iterbot-backups \
  --lifecycle-configuration file://docs/deploy/s3-lifecycle.json
```

Arquivo `s3-lifecycle.json` incluso neste diretorio.

## 3. Criar IAM Role para EC2

1. Console AWS -> IAM -> Roles -> Create role
2. Trusted entity: AWS service -> EC2
3. Attach policy customizada (ou inline):

```bash
aws iam create-policy \
  --policy-name IterBotBackupS3 \
  --policy-document file://docs/deploy/iam-backup-policy.json
```

4. Attach a role da EC2:

```bash
aws ec2 associate-iam-instance-profile \
  --instance-id i-XXXXXXXX \
  --iam-instance-profile Name=IterBotBackupRole
```

Arquivo `iam-backup-policy.json` incluso neste diretorio com permissoes minimas:
- `s3:PutObject` — upload de backups
- `s3:GetObject` — download para restauracao
- `s3:ListBucket` — listar backups disponiveis

## 4. Configurar Crontab

O script `setup-ec2.sh` ja configura automaticamente o crontab:

```
0 2 * * 0 /bin/bash /home/ubuntu/iterbot/deployment/scripts/backup-postgres.sh >> /var/log/iterbot-backup.log 2>&1
```

Para configurar manualmente:

```bash
crontab -e
# Adicionar a linha acima
```

## 5. Executar Backup Manual

```bash
./deployment/scripts/backup-postgres.sh
```

## 6. Restaurar Backup

```bash
# Listar backups disponiveis
./deployment/scripts/restore-postgres.sh

# Restaurar backup especifico
./deployment/scripts/restore-postgres.sh s3://iterbot-backups/weekly/iterbot_backup_20260413_020000.sql.gz
```

O script de restauracao pede confirmacao antes de sobrescrever o banco.

## 7. Verificar se Backup esta Funcionando

```bash
# Verificar ultimo backup no S3
aws s3 ls s3://iterbot-backups/weekly/ --human-readable

# Verificar log do crontab
tail -20 /var/log/iterbot-backup.log
```

## Variaveis de Ambiente

| Variavel | Padrao | Descricao |
|----------|--------|-----------|
| `S3_BACKUP_BUCKET` | `iterbot-backups` | Nome do bucket S3 |
| `S3_BACKUP_PREFIX` | `weekly` | Prefixo dentro do bucket |
| `PROJECT_DIR` | `/home/ubuntu/iterbot` | Diretorio do projeto na EC2 |
| `POSTGRES_USER` | `iterbot_user` | Usuario do PostgreSQL |
| `POSTGRES_DB` | `iterbot` | Nome do banco de dados |
