# Seguranca — Hardening de Producao

Este documento registra as camadas defensivas aplicadas no deploy da
IterBot/CapyVagas em AWS EC2, e como operar com elas.

## Superficie de ataque publica

Apenas **duas portas** estao expostas em `0.0.0.0` no ambiente de
producao:

| Porta | Protocolo | Servico             | Autenticacao                |
|-------|-----------|---------------------|-----------------------------|
| 80    | HTTP      | Traefik (redirect)  | Redireciona 301 para 443    |
| 443   | HTTPS     | Traefik             | TLS 1.3 + Let's Encrypt     |

Qualquer outra porta (8000 backend, 3000 WAHA, 8080 Traefik dashboard,
5432 Postgres, 6379 Redis) fica **apenas na rede interna Docker**
(`172.20.0.0/16`) e nao e alcancavel da internet. Verifique com:

```bash
ss -tlnp | grep -E "0.0.0.0:(80|443|3000|8000|8080)"
# Deve listar apenas 80 e 443.
```

Ou no EC2:

```bash
docker ps --format '{{.Names}}\t{{.Ports}}'
```

Em `iterbot_backend` e `iterbot_waha`, a coluna Ports deve estar vazia.
Em `iterbot_traefik`, apenas `0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp`.

## Camadas defensivas ativas

### 1. TLS obrigatorio

- `traefik.prod.yml` forca `certResolver: letsencrypt` no entrypoint
  `websecure`.
- `traefik.http.middlewares.security-headers` injeta HSTS com
  `stsSeconds: 31536000`, `stsIncludeSubdomains`, `stsPreload`.
- Redirect HTTP -> HTTPS em `redirect-to-https`.

### 2. Autenticacao em camadas

- **Rotas admin (`/admin`, `/portal`)**: BasicAuth no Traefik
  (`admin-auth@file`, `usersFile: /etc/traefik/users/admin-users.txt`)
  **mais** login/session do Django.
- **WAHA (`waha.${DOMAIN}`)**: BasicAuth no Traefik
  (`waha-auth@file`).
- Usuarios gerados em `secrets/users/` via `setup-htpasswd.sh`.

### 3. Rate limiting (Traefik)

Definidos em `infra/traefik/dynamic/middlewares.yml`:

| Middleware          | Average  | Burst | Alvo                                    |
|---------------------|----------|-------|-----------------------------------------|
| `rate-limit`        | 100/s    | 50    | Trafego publico geral                   |
| `login-rate-limit`  | 5/min    | 10    | `/accounts/login`, `/empresas/login`    |
| `admin-rate-limit`  | 30/min   | 60    | `/admin`, `/portal`                     |

Excedentes recebem HTTP 429. Isso neutraliza brute-force sem fail2ban.
Rate-limit e por IP de origem (`ipStrategy.depth: 1`).

### 4. Docker secrets

Credenciais AWS/Django/Postgres/email estao em `/run/secrets/*.txt`
(montados read-only no container). Nunca em variaveis de ambiente cruas.
Ver `docker-compose.yml` `secrets:` e `config/_helpers.py`
`_read_secret_file()`.

### 5. Security headers

Aplicados em todas as rotas publicas (`security-headers@file`):

- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection` habilitado
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security` (HSTS) com preload

## Itens opcionais / nao ativos por default

### IP whitelist em admin/portal

Middleware `admin-ip-whitelist@file` definido mas com `0.0.0.0/0` (aceita
qualquer IP). Para restringir:

1. Edite `infra/traefik/dynamic/middlewares.yml`, substitua
   `0.0.0.0/0` pelos IPs/CIDRs permitidos (ex: `200.20.30.40/32`).
2. Em `docker-compose.prod.yml`, adicione `admin-ip-whitelist@file` aos
   middlewares do router `admin-secure`:
   ```yaml
   - "traefik.http.routers.admin-secure.middlewares=admin-auth@file,admin-ip-whitelist@file,security-headers@file,admin-rate-limit@file"
   ```
3. Redeploy.

**Cuidado**: seu IP publico provavelmente muda (ISP residencial). Use
apenas se tiver IP fixo ou VPN.

### fail2ban no host

Ainda nao configurado. Rate-limit do Traefik cobre a maior parte.
Considerar se aparecerem tentativas persistentes nos logs.

### WAF (AWS WAF ou Cloudflare)

Nao configurado — iria em frente ao Traefik, porem adiciona custo e
latencia. Rate-limit do Traefik basta para o volume atual.

## AWS Security Group

A instancia `***REMOVED***` deve ter Security Group permitindo
apenas:

- **Inbound**: `80/tcp` e `443/tcp` de `0.0.0.0/0` (publico)
- **Inbound**: `22/tcp` apenas via AWS SSM (sem porta SSH publica)
- **Outbound**: irrestrito (default)

Verifique em: AWS Console -> EC2 -> Security Groups -> sg da instancia.
Qualquer regra permitindo 8000, 3000, 8080, 5432, 6379 publicamente
**deve ser removida**.

## Monitoramento de ataques

Logs do Traefik em JSON (ativado em `traefik.prod.yml` `accessLog`).

```bash
# Listar IPs com maior numero de 401 (brute force em andamento)
docker compose logs traefik --tail 5000 | grep -oE '"ClientHost":"[^"]+"' \
  | sort | uniq -c | sort -rn | head -20

# Listar rotas mais atacadas
docker compose logs traefik --tail 5000 \
  | grep -oE '"RequestPath":"[^"]+"' | sort | uniq -c | sort -rn | head -20
```

## Historico

- **2026-04-24**: Hardening inicial — remocao de portas publicas
  desnecessarias, adicao de rate-limit stricto em login/admin, criacao
  de middleware ip-whitelist (opcional), documentacao. Commit: ver
  `git log docs/SECURITY.md`.
