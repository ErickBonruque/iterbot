"""Envio semanal em massa com proteção contra bloqueio do WhatsApp.

- Só recebe quem aceitou a privacidade, não pediu "parar" e tem curso escolhido.
- Intervalo aleatório entre mensagens (nunca depois da última).
- Limite por execução; o restante sai nas execuções seguintes, sem repetir
  quem já recebeu neste ciclo (`weekly_review_sent_at`).
- Envio que o WAHA recusa (send_message → False) é erro e não marca o aluno.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.bot.models import ConversationState
from apps.courses.models import Course
from apps.jobs.services import send_weekly_reviews
from apps.users.models import UserProfile


class _RecordingSender:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.sent_to: list[str] = []

    def send_message(self, chat_id: str, text: str) -> bool:
        self.sent_to.append(chat_id)
        return self.ok


def _student(n: int, course: Course | None, **profile_fields) -> UserProfile:
    fields = {"privacy_consent_at": timezone.now(), **profile_fields}
    user = UserProfile.objects.create(phone_number=f"55459000000{n:02d}@c.us", **fields)
    state, _ = ConversationState.objects.get_or_create(user=user)
    state.selected_course = course
    state.save()
    return user


@patch("apps.jobs.services.build_weekly_local_review", return_value=[])
class SendWeeklyReviewsTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(name="Ciência da Computação", is_active=True)
        self.sleeps: list[float] = []

    def _run(self, sender, **kwargs):
        params = {
            "message_sender": sender,
            "min_interval_seconds": 8,
            "max_interval_seconds": 20,
            "max_per_run": 40,
            "sleep": self.sleeps.append,
        }
        params.update(kwargs)
        return send_weekly_reviews(**params)

    def test_only_consented_not_opted_out_users_with_course_receive(self, _review):
        ok = _student(1, self.course)
        _student(2, self.course, privacy_consent_at=None)
        _student(3, self.course, weekly_review_opt_out=True)
        _student(4, None)
        sender = _RecordingSender()

        stats = self._run(sender)

        self.assertEqual(sender.sent_to, [ok.phone_number])
        self.assertEqual(stats["empty_notice"], 1)
        self.assertEqual(stats["remaining"], 0)

    def test_max_per_run_splits_the_audience_across_runs_without_repeats(self, _review):
        users = [_student(i, self.course) for i in range(5)]
        sender = _RecordingSender()

        first = self._run(sender, max_per_run=2)
        second = self._run(sender, max_per_run=2)
        third = self._run(sender, max_per_run=2)

        self.assertEqual((first["remaining"], second["remaining"], third["remaining"]), (3, 1, 0))
        self.assertCountEqual(sender.sent_to, [u.phone_number for u in users])

    def test_user_served_this_cycle_is_not_sent_again(self, _review):
        _student(1, self.course, weekly_review_sent_at=timezone.now() - timedelta(days=1))
        sender = _RecordingSender()

        self._run(sender)

        self.assertEqual(sender.sent_to, [])

    def test_user_served_last_week_is_sent_again(self, _review):
        _student(1, self.course, weekly_review_sent_at=timezone.now() - timedelta(days=7))
        sender = _RecordingSender()

        self._run(sender)

        self.assertEqual(len(sender.sent_to), 1)

    def test_random_pause_between_messages_but_not_after_the_last(self, _review):
        for i in range(3):
            _student(i, self.course)

        self._run(_RecordingSender())

        self.assertEqual(len(self.sleeps), 2)
        for pause in self.sleeps:
            self.assertGreaterEqual(pause, 8)
            self.assertLessEqual(pause, 20)

    def test_send_refused_by_waha_is_an_error_and_user_stays_pending(self, _review):
        user = _student(1, self.course)

        stats = self._run(_RecordingSender(ok=False))

        user.refresh_from_db()
        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["empty_notice"], 0)
        self.assertIsNone(user.weekly_review_sent_at)
        self.assertEqual(stats["remaining"], 1)


class WeeklyReviewTaskTests(TestCase):
    @override_settings(
        WEEKLY_REVIEW_MIN_INTERVAL_SECONDS=8,
        WEEKLY_REVIEW_MAX_INTERVAL_SECONDS=20,
        WEEKLY_REVIEW_MAX_PER_RUN=40,
        WEEKLY_REVIEW_BATCH_PAUSE_SECONDS=1800,
    )
    @patch("apps.jobs.tasks.send_weekly_reviews")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration.get_active", return_value=MagicMock())
    def test_task_uses_settings_and_schedules_next_batch_when_audience_remains(
        self, _active, _waha, mock_send
    ):
        from apps.jobs.tasks import send_weekly_job_review

        mock_send.return_value = {"sent": 40, "empty_notice": 0, "errors": 0, "remaining": 12}
        with patch.object(send_weekly_job_review, "apply_async") as mock_next:
            send_weekly_job_review()

        kwargs = mock_send.call_args.kwargs
        self.assertEqual(
            (kwargs["min_interval_seconds"], kwargs["max_interval_seconds"], kwargs["max_per_run"]),
            (8, 20, 40),
        )
        mock_next.assert_called_once_with(countdown=1800)

    @patch("apps.jobs.tasks.send_weekly_reviews")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration.get_active", return_value=MagicMock())
    def test_task_stops_when_nothing_remains(self, _active, _waha, mock_send):
        from apps.jobs.tasks import send_weekly_job_review

        mock_send.return_value = {"sent": 3, "empty_notice": 0, "errors": 0, "remaining": 0}
        with patch.object(send_weekly_job_review, "apply_async") as mock_next:
            send_weekly_job_review()

        mock_next.assert_not_called()

    @patch("apps.jobs.tasks.send_weekly_reviews")
    @patch("infra.waha.client.WahaClient")
    @patch("apps.bot.models.BotConfiguration.get_active", return_value=MagicMock())
    def test_task_does_not_loop_when_a_batch_makes_no_progress(self, _active, _waha, mock_send):
        """WAHA fora do ar: tudo falha — não reagenda em laço (próxima segunda tenta)."""
        from apps.jobs.tasks import send_weekly_job_review

        mock_send.return_value = {"sent": 0, "empty_notice": 0, "errors": 40, "remaining": 52}
        with patch.object(send_weekly_job_review, "apply_async") as mock_next:
            send_weekly_job_review()

        mock_next.assert_not_called()
