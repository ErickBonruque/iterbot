from django.db import models


class TimeStampedModel(models.Model):
    """
    Uma classe abstrata base que fornece campos auto-atualizados
    created_at e updated_at.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
