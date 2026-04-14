# Security Groups - CapyVagas EC2

## Regras Inbound (Ingress)

| Tipo | Protocolo | Porta | Origem | Descricao |
|------|-----------|-------|--------|-----------|
| SSH | TCP | 22 | Seu IP ou 0.0.0.0/0 | Acesso SSH (restringir ao seu IP em producao) |
| HTTP | TCP | 80 | 0.0.0.0/0 | Redirect para HTTPS via Traefik |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Trafego web encriptado |

## Regras Outbound (Egress)

| Tipo | Protocolo | Porta | Destino | Descricao |
|------|-----------|-------|---------|-----------|
| All traffic | All | All | 0.0.0.0/0 | Permite saida para internet |

## Portas que NAO devem ser abertas

| Porta | Servico | Motivo |
|-------|---------|--------|
| 3000 | WAHA | Acessivel apenas via Traefik (waha.DOMAIN) |
| 5432 | PostgreSQL | Apenas rede interna Docker |
| 6379 | Redis | Apenas rede interna Docker |
| 8000 | Gunicorn | Apenas rede interna Docker (Traefik roteia) |
| 8080 | Traefik Dashboard | Desabilitado em producao |

## Configuracao via AWS CLI

```bash
# Substituir sg-XXXXXXXX pelo ID do seu security group

aws ec2 authorize-security-group-ingress --group-id sg-XXXXXXXX \
  --protocol tcp --port 22 --cidr SEU_IP/32

aws ec2 authorize-security-group-ingress --group-id sg-XXXXXXXX \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress --group-id sg-XXXXXXXX \
  --protocol tcp --port 443 --cidr 0.0.0.0/0
```
