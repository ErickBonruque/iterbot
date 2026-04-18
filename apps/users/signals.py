from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.users.models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Cria UserProfile automaticamente quando User é criado pelo django-allauth.
    """
    if created:
        UserProfile.objects.create(
            user=instance,
            email=instance.email,
            phone_number=f"web_{instance.id}",
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Sincroniza e-mail entre User e UserProfile se profile existir.
    """
    if hasattr(instance, "profile") and instance.profile.email != instance.email:
        instance.profile.email = instance.email
        instance.profile.save()


@receiver(post_save, sender=UserProfile)
def create_conversation_state(sender, instance, created, **kwargs):
    """Cria ConversationState automaticamente quando UserProfile é criado."""
    if created:
        from apps.bot.models import ConversationState

        ConversationState.objects.get_or_create(user=instance)
