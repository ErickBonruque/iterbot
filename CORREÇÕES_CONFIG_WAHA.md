# ✅ Correções na Página de Configuração WAHA

## Problemas Corrigidos

### 1. ✅ URL do WAHA agora usa http://localhost:3000
**Antes:** `http://waha:3000` (URL interna do Docker)  
**Depois:** `http://localhost:3000` (URL acessível do navegador)

**Arquivo alterado:** `.env`
```bash
WAHA_URL=http://localhost:3000  # Sem barra final
```

---

### 2. ✅ Senha do Dashboard agora funciona corretamente
**Problema:** Os valores padrão hardcoded no modelo estavam errados (`password` em vez de `waha_strong_password_123!`)

**Solução:** 
- Modelo `BotConfiguration` agora usa `blank=True` e delega valores padrão para o método `defaults()`
- O método `defaults()` lê os valores do arquivo `.env`
- Template atualizado para não usar defaults hardcoded

**Arquivos alterados:**
- `apps/bot/models.py` - Campos agora blank=True
- `apps/dashboard/templates/dashboard/bot_configuration.html` - Removidos defaults hardcoded
- Criada migração: `0005_alter_botconfiguration_admin_password_and_more.py`

---

## Credenciais Atuais (Confirmadas)

### Dashboard Web
```
URL: http://localhost:8000/dashboard/
Usuário: admin
Senha: waha_strong_password_123!
```

### Django Admin
```
URL: http://localhost:8000/admin/
Usuário: admin
Senha: waha_strong_password_123!
```

### WAHA Dashboard
```
URL: http://localhost:3000/dashboard/
Link clicável em: http://localhost:8000/dashboard/bot/configuration/
```

---

## Como Verificar

1. **Acesse a página de configuração:**
   ```
   http://localhost:8000/dashboard/bot/configuration/
   ```

2. **Verifique os valores exibidos:**
   - WAHA URL: `http://localhost:3000` ✅
   - Dashboard Username: `admin` ✅
   - Dashboard Password: `waha_strong_password_123!` ✅

3. **Clique no link azul da WAHA URL:**
   - Deve abrir: `http://localhost:3000/dashboard/` em nova aba ✅

---

## Script de Reset (se necessário)

Se precisar resetar a configuração para os valores do .env:

```bash
docker-compose exec backend python reset_config.py
```

Ou manualmente:
```bash
docker-compose exec backend python manage.py shell
```
```python
from apps.bot.models import BotConfiguration
BotConfiguration.objects.all().delete()
config = BotConfiguration.defaults()
config.save()
print(f"URL: {config.waha_url}")
print(f"Password: {config.dashboard_password}")
```

---

## Arquivos Criados/Modificados

### Modificados:
1. `.env` - URL corrigida (sem barra final)
2. `apps/bot/models.py` - Campos blank=True
3. `apps/dashboard/templates/dashboard/bot_configuration.html` - Defaults removidos
4. `CREDENCIAIS.md` - Documentação atualizada

### Criados:
1. `reset_config.py` - Script para resetar configuração
2. `apps/bot/migrations/0005_*.py` - Migração do modelo
3. `CORREÇÕES_CONFIG_WAHA.md` - Este arquivo

---

## Teste Completo

### Passo 1: Verificar configuração atual
```bash
docker-compose exec backend python -c "
from apps.bot.models import BotConfiguration
config = BotConfiguration.objects.order_by('-created_at').first() or BotConfiguration.defaults()
print(f'WAHA URL: {config.waha_url}')
print(f'Dashboard Password: {config.dashboard_password}')
"
```

**Saída esperada:**
```
WAHA URL: http://localhost:3000
Dashboard Password: waha_strong_password_123!
```

### Passo 2: Acessar dashboard
1. Abra: http://localhost:8000/dashboard/
2. Login com: `admin` / `waha_strong_password_123!`
3. Vá para: Configuração WAHA
4. Verifique que todos os campos estão preenchidos corretamente

### Passo 3: Testar link do WAHA
1. Na página de Configuração WAHA
2. Clique no link azul da WAHA URL
3. Deve abrir http://localhost:3000/dashboard/ em nova aba

---

## Status Final

✅ **URL do WAHA:** Corrigida para `http://localhost:3000`  
✅ **Senha do Dashboard:** Funcionando com `waha_strong_password_123!`  
✅ **Link clicável:** Abre WAHA dashboard em nova aba  
✅ **Valores do .env:** Carregados corretamente  
✅ **Migrações:** Aplicadas  
✅ **Sistema:** Reiniciado com sucesso  

**Data:** 29/11/2025  
**Comando executado:** `make restart` ✅
