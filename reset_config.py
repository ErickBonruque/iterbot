#!/usr/bin/env python
"""
Script para resetar a configuração do WAHA e forçar uso dos valores do .env
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'waha_bot.settings')
django.setup()

from apps.bot.models import BotConfiguration

# Deletar todas as configurações antigas
count = BotConfiguration.objects.all().delete()[0]
print(f"✅ {count} configuração(ões) antiga(s) deletada(s)")

# Criar nova configuração com valores do .env
config = BotConfiguration.defaults()
config.save()

print("\n✅ Nova configuração criada com valores do .env:")
print(f"   WAHA URL: {config.waha_url}")
print(f"   Dashboard Username: {config.dashboard_username}")
print(f"   Dashboard Password: {config.dashboard_password}")
print(f"   Admin Username: {config.admin_username}")
print(f"\n🎯 Acesse: http://localhost:8000/dashboard/bot/configuration/")
