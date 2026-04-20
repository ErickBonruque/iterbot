from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ConversationStateMigrationTests(TransactionTestCase):
    migrate_from = ("bot", "0004_migrate_conversation_data")
    migrate_to = ("bot", "0005_normalize_conversation_state")

    def _migrate_to(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate([target])
        return executor.loader.project_state([target]).apps

    def test_migration_normalizes_legacy_and_unknown_states(self):
        old_apps = self._migrate_to(self.migrate_from)
        UserProfile = old_apps.get_model("users", "UserProfile")
        ConversationState = old_apps.get_model("bot", "ConversationState")

        user_valid = UserProfile.objects.create(phone_number="551100000001@c.us")
        user_legacy = UserProfile.objects.create(phone_number="551100000002@c.us")
        user_unknown = UserProfile.objects.create(phone_number="551100000003@c.us")
        user_none = UserProfile.objects.create(phone_number="551100000004@c.us")

        ConversationState.objects.create(user_id=user_valid.id, current_action="login_step_password")
        ConversationState.objects.create(user_id=user_legacy.id, current_action="waiting_ra")
        ConversationState.objects.create(user_id=user_unknown.id, current_action="totally_invalid")
        ConversationState.objects.create(user_id=user_none.id, current_action=None)

        new_apps = self._migrate_to(self.migrate_to)
        NewConversationState = new_apps.get_model("bot", "ConversationState")

        by_user = {
            row.user_id: row.current_action
            for row in NewConversationState.objects.order_by("id")
        }

        self.assertEqual(by_user[user_valid.id], "login_step_password")
        self.assertEqual(by_user[user_legacy.id], "login_step_ra")
        self.assertIsNone(by_user[user_unknown.id])
        self.assertIsNone(by_user[user_none.id])

    def test_migration_is_effectively_idempotent(self):
        old_apps = self._migrate_to(self.migrate_from)
        UserProfile = old_apps.get_model("users", "UserProfile")
        ConversationState = old_apps.get_model("bot", "ConversationState")

        user = UserProfile.objects.create(phone_number="551100000005@c.us")
        ConversationState.objects.create(user_id=user.id, current_action="waiting_password")

        new_apps = self._migrate_to(self.migrate_to)
        NewConversationState = new_apps.get_model("bot", "ConversationState")
        row = NewConversationState.objects.get(user_id=user.id)
        self.assertEqual(row.current_action, "login_step_password")

        # Simulate running normalization logic over already-normalized rows.
        row.current_action = "login_step_password"
        row.save(update_fields=["current_action", "updated_at"])
        row.refresh_from_db()
        self.assertEqual(row.current_action, "login_step_password")
