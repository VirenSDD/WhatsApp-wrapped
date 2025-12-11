from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from re import Match

from app.domain.models import Conversation, MessageKind

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


class ChatParser:
    def parse(self, path: Path, chat_name: Optional[str] = None) -> Conversation:
        conversation = Conversation(chat_name=chat_name or path.stem)
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
                            self._finalize_message(current, conversation)
                        if matched_format and not export_format:
                            export_format = matched_format
                            conversation.export_format = matched_format
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
            self._finalize_message(current, conversation)

        return conversation

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

    def _finalize_message(self, message_data: dict, conversation: Conversation) -> None:
        sender = message_data["sender"]
        text = message_data["text"]
        timestamp = message_data["timestamp"]
        format_hint = message_data.get("format") or conversation.export_format
        kind = self._classify_message(text, format_hint)
        conversation.record_event(sender, timestamp, text if kind == MessageKind.TEXT else "", kind)

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
