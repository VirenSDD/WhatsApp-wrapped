#!/usr/bin/env python3
"""Summarize a WhatsApp style chat export."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

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

STOPWORDS = {
    # Spanish
    "de",
    "la",
    "que",
    "el",
    "en",
    "y",
    "a",
    "los",
    "del",
    "se",
    "las",
    "por",
    "un",
    "para",
    "con",
    "no",
    "una",
    "su",
    "al",
    "lo",
    "como",
    "m\u00e1s",
    "pero",
    "sus",
    "le",
    "ya",
    "o",
    "este",
    "s\u00ed",
    "porque",
    "esta",
    "entre",
    "cuando",
    "muy",
    "sin",
    "sobre",
    "tamb\u00e9n",
    "me",
    "hasta",
    "hay",
    "donde",
    "quien",
    "desde",
    "todo",
    "nos",
    "durante",
    "todos",
    "uno",
    "les",
    "ni",
    "contra",
    "otros",
    "ese",
    "eso",
    "ante",
    "ellos",
    "e",
    "esto",
    "m\u00ed",
    "antes",
    "algunos",
    "qu\u00e9",
    "unos",
    "yo",
    "otro",
    "otras",
    "otra",
    "\u00e9l",
    "tanto",
    "esa",
    "estos",
    "mucho",
    "quienes",
    "nada",
    "muchos",
    "cual",
    "poco",
    "ella",
    "estar",
    "estas",
    "algunas",
    "algo",
    "nosotros",
    "mi",
    "mis",
    "t\u00fa",
    "te",
    "ti",
    "tu",
    "tus",
    "ellas",
    "nosotras",
    "vosotros",
    "vosotras",
    "os",
    "m\u00edo",
    "m\u00eda",
    "m\u00edos",
    "m\u00edas",
    "tuyo",
    "tuya",
    "tuyos",
    "tuyas",
    "suyo",
    "suya",
    "suyos",
    "suyas",
    "nuestro",
    "nuestra",
    "nuestros",
    "nuestras",
    "vuestro",
    "vuestra",
    "vuestros",
    "vuestras",
    "esos",
    "esas",
    "estoy",
    "est\u00e1s",
    "est\u00e1",
    "estamos",
    "est\u00e1is",
    "est\u00e1n",
    "est\u00e9",
    "est\u00e9s",
    "estemos",
    "est\u00e9n",
    "estar\u00e9",
    "estar\u00e1s",
    "estar\u00e1",
    "estaremos",
    "estar\u00e1n",
    "estar\u00eda",
    "estar\u00edas",
    "estar\u00edamos",
    "estar\u00edan",
    "fue",
    "fueron",
    "fui",
    "fuimos",
    "son",
    "es",
    "ser",
    "era",
    "puede",
    "puedo",
    # English
    "the",
    "and",
    "for",
    "that",
    "this",
    "are",
    "was",
    "were",
    "will",
    "with",
    "you",
    "your",
    "they",
    "them",
    "have",
    "has",
    "had",
    "from",
    "not",
    "but",
    "about",
    "their",
    "there",
    "can",
    "could",
    "would",
    "should",
    "it's",
    "its",
    "i'm",
    "i'll",
    "i've",
    "we",
    "our",
    "ours",
    "be",
    "is",
    "to",
    "in",
    "of",
    "on",
    "as",
    "it",
    "at",
    "by",
    "or",
    "if",
    "so",
    "do",
    "did",
    "does",
    "am",
    "an",
    "a",
}


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


def read_messages(path: Path) -> List[Dict[str, object]]:
    messages: List[Dict[str, object]] = []
    current = None
    last_timestamp: datetime | None = None

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            normalized = line.lstrip("\ufeff\u200e").strip("\ufeff")
            match = IOS_TIMESTAMP_RE.match(normalized)
            if not match:
                match = ANDROID_TIMESTAMP_RE.match(normalized)
            start_new_message = False
            timestamp: datetime | None = None
            rest: str | None = None

            if match:
                date_str, time_str, rest = match.groups()
                timestamp = parse_timestamp(date_str, time_str)
                if last_timestamp is None or timestamp >= last_timestamp:
                    start_new_message = True
                else:
                    # Older timestamps are likely forwarded chat fragments; keep them as text.
                    start_new_message = False

            if start_new_message:
                if current:
                    messages.append(current)
                if ":" in rest:
                    sender_part, message_part = rest.split(":", 1)
                    sender = sender_part.strip()
                    text = message_part.strip()
                else:
                    sender = "System"
                    text = rest.strip()
                current = {"datetime": timestamp, "sender": sender, "text": text}
                last_timestamp = timestamp
            else:
                if current is None:
                    continue
                addition = normalized.strip()
                if not addition:
                    continue
                if current["text"]:
                    current["text"] = f"{current['text']}\n{addition}"
                else:
                    current["text"] = addition

    if current:
        messages.append(current)

    return messages


def _contains_attachment_keyword(text: str, keyword: str) -> bool:
    upper = text.upper()
    return "<ATTACHED" in upper and keyword in upper


def detect_attachment_type(text: str) -> str | None:
    lowered = text.lower()
    if VOICE_ONCE_PLACEHOLDER in lowered:
        return "voice"
    if VIDEO_NOTE_PLACEHOLDER in lowered:
        return "video_note"
    if MEDIA_PLACEHOLDER in lowered:
        return "photo"
    match = FILE_ATTACHMENT_RE.search(text)
    if match:
        extension = match.group(2).lower()
        if extension == "opus":
            return "voice"
        if extension == "webp":
            return "sticker"
        if extension in {"jpg", "jpeg", "png", "gif"}:
            return "photo"
    return None


def is_voice_message(text: str) -> bool:
    lowered = text.lower()
    if "audio omit" in lowered or "nota de voz omit" in lowered:
        return True
    return detect_attachment_type(text) == "voice"


def is_photo(text: str) -> bool:
    lowered = text.lower()
    if "image omit" in lowered or "imagen omit" in lowered or "foto omit" in lowered:
        return True
    attachment = detect_attachment_type(text)
    if attachment == "photo":
        return True
    return _contains_attachment_keyword(text, "PHOTO")


def is_sticker(text: str) -> bool:
    lowered = text.lower()
    if "sticker omit" in lowered:
        return True
    if detect_attachment_type(text) == "sticker":
        return True
    return _contains_attachment_keyword(text, "STICKER")


def tokenize(text: str) -> Iterable[str]:
    cleaned = re.findall(r"[A-Za-z\u00C0-\u017F]+", text.lower())
    for word in cleaned:
        if word in STOPWORDS:
            continue
        if len(word) <= 2:
            continue
        yield word


def summarize(messages: List[Dict[str, object]], top_n: int) -> Dict[str, object]:
    totals_by_year = Counter()
    totals_by_person = Counter()
    voice_by_person = Counter()
    video_note_by_person = Counter()
    photos_by_person = Counter()
    stickers_by_person = Counter()
    word_counter = Counter()

    total_voice = 0
    total_video_notes = 0
    total_photos = 0
    total_stickers = 0

    for msg in messages:
        sender = str(msg["sender"])
        text = str(msg["text"])
        timestamp: datetime = msg["datetime"]  # type: ignore[assignment]

        totals_by_person[sender] += 1
        totals_by_year[timestamp.year] += 1

        attachment_type = detect_attachment_type(text)

        if is_voice_message(text):
            total_voice += 1
            voice_by_person[sender] += 1
            continue
        if attachment_type == "video_note":
            total_video_notes += 1
            video_note_by_person[sender] += 1
            continue
        if is_photo(text):
            total_photos += 1
            photos_by_person[sender] += 1
            continue
        if is_sticker(text):
            total_stickers += 1
            stickers_by_person[sender] += 1
            continue

        word_counter.update(tokenize(text))

    return {
        "total_messages": len(messages),
        "messages_by_year": totals_by_year,
        "messages_by_person": totals_by_person,
        "voice_total": total_voice,
        "voice_by_person": voice_by_person,
        "video_note_total": total_video_notes,
        "video_note_by_person": video_note_by_person,
        "photo_total": total_photos,
        "photo_by_person": photos_by_person,
        "sticker_total": total_stickers,
        "sticker_by_person": stickers_by_person,
        "top_words": word_counter.most_common(top_n),
    }


def print_counter(title: str, counter: Counter, sort_by_value: bool = True) -> None:
    print(title)
    if not counter:
        print("  (none)")
        return
    if sort_by_value:
        iterable = sorted(counter.items(), key=lambda kv: (kv[1], kv[0]))
    else:
        iterable = sorted(counter.items(), key=lambda kv: kv[0])
    for key, value in iterable:
        print(f"  {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize chat activity.")
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=Path("_chat.txt"),
        help="Path to the _chat.txt export (default: ./_chat.txt)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many of the most frequent words to display (default: 20)",
    )
    args = parser.parse_args()

    messages = read_messages(args.file)
    if not messages:
        raise SystemExit(f"No messages found in {args.file}")

    stats = summarize(messages, args.top)

    print(f"Total messages: {stats['total_messages']}")
    print_counter("Messages by year:", stats["messages_by_year"], sort_by_value=False)
    print_counter("Messages by person:", stats["messages_by_person"])

    print(f"\nVoice notes: {stats['voice_total']}")
    print_counter("Voice notes by person:", stats["voice_by_person"])

    print(f"\nVideo notes: {stats['video_note_total']}")
    print_counter("Video notes by person:", stats["video_note_by_person"])

    print(f"\nPhotos: {stats['photo_total']}")
    print_counter("Photos by person:", stats["photo_by_person"])

    print(f"\nStickers: {stats['sticker_total']}")
    print_counter("Stickers by person:", stats["sticker_by_person"])

    print("\nMost frequent words:")
    for word, count in stats["top_words"]:
        print(f"  {word}: {count}")


if __name__ == "__main__":
    main()
