# Migração de dados: copia estado de conversa de UserProfile para ConversationState

from django.db import migrations


def copy_conversation_data(apps, schema_editor):
    UserProfile = apps.get_model("users", "UserProfile")
    ConversationState = apps.get_model("bot", "ConversationState")

    conversation_states = []
    for profile in UserProfile.objects.all():
        conversation_states.append(
            ConversationState(
                user_id=profile.pk,
                current_action=profile.current_action,
                selected_course_id=profile.selected_course_id,
                selected_term_id=profile.selected_term_id,
                flow_data=profile.flow_data or {},
            )
        )

    if conversation_states:
        ConversationState.objects.bulk_create(conversation_states, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("bot", "0003_add_conversationstate"),
        ("users", "0004_add_email_verification_fields"),
    ]

    operations = [
        migrations.RunPython(copy_conversation_data, migrations.RunPython.noop),
    ]