#!/bin/sh

set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn waha_bot.wsgi:application --bind 0.0.0.0:8000
