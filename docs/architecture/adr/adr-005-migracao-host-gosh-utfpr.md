# ADR-005: Migração da EC2 AWS para VM própria da UTFPR (`gosh`)

## Status

Accepted (supersedes parte de [ADR-004](adr-004-ec2-docker-compose.md))

## Date

2026-07-01

## Context

O deploy inicial rodava numa EC2 AWS t3.small (ADR-004). Duas mudanças de contexto motivaram a migração:

1. **Custo/hospedagem institucional:** a UTFPR passou a fornecer hospedagem própria, eliminando o custo AWS e a dependência de conta externa.
2. **Host próprio em vez de compartilhado:** o plano anterior (`docs/deploy/MIGRACAO-DOMINIO-FIXO.md`) previa migrar para o servidor `200.134.22.218` (`chat-universitario.sh.utfpr.edu.br`), **compartilhado com outro bot de WhatsApp**. Esse plano nunca foi executado. Em vez disso, o projeto conseguiu uma **VM dedicada**: `gosh.sh.utfpr.edu.br` / `200.134.22.219`.

A EC2 antiga (conta AWS do projeto) foi **parada** em 2026-06-30, com o volume EBS preservado durante a transição, e posteriormente terminada após a validação da migração.

## Decision

**Migrar o deploy para a VM própria da UTFPR `gosh.sh.utfpr.edu.br` (`200.134.22.219`), mantendo Docker Compose.**

### Características do host

- Ubuntu 22.04 LTS, kernel 5.15, **1 vCPU** (Xeon E7-4850), **1.8 GB RAM** (+3.8 GB swap), **19 GB de disco** (~9 GB livres). Gerida pela **COGETI/UTFPR via Ansible**.
- Acesso SSH: usuário institucional (grupo `sudo`), autenticação por senha.
- **Porta 22 (SSH) filtrada de fora da rede da UTFPR** — administração e deploy exigem estar no campus ou VPN institucional. Portas **80/443 acessíveis pela internet** (alunos, portal de empresas, Let's Encrypt HTTP-01).
- Docker Engine 29.6.1 + Compose v5.2.0 instalados via repositório oficial, com rotação de log (`json-file`, `max-size=10m`, `max-file=3`) e `live-restore`.

### Domínio

- Produção: **`gosh.sh.utfpr.edu.br`** (1 registro A). O domínio `chat-universitario.sh.utfpr.edu.br` foi abandonado.

### Estratégia de dados (o que migra e o que recomeça)

- **Cursos e termos de busca:** preservados a partir do **próprio repositório** (`apps/courses/fixtures/courses_terms.json` + comando `seed_courses`), que já contêm os 3 cursos e 35 termos do campus Santa Helena. **Não** há migração do banco da EC2 antiga.
- **Empresas, alunos e vagas:** descartados — eram apenas dados de teste (o software ainda não estava em produção). Começam do zero no host novo.
- Consequência: a EC2 antiga pode ser **terminada** sem dump de banco (após confirmação de que não houve edições de termos feitas só em produção).

## Consequences

### Positive

- Custo zero de hospedagem (some a fatura AWS).
- Host **dedicado** — sem contenção com o bot vizinho; regras de convivência do plano antigo deixam de ser necessárias.
- Dados essenciais (cursos/termos) versionados em código, reproduzíveis com um comando.

### Negative

- **Recurso menor** que a EC2 (1 vCPU/1.8 GB vs 2 vCPU/2 GB) e menor que o recomendado (2–4 GB) — risco de OOM com a stack completa (WAHA/Chromium é o maior consumidor). Exige ajuste de limites de memória no `docker-compose.prod.yml` (Gate 3).
- **Deploy dependente da rede da UTFPR** (SSH filtrado de fora) — CI/CD via GitHub Actions não alcança a porta 22; opções: self-hosted runner na rede, deploy manual no campus, ou VPN institucional.
- OS/patching sob gestão da COGETI (Ansible) — mudanças fora do Ansible podem ser sobrescritas.

### Neutral

- WAHA continua interno (ADR-001 inalterado); dashboard só via túnel SSH.
- EC2 antiga parada com EBS preservado até a validação final; depois será terminada.
