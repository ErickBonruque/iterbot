from django.db import migrations

# Lógica congelada no estado de quando esta migração foi escrita. Antes ela
# importava `apps.bot.state_machine`, e qualquer mudança nos estados de hoje
# (ex.: remoção do passo de senha, migração 0009) mudaria o que uma migração
# antiga faz num banco novo.
_CANONICAL_STATES = {
    "login_step_ra",
    "login_step_password",
    "login_step_email",
    "login_step_waiting_confirmation",
    "course_selection",
    "term_selection",
    "company_onboarding_selection",
    "company_login_email",
    "company_login_password",
    "local_jobs_list",
    "local_job_detail",
    "profile_periodo",
    "profile_skills",
    "profile_link",
    "confirm_application",
}
_LEGACY_ALIASES = {
    "waiting_ra": "login_step_ra",
    "waiting_password": "login_step_password",
    "waiting_email": "login_step_email",
    "waiting_confirmation": "login_step_waiting_confirmation",
    "menu": None,
    "start": None,
}


def _normalize(current_action):
    if not current_action:
        return None
    value = current_action.strip().lower()
    if value in _CANONICAL_STATES:
        return value
    return _LEGACY_ALIASES.get(value)


def normalize_conversation_states(apps, schema_editor):
    ConversationState = apps.get_model("bot", "ConversationState")

    for state in ConversationState.objects.all().only("id", "current_action"):
        normalized = _normalize(state.current_action)
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
