#!/usr/bin/env python3
"""Summarize a WhatsApp-style chat export using the new domain architecture."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Hashable, Mapping, TypeVar

from application.services import ConversationSummarizer, SummaryStats
from infrastructure.parser import ChatParser


K = TypeVar("K", bound=Hashable)


def print_counter(
    title: str,
    counter: Mapping[K, int],
    sort_by_value: bool = True,
) -> None:
    print(title)
    if not counter:
        print("  (none)")
        return
    items = list(counter.items())
    if sort_by_value:
        items.sort(key=lambda kv: (kv[1], str(kv[0])))
    else:
        items.sort(key=lambda kv: str(kv[0]))
    for key, value in items:
        print(f"  {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize chat activity.")
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=Path("_chat.txt"),
        help="Path to the chat export file (default: ./_chat.txt)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="How many of the most frequent words to display (default: 20)",
    )
    args = parser.parse_args()

    conversation = ChatParser().parse(args.file)
    stats: SummaryStats = ConversationSummarizer().summarize(conversation, top_n=args.top)

    print(f"Total messages: {stats['total_messages']}")
    print_counter("Messages by year:", stats["messages_by_year"], sort_by_value=False)
    print_counter("Messages by person:", stats["messages_by_person"])

    print(f"\nVoice notes: {stats['voice_total']}")
    print_counter("Voice notes by person:", stats["voice_by_person"])

    print(f"\nVideos: {stats['video_total']}")
    print_counter("Videos by person:", stats["video_by_person"])

    if stats["export_format"] != "ios":
        print(f"\nVideo notes: {stats['video_note_total']}")
        print_counter("Video notes by person:", stats["video_note_by_person"])

    print(f"\nPhotos: {stats['photo_total']}")
    print_counter("Photos by person:", stats["photo_by_person"])

    print(f"\nStickers: {stats['sticker_total']}")
    print_counter("Stickers by person:", stats["sticker_by_person"])

    print(f"\nCharacters sent: {stats['total_characters']}")
    print_counter("Characters by person:", stats["char_by_person"])

    print("\nLongest text length by person:")
    print_counter("Longest text by person:", stats["longest_text_by_person"])

    print("\nLongest text content by person:")
    content = stats["longest_text_content"]
    if not content:
        print("  (none)")
    else:
        for person in sorted(content):
            snippet = content[person].replace("\n", "\\n")
            length = stats["longest_text_by_person"].get(person, len(content[person]))
            print(f"  {person} [{length} chars]: {snippet}")

    print("\nMost frequent words:")
    for word, count in stats["top_words"]:
        print(f"  {word}: {count}")


if __name__ == "__main__":
    main()
