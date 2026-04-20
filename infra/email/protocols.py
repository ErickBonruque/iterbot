"""Contratos de provider para envio de email transacional."""

from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(slots=True)
class EmailSendResult:
    """Resultado padronizado para provedores de email."""

    status: str
    provider: str
    message_id: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


class EmailProvider(Protocol):
    """Contrato comum para providers de email transacional."""

    def send(
        self,
        *,
        subject: str,
        message: str,
        from_email: str,
        recipient_list: list[str],
    ) -> EmailSendResult:
        """Envia email transacional e retorna metadados padronizados."""
