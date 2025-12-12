from __future__ import annotations

from pathlib import Path

from app.domain.export_format import ExportFormat
from app.infrastructure.parser import ChatParser


def _write_chat(tmp_path: Path, filename: str, lines: list[str]) -> Path:
    path = tmp_path / filename
    # Add trailing newline so parser finalizes last message reliably
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_parse_android_chat(tmp_path: Path) -> None:
    path = _write_chat(
        tmp_path,
        "android_chat.txt",
        [
            "12/05/2024, 09:15 - Viren: Hola carlos carlos carlos",
            "12/05/2024, 09:16 - Carlos: <media omitted>",
            "12/05/2024, 09:17 - Viren: sticker omit ;)",
        ],
    )

    conversation = ChatParser().parse(path)

    assert conversation.export_format == ExportFormat.ANDROID
    assert conversation.year_counts[2024] == 3
    assert conversation.text_messages == ["Hola carlos carlos carlos"]

    viren_participant = conversation.participants["Viren"]
    assert viren_participant.message_count == 2
    assert viren_participant.characters == 25
    assert viren_participant.longest_text == "Hola carlos carlos carlos"
    assert viren_participant.stickers == 1

    carlos_participant = conversation.participants["Carlos"]
    assert carlos_participant.message_count == 1
    assert carlos_participant.photos == 1
    assert carlos_participant.characters == 0


def test_parse_ios_chat(tmp_path: Path) -> None:
    path = _write_chat(
        tmp_path,
        "ios_chat.txt",
        [
            "[05/12/2024, 09:15:00] Alice: Hola Bob",
            "[05/12/2024, 09:16:00] Bob: <video note omitted>",
            "[05/12/2024, 09:17:00] Alice: Long note start",
            "still going strong",
        ],
    )

    conversation = ChatParser().parse(path)

    assert conversation.export_format == ExportFormat.IOS
    assert conversation.year_counts[2024] == 3
    assert conversation.text_messages[1] == "Long note start\nstill going strong"

    alice = conversation.participants["Alice"]
    assert alice.message_count == 2
    assert alice.characters == len("Hola Bob") + len("Long note start\nstill going strong")
    assert alice.videos == 0

    bob = conversation.participants["Bob"]
    assert bob.videos == 1
    assert bob.video_notes == 0
