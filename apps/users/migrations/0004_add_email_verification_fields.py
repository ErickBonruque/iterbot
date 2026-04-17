import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_userprofile_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="email_verified",
            field=models.BooleanField(default=False, help_text="Indica se o email institucional foi confirmado via token"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="email_confirmation_token",
            field=models.CharField(
                blank=True,
                help_text="Token UUID para confirmação de email",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="email_confirmation_sent_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Data/hora do último envio de email de confirmação",
                null=True,
            ),
        ),
    ]
