# IterBot - Hosting Cost Comparison

**Last updated:** 2026-04-17

## Baseline: AWS EC2 t3.small

| Item | Detail |
|------|--------|
| Instance | t3.small (2 vCPU, 2GB RAM) |
| Region | us-east-1 |
| EBS | 8GB gp3 (default) |
| EIP | 1 Elastic IP (free when attached) |
| Current RAM usage | ~1.5GB of 2GB |
| Monthly cost (on-demand) | ~$15.73/mo total |
| Reserved 1yr (no upfront) | ~$10.79/mo total |

**Current deployment:** Docker Compose on EC2 with Traefik reverse proxy, Let's Encrypt TLS, S3 backups via IAM Role.

## Comparison Table

| Provider | Plan | vCPU | RAM | Storage | Monthly Cost | SSL/TLS | Docker Compose | Notes |
|----------|------|------|-----|---------|--------------|---------|----------------|-------|
| **AWS EC2 t3.small** | On-Demand | 2 | 2GB | 8GB gp3 | ~$15.73 | Traefik + LE | ✅ | Baseline. Full control. |
| **AWS EC2 t3.small** | Reserved 1yr | 2 | 2GB | 8GB gp3 | ~$10.79 | Traefik + LE | ✅ | 32% savings. Best AWS option. |
| **Fly.io** | shared-cpu-1x | 1 | 256MB | 1GB | ~$5.91+extras | Auto LE | ❌ | Too little RAM for full stack. |
| **Fly.io** | multiple apps | 4 | 4×512MB | 4×1GB | ~$22-35 | Auto LE | ❌ | Complex migration. |
| **Render** | Starter | 0.5 | 512MB | — | ~$7+/service | Auto | ❌ | WAHA unsupported. |
| **Hetzner CX22** | Cloud | 2 | 4GB | 40GB | ~$4.50 | Traefik + LE | ✅ | EU latency ~180ms from BR. |
| **DigitalOcean** | Basic 1GB | 1 | 1GB | 25GB | $6 | Traefik + LE | ✅ | Tight RAM for full stack. |
| **DigitalOcean** | Basic 2GB | 1 | 2GB | 50GB | $12 | Traefik + LE | ✅ | Comparable to EC2. |

## Recommendation

**Stay with EC2 t3.small.** The cost differential vs cheaper VPS providers (Hetzner ~$4.50, DigitalOcean 2GB ~$12) doesn't justify the migration effort for an academic project. Current setup works and is already deployed. Consider a Reserved Instance if budget allows a 1-year commitment.

## Hidden Costs

| Cost Item | Monthly Estimate |
|-----------|-----------------|
| EC2 compute (t3.small on-demand) | $15.09 |
| EBS 8GB gp3 | $0.64 |
| Data transfer (est. 5GB) | $0.45 |
| S3 backups (est. 5GB) | $0.12 |
| SES emails (est. 1000/mo) | $0.00 (free tier) |
| Let's Encrypt | $0.00 |
| Elastic IP (attached) | $0.00 |
| **Total estimated monthly cost** | **~$16.30** |

## Cost Scenarios

| Scenario | Monthly Cost | Verdict |
|----------|-------------|---------|
| EC2 t3.small (current) | ~$15.73 on-demand | Baseline. Already working. |
| EC2 t3.small (reserved 1yr) | ~$10.79 | 32% savings. Best AWS option. |
| Hetzner CX22 | ~$4.50 | 71% cheaper. EU latency penalty. |
| DigitalOcean 2GB | $12/mo | 24% cheaper. Similar setup. |
| Fly.io / Render | $22-50/mo | More expensive. Architectural mismatch. |