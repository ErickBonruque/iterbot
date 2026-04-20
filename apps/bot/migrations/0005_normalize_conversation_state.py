from django.db import migrations

from apps.bot.state_machine import normalized_flow_state


def normalize_conversation_states(apps, schema_editor):
    ConversationState = apps.get_model("bot", "ConversationState")

    for state in ConversationState.objects.all().only("id", "current_action"):
        normalized = normalized_flow_state(state.current_action).persisted
        if state.current_action != normalized:
            state.current_action = normalized
            state.save(update_fields=["current_action", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("bot", "0004_migrate_conversation_data"),
    ]

    operations = [
        migrations.RunPython(normalize_conversation_states, migrations.RunPython.noop),
    ]
