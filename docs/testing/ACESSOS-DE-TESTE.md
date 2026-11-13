# Acessos de teste (admin só leitura + alunos fictícios)

Para rodadas de teste com pessoas de fora da equipe. Tudo roda **no host gosh**
(campus ou VPN), dentro de `~/iterbot`. Antes, defina o atalho que o `deploy.sh` usa:

```bash
dc() { docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  $( [ -f docker-compose.resources.yml ] && echo -f docker-compose.resources.yml ) "$@"; }
```

## 1. Conta do admin somente leitura

Quem recebe esta conta **vê** o painel (empresas, vagas, cursos, perfis de aluno,
candidaturas, métricas, status do bot) e **não consegue alterar nada**: não salva
formulário, não aprova/bloqueia empresa, não aprova vaga, não dispara coleta, não
testa busca e não vê o QR nem os botões do WhatsApp. Também não vê o histórico de
mensagens com o bot (*Interações*, *Estados de conversa*) nem os usuários do Django.

```bash
# 1) Conta no Django (gera a senha e mostra uma vez — anote)
dc exec backend python manage.py criar_conta_leitura leitura

# 2) A mesma conta no BasicAuth do /admin (pede a senha: use a gerada acima)
echo "leitura:$(openssl passwd -apr1)" >> secrets/users/admin-users.txt

# 3) O Traefik só relê o arquivo de usuários ao recarregar (fica ~5 s fora do ar)
dc restart traefik
```

Quem entra digita usuário e senha **duas vezes**: primeiro na janela do navegador
(BasicAuth), depois na tela de login do admin. É a mesma dupla nas duas.

- Senha perdida: `criar_conta_leitura leitura --nova-senha` e refazer o passo 2
  (apague antes a linha antiga `leitura:` de `secrets/users/admin-users.txt`).
- Rodar o comando de novo sem `--nova-senha` só ressincroniza as permissões do
  grupo "Somente leitura" (útil depois de criar modelos novos).
- Mais de uma pessoa? Prefira uma conta por pessoa (`leitura-fulano`): o log do
  admin registra quem fez o quê.

## 2. E-mails de aluno fictícios

O cadastro do aluno no bot exige clicar num link mandado ao e-mail @alunos. Os
e-mails listados em `STUDENT_TEST_EMAILS` pulam esse passo: o cadastro é aceito na
hora e **nenhum e-mail é enviado**. O bot responde "Conta de teste" para deixar
claro que um aluno de verdade receberia o link.

No `.env` do host:

```bash
STUDENT_TEST_EMAILS=iterbot.teste01@alunos.utfpr.edu.br,iterbot.teste02@alunos.utfpr.edu.br,iterbot.teste03@alunos.utfpr.edu.br,iterbot.teste04@alunos.utfpr.edu.br,iterbot.teste05@alunos.utfpr.edu.br
```

```bash
dc up -d backend celery_worker   # recria com o .env novo (restart não relê o env_file)
```

- **Um e-mail por testador**: o e-mail fica preso ao número de WhatsApp que o
  usou. Se outra pessoa digitar o mesmo, o bot responde que ele já está vinculado
  a outro número e pede outro.
- O RA pode ser qualquer texto com 5+ caracteres (ex.: `a0000001`).
- Cada número passa primeiro pelo texto de privacidade (LGPD), como um aluno real.

## 3. Depois do teste

```bash
# Desliga os e-mails fictícios
sed -i 's/^STUDENT_TEST_EMAILS=.*/STUDENT_TEST_EMAILS=/' .env
dc up -d backend celery_worker

# Apaga os perfis dos testadores (leva junto conversas e candidaturas deles)
dc exec backend python manage.py shell -c \
  "from apps.users.models import UserProfile; print(UserProfile.objects.filter(email__startswith='iterbot.teste').delete())"

# Desativa a conta de leitura e tira o BasicAuth dela
dc exec backend python manage.py shell -c \
  "from django.contrib.auth.models import User; print(User.objects.filter(username='leitura').update(is_active=False))"
sed -i '/^leitura:/d' secrets/users/admin-users.txt
dc restart traefik
```
