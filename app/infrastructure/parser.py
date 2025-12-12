from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from re import Match

from app.domain.conversation import Conversation
from app.domain.domain_error import DomainError
from app.domain.participant import MessageKind, Participant

IOS_TIMESTAMP_RE = re.compile(
    r"^\s*\[(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\]\s+(.*)"
)
ANDROID_TIMESTAMP_RE = re.compile(
    r"^\s*(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+-\s+(.*)"
)

MEDIA_PLACEHOLDER = "<media omitted>"
VIDEO_NOTE_PLACEHOLDER = "<video note omitted>"
VOICE_ONCE_PLACEHOLDER = "<view once voice message omitted>"
FILE_ATTACHMENT_RE = re.compile(r"([A-Za-z0-9_-]+)\.([A-Za-z0-9]+)\s+\(file attached\)", re.I)
ATTACHED_TAG_RE = re.compile(r"<attached:\s*[^>]+\.(\w+)>", re.I)
SYSTEM_TEXT_MARKERS = (
    "messages and calls are end-to-end encrypted",
    "created this group",
    "added you",
    "changed this group's icon",
    "changed this group's description",
    "changed the subject",
    "changed this group's subject",
    "joined using this group's invite link",
    "pinned a message",
)


def parse_timestamp(date_str: str, time_str: str) -> datetime:
    joined = f"{date_str} {time_str}"
    patterns = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
    ]
    for pattern in patterns:
        try:
            return datetime.strptime(joined, pattern)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {joined}")


@dataclass
class ParticipantTotals:
    message_count: int = 0
    characters: int = 0
    longest_text: str = ""
    voice_notes: int = 0
    videos: int = 0
    video_notes: int = 0
    photos: int = 0
    stickers: int = 0


class ChatParser:
    def parse(self, path: Path, chat_name: Optional[str] = None) -> Conversation:
        participant_totals: Dict[str, ParticipantTotals] = {}
        text_messages: list[str] = []
        year_counts: Counter[int] = Counter()
        current: Optional[dict] = None
        export_format: Optional[str] = None
        last_timestamp: Optional[datetime] = None

        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\n")
                normalized = line.lstrip("\ufeff\u200e").strip("\ufeff")
                match, matched_format = self._match_timestamp(normalized, export_format)

                if match:
                    start_new = self._should_start_new(
                        match, matched_format, export_format, last_timestamp
                    )
                    timestamp = parse_timestamp(*match.groups()[:2])
                    rest = match.group(3)
                    if start_new:
                        if current:
                            self._finalize_message(
                                current,
                                participant_totals,
                                year_counts,
                                text_messages,
                                export_format,
                            )
                        if matched_format and not export_format:
                            export_format = matched_format
                        if ":" not in rest:
                            current = None
                            last_timestamp = timestamp
                            continue
                        sender_part, message_part = rest.split(":", 1)
                        sender = sender_part.strip()
                        text = message_part.strip()
                        if self._is_system_text(text):
                            current = None
                            last_timestamp = timestamp
                            continue
                        current = {
                            "sender": sender,
                            "text": text,
                            "timestamp": timestamp,
                            "format": matched_format or export_format,
                        }
                        last_timestamp = timestamp
                        continue
                if current:
                    addition = normalized.strip()
                    if addition:
                        current["text"] = f"{current['text']}\n{addition}"

        if current:
            self._finalize_message(
                current, participant_totals, year_counts, text_messages, export_format
            )

        if not export_format:
            raise DomainError("Unable to determine export format from chat transcript")

        participants = {
            name: Participant.create(
                name,
                message_count=totals.message_count,
                characters=totals.characters,
                longest_text=totals.longest_text,
                voice_notes=totals.voice_notes,
                videos=totals.videos,
                video_notes=totals.video_notes,
                photos=totals.photos,
                stickers=totals.stickers,
            )
            for name, totals in participant_totals.items()
        }

        return Conversation.create(
            chat_name=chat_name or path.stem,
            participants=participants,
            year_counts=year_counts,
            text_messages=text_messages,
            export_format=export_format,
        )

    def _match_timestamp(
        self, line: str, export_format: Optional[str]
    ) -> Tuple[Optional[Match[str]], Optional[str]]:
        match: Optional[Match[str]] = None
        matched_format: Optional[str] = None
        if export_format in (None, "ios"):
            match = IOS_TIMESTAMP_RE.match(line)
            if match:
                matched_format = "ios"
        if match is None and export_format in (None, "android"):
            match = ANDROID_TIMESTAMP_RE.match(line)
            if match:
                matched_format = "android"
        return match, matched_format

    def _should_start_new(
        self,
        match: Match[str],
        matched_format: Optional[str],
        export_format: Optional[str],
        last_timestamp: Optional[datetime],
    ) -> bool:
        if matched_format is None:
            return False
        timestamp = parse_timestamp(*match.groups()[:2])
        if last_timestamp and timestamp < last_timestamp:
            return False
        if export_format and matched_format != export_format and matched_format == "ios":
            return False
        return True

    def _finalize_message(
        self,
        message_data: dict,
        participant_totals: Dict[str, ParticipantTotals],
        year_counts: Counter[int],
        text_messages: list[str],
        export_format: Optional[str],
    ) -> None:
        sender = message_data["sender"]
        text = message_data["text"]
        timestamp = message_data["timestamp"]
        format_hint = message_data.get("format") or export_format
        kind = self._classify_message(text, format_hint)
        stats = participant_totals.setdefault(sender, ParticipantTotals())
        stats.message_count += 1
        year_counts[timestamp.year] += 1

        if kind == MessageKind.TEXT:
            self._record_text(stats, text)
            text_messages.append(text)
        else:
            self._record_kind(stats, kind)

    def _classify_message(self, text: str, export_format: Optional[str]) -> MessageKind:
        lowered = text.lower()
        if "audio omit" in lowered or "nota de voz" in lowered:
            return MessageKind.VOICE
        if VOICE_ONCE_PLACEHOLDER in lowered:
            return MessageKind.VOICE
        if VIDEO_NOTE_PLACEHOLDER in lowered:
            return MessageKind.VIDEO if export_format == "ios" else MessageKind.VIDEO_NOTE
        if MEDIA_PLACEHOLDER in lowered:
            return MessageKind.PHOTO
        attachment = self._detect_attachment(text)
        if attachment == "voice":
            return MessageKind.VOICE
        if attachment == "video":
            return MessageKind.VIDEO
        if attachment == "video_note":
            return MessageKind.VIDEO_NOTE
        if attachment == "photo":
            return MessageKind.PHOTO
        if attachment == "sticker":
            return MessageKind.STICKER
        if "sticker omit" in lowered:
            return MessageKind.STICKER
        return MessageKind.TEXT

    def _detect_attachment(self, text: str) -> Optional[str]:
        match = ATTACHED_TAG_RE.search(text)
        if match:
            ext = match.group(1).lower()
            return self._ext_to_type(ext)
        match = FILE_ATTACHMENT_RE.search(text)
        if match:
            ext = match.group(2).lower()
            return self._ext_to_type(ext)
        return None

    @staticmethod
    def _ext_to_type(ext: str) -> Optional[str]:
        if ext == "opus":
            return "voice"
        if ext in {"mp4", "mov", "m4v"}:
            return "video"
        if ext in {"jpg", "jpeg", "png", "gif"}:
            return "photo"
        if ext in {"webp", "sticker"}:
            return "sticker"
        return None

    @staticmethod
    def _is_system_text(text: str) -> bool:
        normalized = text.strip("\u200e\u200f ").lower()
        return any(marker in normalized for marker in SYSTEM_TEXT_MARKERS)

    @staticmethod
    def _record_text(stats: ParticipantTotals, text: str) -> None:
        length = len(text)
        stats.characters += length
        if length > len(stats.longest_text):
            stats.longest_text = text

    @staticmethod
    def _record_kind(stats: ParticipantTotals, kind: MessageKind) -> None:
        if kind == MessageKind.VOICE:
            stats.voice_notes += 1
        elif kind == MessageKind.VIDEO:
            stats.videos += 1
        elif kind == MessageKind.VIDEO_NOTE:
            stats.video_notes += 1
        elif kind == MessageKind.PHOTO:
            stats.photos += 1
        elif kind == MessageKind.STICKER:
            stats.stickers += 1
