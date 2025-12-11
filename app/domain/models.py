from __future__ import annotations

from collections import Counter
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Dict

from pydantic.dataclasses import dataclass


class MessageKind(Enum):
    TEXT = "text"
    VOICE = "voice"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"
    PHOTO = "photo"
    STICKER = "sticker"


@dataclass
class ParticipantStats:
    name: str
    message_count: int = 0
    characters: int = 0
    longest_text_length: int = 0
    longest_text: str = ""
    voice_notes: int = 0
    videos: int = 0
    video_notes: int = 0
    photos: int = 0
    stickers: int = 0

    def record_text(self, text: str) -> None:
        length = len(text)
        self.characters += length
        if length > self.longest_text_length:
            self.longest_text_length = length
            self.longest_text = text

    def record_kind(self, kind: MessageKind) -> None:
        if kind == MessageKind.VOICE:
            self.voice_notes += 1
        elif kind == MessageKind.VIDEO:
            self.videos += 1
        elif kind == MessageKind.VIDEO_NOTE:
            self.video_notes += 1
        elif kind == MessageKind.PHOTO:
            self.photos += 1
        elif kind == MessageKind.STICKER:
            self.stickers += 1


@dataclass
class Conversation:
    chat_name: str
    participants: Dict[str, ParticipantStats] = field(default_factory=dict)
    year_counts: Counter = field(default_factory=Counter)
    text_messages: list[str] = field(default_factory=list)
    export_format: str = ""
    total_messages: int = 0

    def get_participant(self, name: str) -> ParticipantStats:
        if name not in self.participants:
            self.participants[name] = ParticipantStats(name=name)
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
