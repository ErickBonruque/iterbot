from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.users.adapters import UTFPRAccountAdapter
from infra.email.idempotency import build_email_idempotency_key


class PasswordResetAdapterTests(SimpleTestCase):
    def test_password_reset_mail_routes_through_shared_sender(self):
        adapter = UTFPRAccountAdapter()
        context = {"key": "reset-token-123", "uid": "uid-456"}
        rendered_message = SimpleNamespace(subject="Reset subject", body="Reset body")

        with (
            patch(
                "apps.users.adapters.DefaultAccountAdapter.render_mail",
                return_value=rendered_message,
            ) as render_mail_spy,
            patch(
                "apps.users.adapters.send_transactional_email",
                return_value={"status": "sent", "provider": "resend"},
            ) as send_spy,
        ):
            result = adapter.send_mail(
                "account/email/password_reset_key",
                "aluno@utfpr.edu.br",
                context,
            )

        expected_key = build_email_idempotency_key(
            "password_reset",
            recipient="aluno@utfpr.edu.br",
            event_token="reset-token-123",
            event_uid="uid-456",
        )
        assert result == {"status": "sent", "provider": "resend"}
        render_mail_spy.assert_called_once_with(
            "account/email/password_reset_key",
            "aluno@utfpr.edu.br",
            context,
        )
        send_spy.assert_called_once_with(
            subject="Reset subject",
            message="Reset body",
            recipient_list=["aluno@utfpr.edu.br"],
            idempotency_key=expected_key,
        )

    def test_non_reset_allauth_mail_keeps_existing_adapter_path(self):
        adapter = UTFPRAccountAdapter()
        context = {"anything": "kept"}

        with (
            patch(
                "apps.users.adapters.DefaultAccountAdapter.send_mail",
                return_value="legacy-path",
            ) as legacy_send_spy,
            patch(
                "apps.users.adapters.send_transactional_email",
            ) as send_spy,
        ):
            result = adapter.send_mail(
                "account/email/email_confirmation_signup",
                "aluno@utfpr.edu.br",
                context,
            )

        assert result == "legacy-path"
        legacy_send_spy.assert_called_once_with(
            "account/email/email_confirmation_signup",
            "aluno@utfpr.edu.br",
            context,
        )
        send_spy.assert_not_called()
