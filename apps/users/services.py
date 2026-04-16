import logging

from apps.users.models import UserProfile

logger = logging.getLogger(__name__)


class UTFPRAuthService:
    """
    Serviço para autenticação no portal da UTFPR.
    """

    def authenticate(self, ra, password):
        """
        Autentica o usuário no portal do aluno.
        Retorna True se sucesso, False caso contrário.
        """
        logger.info(f"Tentando autenticar RA: {ra}")

        # TODO: Implementar scraping real ou integração com API se houver
        # Por enquanto, retorna True para qualquer RA que não seja '000000'

        if ra == "000000":
            return False

        return True

    def link_user(self, phone_number, ra, password):
        """
        Vincula um RA a um número de telefone após autenticação bem sucedida.
        """
        if self.authenticate(ra, password):
            user, created = UserProfile.objects.update_or_create(
                phone_number=phone_number,
                defaults={
                    "ra": ra,
                    "utfpr_password": password,  # TODO: Encrypt this!
                    "is_authenticated_utfpr": True,
                },
            )
            return user
        return None

    def logout(self, phone_number):
        """
        Desvincula o usuário.
        """
        try:
            user = UserProfile.objects.get(phone_number=phone_number)
            user.is_authenticated_utfpr = False
            user.utfpr_password = None
            user.save()
            return True
        except UserProfile.DoesNotExist:
            return False
