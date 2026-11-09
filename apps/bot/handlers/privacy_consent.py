"""Consentimento de privacidade (LGPD) no primeiro contato com o bot."""

import hashlib
import unicodedata
from enum import Enum

import structlog
from django.conf import settings
from django.utils import timezone

from apps.bot.messages import BOT_MESSAGES
from apps.bot.models import ConversationState
from apps.bot.state_machine import (
    STATE_IDLE,
    STATE_PRIVACY_CONSENT,
    apply_state_transition,
    normalize_current_action,
)
from apps.users.models import UserProfile

from .base import BaseHandler

logger = structlog.get_logger(__name__)


class ConsentOutcome(Enum):
    ASKED = "asked"
    ACCEPTED = "accepted"
    DECLINED = "declined"


def _normalize(text: str) -> str:
    """Minúsculas, sem acento e sem pontuação nas pontas ("Não aceito." → "nao aceito")."""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return plain.strip(" .!?,;")


_ACCEPT = frozenset({"1", "1️⃣", "aceito", "aceitar", "sim", "concordo", "eu aceito"})
_DECLINE = frozenset({"2", "2️⃣", "nao aceito", "nao", "recuso", "nao concordo"})


class PrivacyConsentHandler(BaseHandler):
    """Mostra o texto de privacidade e registra o aceite (ou apaga quem recusa).

    O aceite só vale depois que o texto foi mostrado (estado `privacy_consent`),
    para ninguém "aceitar" digitando 1 sem ter lido. O texto é editável no admin
    (BotMessage `auth.privacy_consent`); o hash curto do texto exibido fica em
    `UserProfile.privacy_consent_version` como prova de qual versão foi aceita.
    """

    @staticmethod
    def needs_consent(user: UserProfile) -> bool:
        return user.privacy_consent_at is None

    def consent_text(self) -> str:
        return self.resolve_message(
            BOT_MESSAGES.auth.privacy_consent.key,
            BOT_MESSAGES.auth.privacy_consent.text,
            contact_email=settings.PRIVACY_CONTACT_EMAIL,
        )

    @staticmethod
    def text_version(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    def process(self, user: UserProfile, chat_id: str, text: str) -> ConsentOutcome:
        state, _ = ConversationState.objects.get_or_create(user=user)
        pending = normalize_current_action(state.current_action) == STATE_PRIVACY_CONSENT
        answer = _normalize(text)

        if pending and answer in _ACCEPT:
            consent_text = self.consent_text()
            user.privacy_consent_at = timezone.now()
            user.privacy_consent_version = self.text_version(consent_text)
            user.save(update_fields=["privacy_consent_at", "privacy_consent_version", "updated_at"])
            apply_state_transition(
                conversation_state=state, next_state=STATE_IDLE, clear_flow_data=True
            )
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.privacy_consent_accepted.key,
                    BOT_MESSAGES.auth.privacy_consent_accepted.text,
                ),
            )
            logger.info(
                "privacy_consent_accepted",
                user_id=user.id,
                version=user.privacy_consent_version,
            )
            return ConsentOutcome.ACCEPTED

        if pending and answer in _DECLINE:
            self.send_msg(
                user,
                chat_id,
                self.resolve_message(
                    BOT_MESSAGES.auth.privacy_consent_declined.key,
                    BOT_MESSAGES.auth.privacy_consent_declined.text,
                ),
            )
            user_id = user.id
            # CASCADE apaga conversa (ConversationState) e InteractionLog;
            # BotActionLog fica com user=NULL (só métricas, sem conteúdo).
            user.delete()
            logger.info("privacy_consent_declined_profile_deleted", user_id=user_id)
            return ConsentOutcome.DECLINED

        apply_state_transition(
            conversation_state=state, next_state=STATE_PRIVACY_CONSENT, clear_flow_data=True
        )
        self.send_msg(user, chat_id, self.consent_text())
        return ConsentOutcome.ASKED

    def handle(self, user: UserProfile, chat_id: str, text: str) -> bool:
        if not self.needs_consent(user):
            return False
        self.process(user, chat_id, text)
        return True
