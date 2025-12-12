from __future__ import annotations

from collections import Counter
from typing import Dict

from pydantic.dataclasses import dataclass

from app.domain.domain_error import DomainError
from app.domain.export_format import ExportFormat
from app.domain.participant import Participant


@dataclass
class Conversation:
    chat_name: str
    participants: Dict[str, Participant]
    year_counts: Counter
    text_messages: list[str]
    export_format: ExportFormat

    @staticmethod
    def create(
        *,
        chat_name: str,
        participants: Dict[str, Participant],
        year_counts: Counter,
        text_messages: list[str],
        export_format: str | ExportFormat | None = None,
    ) -> Conversation:
        if not chat_name:
            raise DomainError("chat_name is required")
        if participants is None:
            raise DomainError("participants are required")
        if year_counts is None:
            raise DomainError("year_counts are required")
        if text_messages is None:
            raise DomainError("text_messages are required")

        format_value = Conversation._normalize_export_format(export_format)
        return Conversation(
            chat_name=chat_name,
            participants=participants,
            year_counts=year_counts,
            text_messages=text_messages,
            export_format=format_value,
        )

    @staticmethod
    def _normalize_export_format(value: str | ExportFormat | None) -> ExportFormat:
        if value in (None, "", False):
            raise DomainError("export_format is required")
        if isinstance(value, ExportFormat):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                raise DomainError("export_format is required")
            try:
                return ExportFormat(normalized)
            except ValueError as exc:  # pragma: no cover - data validation
                raise DomainError(f"Invalid export format: {value}") from exc
        raise DomainError(f"Unsupported export format type: {type(value)!r}")
