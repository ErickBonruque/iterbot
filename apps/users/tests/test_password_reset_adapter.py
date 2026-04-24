"""Testes do UTFPRAccountAdapter roteando todos e-mails allauth via provider transacional."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.users.adapters import UTFPRAccountAdapter
from infra.email.idempotency import build_email_idempotency_key


class UTFPRAccountAdapterSendMailTests(SimpleTestCase):
    def _stub_user(self, pk: int = 42):
        return SimpleNamespace(pk=pk, email="aluno@utfpr.edu.br")

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
                return_value={"status": "sent", "provider": "brevo"},
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
            event_uid="aluno@utfpr.edu.br",
        )
        assert result == {"status": "sent", "provider": "brevo"}
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
            event_type="password_reset",
        )

    def test_signup_confirmation_mail_routes_through_shared_sender(self):
        adapter = UTFPRAccountAdapter()
        user = self._stub_user(pk=7)
        context = {"key": "confirm-key", "user": user}
        rendered_message = SimpleNamespace(subject="Signup", body="Signup body")

        with (
            patch(
                "apps.users.adapters.DefaultAccountAdapter.render_mail",
                return_value=rendered_message,
            ),
            patch(
                "apps.users.adapters.send_transactional_email",
                return_value={"status": "sent", "provider": "brevo"},
            ) as send_spy,
        ):
            adapter.send_mail(
                "account/email/email_confirmation_signup",
                "novo@alunos.utfpr.edu.br",
                context,
            )

        expected_key = build_email_idempotency_key(
            "email_confirmation_signup",
            recipient="novo@alunos.utfpr.edu.br",
            event_token="confirm-key",
            event_uid="7",
        )
        send_spy.assert_called_once_with(
            subject="Signup",
            message="Signup body",
            recipient_list=["novo@alunos.utfpr.edu.br"],
            idempotency_key=expected_key,
            event_type="email_confirmation",
        )

    def test_unknown_template_still_routes_via_transactional_sender(self):
        adapter = UTFPRAccountAdapter()
        context = {"user": self._stub_user(pk=1)}
        rendered_message = SimpleNamespace(subject="Generic", body="Generic body")

        with (
            patch(
                "apps.users.adapters.DefaultAccountAdapter.render_mail",
                return_value=rendered_message,
            ),
            patch(
                "apps.users.adapters.send_transactional_email",
                return_value={"status": "sent", "provider": "brevo"},
            ) as send_spy,
            patch(
                "apps.users.adapters.DefaultAccountAdapter.send_mail",
            ) as legacy_send_spy,
        ):
            adapter.send_mail(
                "account/email/desconhecido",
                "aluno@utfpr.edu.br",
                context,
            )

        send_spy.assert_called_once()
        legacy_send_spy.assert_not_called()
        call_kwargs = send_spy.call_args.kwargs
        assert call_kwargs["event_type"] == "allauth_generic"

    def test_provider_error_is_logged_and_returned(self):
        adapter = UTFPRAccountAdapter()
        context = {"key": "k", "uid": "u"}
        rendered_message = SimpleNamespace(subject="s", body="b")

        with (
            patch(
                "apps.users.adapters.DefaultAccountAdapter.render_mail",
                return_value=rendered_message,
            ),
            patch(
                "apps.users.adapters.send_transactional_email",
                return_value={"status": "error", "provider": "brevo", "error_code": "http_401"},
            ),
            patch("apps.users.adapters.logger.error") as error_spy,
        ):
            result = adapter.send_mail(
                "account/email/password_reset_key",
                "aluno@utfpr.edu.br",
                context,
            )

        assert result["status"] == "error"
        error_spy.assert_called_once()
        error_kwargs = error_spy.call_args.kwargs
        assert error_kwargs["template_prefix"] == "account/email/password_reset_key"
        assert error_kwargs["error_code"] == "http_401"
