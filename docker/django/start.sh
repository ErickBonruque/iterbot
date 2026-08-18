#!/bin/sh

set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# O host de producao (gosh) tem 1 vCPU e 1.8 GB de RAM. Com o worker sync unico
# que havia aqui, o backend atendia uma requisicao por vez: qualquer request
# lenta (admin, portal, scrape) segurava o POST do webhook do WAHA ate estourar
# o timeout, e o WAHA reenviava o evento — resposta duplicada para o aluno.
# gthread ataca o gargalo real (espera de I/O em banco, WAHA e e-mail) sem o
# custo de RAM de mais processos. Ajustavel por env var, sem rebuild da imagem:
# em aperto de memoria, GUNICORN_WORKERS=1 ainda mantem as threads.
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_THREADS="${GUNICORN_THREADS:-4}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-60}"

# exec: gunicorn assume o PID 1 e recebe os sinais de parada do Docker direto,
# encerrando as requisicoes em curso antes de sair.
# max-requests recicla o worker periodicamente — protecao barata contra
# vazamento de memoria num host onde RAM e disco sao os limites.
exec gunicorn waha_bot.wsgi:application \
    --bind 0.0.0.0:8000 \
    --worker-class gthread \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --max-requests 500 \
    --max-requests-jitter 50
