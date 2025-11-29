# Secrets Directory

Este diretório contém os arquivos de segredos usados pelo Docker Compose.

## Configuração

Para configurar os segredos, copie os arquivos `.example` e remova a extensão `.example`:

```bash
cp django_secret_key.txt.example django_secret_key.txt
cp postgres_password.txt.example postgres_password.txt
cp waha_api_key.txt.example waha_api_key.txt
cp waha_dashboard_password.txt.example waha_dashboard_password.txt
cp waha_swagger_password.txt.example waha_swagger_password.txt
```

Em seguida, edite cada arquivo e substitua os valores de exemplo por valores reais e seguros.

## Geração de Secrets

Para gerar valores seguros, você pode usar:

```bash
# Django Secret Key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > django_secret_key.txt

# Senhas aleatórias
openssl rand -base64 32 > postgres_password.txt
openssl rand -base64 32 > waha_api_key.txt
openssl rand -base64 32 > waha_dashboard_password.txt
openssl rand -base64 32 > waha_swagger_password.txt
```

## Segurança

⚠️ **IMPORTANTE**: Nunca commite os arquivos `.txt` (sem `.example`) no Git. Eles contêm informações sensíveis e devem ser mantidos em segredo.

Os arquivos `.txt` já estão no `.gitignore` deste diretório.
