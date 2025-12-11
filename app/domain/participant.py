from __future__ import annotations

from enum import Enum

from pydantic.dataclasses import dataclass


class MessageKind(Enum):
    TEXT = "text"
    VOICE = "voice"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"
    PHOTO = "photo"
    STICKER = "sticker"


@dataclass
class Participant:
    name: str
    message_count: int = 0
    characters: int = 0
    longest_text: str = ""
    voice_notes: int = 0
    videos: int = 0
    video_notes: int = 0
    photos: int = 0
    stickers: int = 0

    def record_text(self, text: str) -> None:
        length = len(text)
        self.characters += length
        if length > len(self.longest_text):
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
