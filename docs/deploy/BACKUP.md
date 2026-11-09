# Backup e restauração (host gosh)

Substitui o backup para S3 da era EC2 (conta AWS encerrada). Tudo roda **no host**, no
usuário `a2587246`, sem root.

| O quê | Onde | Retenção |
|---|---|---|
| Dump do Postgres (`iterbot_db_*.sql.gz`) | `~/iterbot/backups/daily/` | 14 diários |
| `.env` + `secrets/` + `docker-compose.resources.yml` (`iterbot_config_*.tar.gz`) | idem | 14 diários |
| Cópia de domingo dos dois | `~/iterbot/backups/weekly/` | 4 semanais |
| Cópia fora do host (criptografada) | bucket Backblaze B2 via `rclone` | 30 dias |

> O tar de configuração existe porque sem a `ENCRYPTION_KEY` do `.env` os campos
> criptografados do banco ficam ilegíveis — restaurar só o dump não basta num host novo.
> `backups/` está no `.gitignore` e é criado com permissão 700 (dados pessoais + segredos).

## Scripts (`deployment/scripts/`)

- `backup-postgres.sh` — dump + validação (tamanho, `gzip -t`, rodapé "dump complete") +
  tar de configuração + rotação + cópia fora do host. Falhou → alerta por e-mail para
  `ALERT_EMAIL` (`manage.py send_ops_alert`) e `exit 1`. Sucesso → grava `backups/last-success`
  (o `smoke-check.sh` acusa se passar de 26 h).
- `install-backup-cron.sh` — agenda no cron do usuário: backup às 03:30 e
  `check-disk-space.sh` a cada 6 h (alerta com disco ≥ 85%). Idempotente.
- `restore-test.sh [arquivo]` — restaura num Postgres **temporário** e compara a contagem de
  linhas das tabelas principais com a produção. Não toca no banco real.
- `restore-postgres.sh <arquivo>` — restaura **por cima** da produção (pede `RESTAURAR`; para
  backend/worker/beat durante a restauração e os sobe de novo).
- `deploy.sh` faz um backup antes de todo deploy.

## Ativar no host (uma vez)

```bash
cd ~/iterbot
bash deployment/scripts/backup-postgres.sh      # 1º backup manual (sem cópia externa ainda)
bash deployment/scripts/restore-test.sh         # prova que o backup restaura
bash deployment/scripts/install-backup-cron.sh  # agenda
crontab -l                                      # conferir
```

## Cópia fora do host: Backblaze B2 + rclone crypt

1. **Conta e bucket** (no navegador): crie a conta em backblaze.com (10 GB grátis, sem
   cartão), um bucket **privado** (ex.: `iterbot-backups-<algo-aleatorio>`) e uma
   *Application Key* **restrita a esse bucket** com leitura e escrita. Anote `keyID` e
   `applicationKey`.
2. **rclone no host, sem root:**
   ```bash
   mkdir -p ~/bin && cd /tmp
   curl -fsSLO https://downloads.rclone.org/rclone-current-linux-amd64.zip
   unzip -o rclone-current-linux-amd64.zip && mv rclone-*-linux-amd64/rclone ~/bin/
   ~/bin/rclone version
   ```
3. **Remotes** (interativo, `~/bin/rclone config`), ou em linha:
   ```bash
   ~/bin/rclone config create iterbot-b2 b2 account <keyID> key <applicationKey> hard_delete true
   ~/bin/rclone config create iterbot-offsite crypt remote iterbot-b2:<bucket>/iterbot \
       password "<senha-forte-1>" password2 "<senha-forte-2>" --obscure
   chmod 600 ~/.config/rclone/rclone.conf
   ```
   `hard_delete` faz a retenção apagar de verdade (sem isso o B2 guarda versões ocultas).
4. **Guarde as duas senhas do crypt FORA do host** (gerenciador de senhas). Sem elas a
   cópia externa é ilegível — que é o objetivo, mas também vale para você.
5. Ligue no `.env` do projeto e teste:
   ```bash
   echo 'OFFSITE_REMOTE=iterbot-offsite:' >> ~/iterbot/.env
   bash deployment/scripts/backup-postgres.sh
   ~/bin/rclone ls iterbot-offsite:daily          # nomes legíveis (rclone descriptografa)
   ~/bin/rclone ls iterbot-b2:<bucket>/iterbot    # no bucket: nomes e conteúdo cifrados
   ```

## Restaurar

```bash
# do disco local
bash deployment/scripts/restore-postgres.sh backups/daily/iterbot_db_AAAAMMDD_HHMMSS.sql.gz

# da cópia externa (host novo: reinstale o rclone e recrie os remotes com as senhas guardadas)
~/bin/rclone copy iterbot-offsite:daily/iterbot_db_AAAAMMDD_HHMMSS.sql.gz backups/restore/
~/bin/rclone copy iterbot-offsite:daily/iterbot_config_AAAAMMDD_HHMMSS.tar.gz backups/restore/
tar -xzf backups/restore/iterbot_config_*.tar.gz -C ~/iterbot   # .env, secrets/, resources.yml
```

Num host novo: restaure a configuração, suba `db` (`docker compose ... up -d db`), rode
`restore-postgres.sh` e depois suba o resto. O WhatsApp precisa ser pareado de novo (QR em
`/admin/status-bot/`); certificados TLS são reemitidos sozinhos.

## Variáveis (opcionais, no `.env`)

`BACKUP_DIR` (padrão `~/iterbot/backups`), `BACKUP_KEEP_DAILY` (14), `BACKUP_KEEP_WEEKLY` (4),
`OFFSITE_REMOTE` (vazio = sem cópia externa), `OFFSITE_KEEP_DAYS` (30), `DISK_THRESHOLD` (85).
