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
    message_count: int
    characters: int
    longest_text: str
    voice_notes: int
    videos: int
    video_notes: int
    photos: int
    stickers: int

    @staticmethod
    def create(
        name: str,
        *,
        message_count: int = 0,
        characters: int = 0,
        longest_text: str = "",
        voice_notes: int = 0,
        videos: int = 0,
        video_notes: int = 0,
        photos: int = 0,
        stickers: int = 0,
    ) -> "Participant":
        return Participant(
            name=name,
            message_count=message_count,
            characters=characters,
            longest_text=longest_text,
            voice_notes=voice_notes,
            videos=videos,
            video_notes=video_notes,
            photos=photos,
            stickers=stickers,
        )
