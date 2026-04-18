from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_add_email_verification_fields"),
        ("bot", "0004_migrate_conversation_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="current_action",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="flow_data",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="selected_course",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="selected_term",
        ),
    ]
