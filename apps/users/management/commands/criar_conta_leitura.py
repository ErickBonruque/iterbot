"""Cria (ou atualiza) uma conta do admin que só consegue ver, sem alterar nada.

Uso no host:
    docker compose exec backend python manage.py criar_conta_leitura <usuario>
    docker compose exec backend python manage.py criar_conta_leitura <usuario> --nova-senha

A conta entra no grupo "Somente leitura", que recebe só as permissões ``view_*``
dos apps do IterBot — menos o histórico de conversas com o bot (LGPD) e os
usuários do Django. A senha é gerada aqui e mostrada uma única vez.
"""

import secrets

from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import UserProfile

GRUPO = "Somente leitura"
APPS = ("users", "courses", "jobs", "bot", "companies", "core")
# Conteúdo das mensagens trocadas com o bot fica só para quem opera o sistema.
MODELOS_FORA = {("bot", "interactionlog"), ("bot", "conversationstate")}


def permissoes_de_leitura():
    perms = Permission.objects.select_related("content_type").filter(
        content_type__app_label__in=APPS, codename__startswith="view_"
    )
    return [
        p for p in perms if (p.content_type.app_label, p.content_type.model) not in MODELOS_FORA
    ]


class Command(BaseCommand):
    help = "Cria/atualiza uma conta do admin somente leitura (senha gerada e exibida uma vez)."

    def add_arguments(self, parser):
        parser.add_argument("usuario")
        parser.add_argument("--email", default="")
        parser.add_argument(
            "--nova-senha",
            action="store_true",
            help="Gera outra senha para uma conta que já existe.",
        )

    @transaction.atomic
    def handle(self, *args, usuario, email, nova_senha, **options):
        grupo, _ = Group.objects.get_or_create(name=GRUPO)
        grupo.permissions.set(permissoes_de_leitura())

        user = User.objects.filter(username=usuario).first()
        if user is not None and user.is_superuser:
            raise CommandError(
                f"'{usuario}' é superusuário — escolha outro nome para a conta de leitura."
            )

        criada = user is None
        if criada:
            # E-mail interno por padrão: o signal de User copia o e-mail para um
            # UserProfile, onde ele é único — em branco colidiria com outro vazio.
            user = User(username=usuario, email=email or f"{usuario}@iterbot.local")
        elif email:
            user.email = email
        user.is_staff = True
        user.is_superuser = False
        user.is_active = True

        senha = None
        if criada or nova_senha:
            senha = secrets.token_urlsafe(12)
            user.set_password(senha)
        user.save()
        # O signal cria um perfil "web_N" para todo User; conta de leitura não é
        # aluno e não pode inflar o total de alunos do painel.
        UserProfile.objects.filter(user=user).delete()

        # Só o grupo dá permissão: nada de permissão avulsa ou outro grupo.
        user.user_permissions.clear()
        user.groups.set([grupo])

        acao = "criada" if criada else "atualizada"
        self.stdout.write(self.style.SUCCESS(f"Conta de leitura '{usuario}' {acao}."))
        if senha:
            self.stdout.write(f"Senha (anote agora, não será mostrada de novo): {senha}")
        else:
            self.stdout.write("Senha mantida (use --nova-senha para gerar outra).")
