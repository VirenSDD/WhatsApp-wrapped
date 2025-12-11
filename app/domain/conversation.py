from __future__ import annotations

from collections import Counter
from dataclasses import field
from datetime import datetime
from typing import Dict

from pydantic.dataclasses import dataclass

from app.domain.participant import MessageKind, Participant


@dataclass
class Conversation:
    chat_name: str
    participants: Dict[str, Participant] = field(default_factory=dict)
    year_counts: Counter = field(default_factory=Counter)
    text_messages: list[str] = field(default_factory=list)
    export_format: str = ""
    total_messages: int = 0

    def get_participant(self, name: str) -> Participant:
        if name not in self.participants:
            self.participants[name] = Participant(name=name)
        return self.participants[name]

    def record_event(self, sender: str, timestamp: datetime, text: str, kind: MessageKind) -> None:
        stats = self.get_participant(sender)
        stats.message_count += 1
        self.total_messages += 1
        self.year_counts[timestamp.year] += 1

        if kind == MessageKind.TEXT:
            stats.record_text(text)
            if text:
                self.text_messages.append(text)
        else:
            stats.record_kind(kind)
