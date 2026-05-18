# 🐳 Como Rodar o IterBot com Docker

Guia completo para executar o projeto IterBot-UTFPR usando Docker e Docker Compose.

## 📋 Pré-requisitos

- **Docker** instalado e rodando (versão 20.10+)
- **Docker Compose** instalado (versão 2.0+)
- Terminal aberto na pasta do projeto
- **Git** para clonar o repositório

### Verificar Instalação

```bash
docker --version
docker-compose --version
```

---

## 🚀 Primeira Execução (Setup Inicial)

### 1. Clone o Repositório

```bash
git clone https://github.com/ErickBonruque/iterbot.git
cd iterbot
```

### 2. Configure as Variáveis de Ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite o arquivo .env com suas configurações
nano .env  # ou use seu editor preferido
```

**Principais variáveis a configurar:**

```ini
# Para produção, altere:
DEBUG=False
DOMAIN=seu-dominio.com.br
ALLOWED_HOSTS=localhost,127.0.0.1,seu-dominio.com.br

# Para desenvolvimento local, mantenha:
DEBUG=True
DOMAIN=localhost
```

### 3. Configure os Secrets

Os secrets são credenciais sensíveis que não devem estar no código.

```bash
cd secrets

# Copie os arquivos de exemplo
cp django_secret_key.txt.example django_secret_key.txt
cp postgres_password.txt.example postgres_password.txt
cp waha_api_key.txt.example waha_api_key.txt
cp waha_dashboard_password.txt.example waha_dashboard_password.txt
cp waha_swagger_password.txt.example waha_swagger_password.txt
```

**Gere valores seguros automaticamente:**

```bash
# Django Secret Key
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > django_secret_key.txt

# Senhas aleatórias seguras
openssl rand -base64 32 > postgres_password.txt
openssl rand -base64 32 > waha_api_key.txt
openssl rand -base64 32 > waha_dashboard_password.txt
openssl rand -base64 32 > waha_swagger_password.txt

cd ..
```

**⚠️ IMPORTANTE:** Nunca commite os arquivos `.txt` em `secrets/`!

### 4. Build das Imagens

```bash
docker-compose build
```

**Ou usando o Makefile:**

```bash
make build
```

Este processo pode levar alguns minutos na primeira vez.

### 5. Inicie os Serviços

```bash
# Modo foreground (ver logs)
docker-compose up

# Modo background (daemon)
docker-compose up -d
```

**Ou usando o Makefile:**

```bash
make up
```

### 6. Aguarde os Health Checks

Os serviços têm health checks configurados. Aguarde até que todos estejam saudáveis:

```bash
docker-compose ps
```

Você deve ver algo assim:

```
NAME                          STATUS
iterbot-utfpr-backend-1     Up (healthy)
iterbot-utfpr-db-1          Up (healthy)
iterbot-utfpr-redis-1       Up (healthy)
iterbot-utfpr-waha-1        Up
iterbot-utfpr-traefik-1     Up
```

### 7. Execute as Migrações do Banco de Dados

```bash
docker-compose exec backend python manage.py migrate
```

**Ou usando o Makefile:**

```bash
make migrate
```

### 8. Crie um Superusuário

```bash
docker-compose exec backend python manage.py createsuperuser
```

Siga as instruções para criar seu usuário administrador.

### 9. Colete Arquivos Estáticos (Produção)

```bash
docker-compose exec backend python manage.py collectstatic --noinput
```

### 10. Verifique o Health Check

```bash
curl http://localhost/health/
```

Resposta esperada:

```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "cache": "healthy"
  }
}
```

### 11. Acesse a Aplicação

- **Dashboard**: http://localhost/dashboard/
- **Django Admin**: http://localhost/admin/
- **WAHA Dashboard**: http://waha.localhost/
- **Traefik Dashboard**: http://localhost:8080/
- **Health Check**: http://localhost/health/

---

## 🔄 Atualizações e Alterações

### Cenário 1: Alterou Código Python (.py)

**Não precisa rebuildar!** O código é montado via volume.

```bash
# Reinicie apenas o backend
docker-compose restart backend

# Ou reinicie todos os serviços
docker-compose restart
```

### Cenário 2: Alterou pyproject.toml ou poetry.lock (Dependências)

**Precisa rebuildar a imagem:**

```bash
# Pare os serviços
docker-compose down

# Rebuild apenas o backend
docker-compose build backend

# Ou rebuild tudo
docker-compose build

# Suba novamente
docker-compose up -d
```

### Cenário 3: Alterou docker-compose.yml ou Dockerfile

**Precisa rebuildar:**

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

### Cenário 4: Alterou Modelos Django (models.py)

**Precisa criar e aplicar migrações:**

```bash
# Crie as migrações
docker-compose exec backend python manage.py makemigrations

# Aplique as migrações
docker-compose exec backend python manage.py migrate
```

### Cenário 5: Alterou Configuração do Traefik

```bash
# Reinicie apenas o Traefik
docker-compose restart traefik
```

---

## 🛠️ Comandos Úteis

### Ver Logs

```bash
# Todos os serviços
docker-compose logs -f

# Apenas backend
docker-compose logs -f backend

# Apenas últimas 100 linhas
docker-compose logs --tail=100 backend

# Apenas erros
docker-compose logs backend | grep ERROR
```

### Executar Comandos no Container

```bash
# Shell interativo
docker-compose exec backend bash

# Executar manage.py
docker-compose exec backend python manage.py <comando>

# Shell do Django
docker-compose exec backend python manage.py shell

# Executar testes
docker-compose exec backend pytest
```

### Verificar Status dos Serviços

```bash
# Status resumido
docker-compose ps

# Status detalhado
docker-compose ps -a

# Ver uso de recursos
docker stats
```

### Limpar Volumes e Dados

```bash
# ⚠️ CUIDADO: Remove TODOS os dados!
docker-compose down -v

# Remover apenas volumes órfãos
docker volume prune

# Remover imagens não usadas
docker image prune -a
```

### Backup do Banco de Dados

```bash
# Criar backup
docker-compose exec db pg_dump -U iterbot_user iterbot > backup.sql

# Restaurar backup
docker-compose exec -T db psql -U iterbot_user iterbot < backup.sql
```

---

## 🐛 Troubleshooting

### Problema: "Port already in use"

```bash
# Descubra qual processo está usando a porta
sudo lsof -i :80
sudo lsof -i :443

# Pare o processo ou mude a porta no docker-compose.yml
```

### Problema: "Cannot connect to database"

```bash
# Verifique se o PostgreSQL está healthy
docker-compose ps db

# Veja os logs do banco
docker-compose logs db

# Reinicie o banco
docker-compose restart db
```

### Problema: "Permission denied" em secrets/

```bash
# Ajuste as permissões
chmod 600 secrets/*.txt
```

### Problema: Migrations não aplicadas

```bash
# Force a criação de migrações
docker-compose exec backend python manage.py makemigrations --empty <app_name>

# Aplique novamente
docker-compose exec backend python manage.py migrate --fake-initial
```

### Problema: Redis não conecta

```bash
# Verifique o status
docker-compose ps redis

# Teste a conexão
docker-compose exec redis redis-cli ping
# Deve retornar: PONG

# Veja os logs
docker-compose logs redis
```

### Problema: WAHA não responde

```bash
# Verifique os logs
docker-compose logs waha

# Reinicie o serviço
docker-compose restart waha

# Verifique se o volume de sessões está correto
docker volume ls | grep waha
```

---

## 🔒 Produção

### Checklist para Deploy em Produção

- [ ] Configurar `DEBUG=False` no `.env`
- [ ] Configurar `DOMAIN` com seu domínio real
- [ ] Gerar secrets seguros (não usar os de exemplo)
- [ ] Configurar certificado SSL (Let's Encrypt via Traefik)
- [ ] Configurar backup automático do banco de dados
- [ ] Configurar monitoramento (logs, métricas)
- [ ] Revisar `ALLOWED_HOSTS` no `.env`
- [ ] Configurar firewall (portas 80, 443, 8080)
- [ ] Testar health checks
- [ ] Configurar restart policies (já configurado)

### HTTPS com Let's Encrypt

O Traefik está configurado para obter certificados automaticamente.

**Edite `infra/traefik/traefik.yml`:**

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      email: seu-email@exemplo.com  # ALTERE AQUI
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web
```

**Certifique-se de que:**
1. Seu domínio aponta para o servidor (DNS configurado)
2. Portas 80 e 443 estão abertas
3. `DOMAIN` no `.env` está correto

### Backup Automático

Crie um script de backup:

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup do banco
docker-compose exec -T db pg_dump -U iterbot_user iterbot > "$BACKUP_DIR/db_$DATE.sql"

# Backup dos volumes
docker run --rm -v iterbot-utfpr_postgres_data:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/postgres_data_$DATE.tar.gz /data

# Manter apenas últimos 7 dias
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

Configure no cron:

```bash
# Backup diário às 2h da manhã
0 2 * * * /path/to/backup.sh
```

---

## 📊 Monitoramento

### Ver Métricas de Recursos

```bash
# CPU, memória, rede
docker stats

# Apenas backend
docker stats iterbot-utfpr-backend-1
```

### Logs Estruturados

Os logs são em formato JSON para fácil parsing:

```bash
# Ver logs estruturados
docker-compose logs backend | jq .

# Filtrar por nível
docker-compose logs backend | jq 'select(.level=="error")'

# Filtrar por correlation_id
docker-compose logs backend | jq 'select(.correlation_id=="abc-123")'
```

---

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes
docker-compose exec backend pytest

# Com cobertura
docker-compose exec backend pytest --cov

# Apenas um app
docker-compose exec backend pytest apps/bot/

# Verbose
docker-compose exec backend pytest -v
```

### Verificação de Código

```bash
# Formatação
docker-compose exec backend black .

# Linting
docker-compose exec backend ruff check .

# Type checking
docker-compose exec backend mypy .
```

---

## 🔧 Makefile (Opcional)

Se você tem um `Makefile`, pode usar comandos simplificados:

```bash
make build      # Build das imagens
make up         # Subir serviços
make down       # Parar serviços
make logs       # Ver logs
make migrate    # Aplicar migrações
make test       # Executar testes
make shell      # Shell do Django
make lint       # Verificar código
```

---

## 📚 Recursos Adicionais

- [Documentação Docker](https://docs.docker.com/)
- [Documentação Docker Compose](https://docs.docker.com/compose/)
- [Documentação Django](https://docs.djangoproject.com/)
- [Documentação Traefik](https://doc.traefik.io/traefik/)
- [REFACTORING.md](REFACTORING.md) - Detalhes da refatoração

---

## 🆘 Suporte

Se encontrar problemas:

1. Verifique os logs: `docker-compose logs`
2. Verifique o health check: `curl http://localhost/health/`
3. Consulte a seção de Troubleshooting acima
4. Abra uma issue no GitHub

---

**Versão:** 2.0.0 (Refatorado para Produção)
**Data:** 2024-11-29
