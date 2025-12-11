"""FastAPI + NiceGUI interface for chat summaries."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, TypedDict

from fastapi import FastAPI
from nicegui import events, ui

from application.services import ConversationSummarizer, SummaryStats
from infrastructure.parser import ChatParser
from wrapped_image import WrappedPayload, generate_wrapped_image

fastapi_app = FastAPI()
app = fastapi_app


class HighlightEntry(TypedDict):
    label: str
    emoji: str
    value: str


class YearRow(TypedDict):
    year: int
    messages: int


class ParticipantRow(TypedDict):
    name: str
    messages: int
    characters: int
    longest: int
    voice: int
    videos: int
    video_notes: int
    photos: int
    stickers: int


class SummaryContext(TypedDict):
    filename: str
    totals: List[Tuple[str, int]]
    year_rows: List[YearRow]
    people_rows: List[ParticipantRow]
    show_video_notes: bool
    top_words: List["WordRow"]
    highlights: List[HighlightEntry]
    share_payload: WrappedPayload


class WordRow(TypedDict):
    word: str
    count: int


def _top_person(counter: Dict[str, int]) -> Tuple[str, int]:
    if not counter:
        return ("N/A", 0)
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def build_summary_context(stats: SummaryStats, filename: str) -> SummaryContext:
    show_video_notes = stats["export_format"] != "ios" and stats["video_note_total"] > 0
    totals = [
        ("Messages", stats["total_messages"]),
        ("Voice notes", stats["voice_total"]),
        ("Videos", stats["video_total"]),
    ]
    if show_video_notes:
        totals.append(("Video notes", stats["video_note_total"]))
    totals.extend(
        [
            ("Photos", stats["photo_total"]),
            ("Stickers", stats["sticker_total"]),
            ("Characters", stats["total_characters"]),
        ]
    )

    year_rows: List[YearRow] = [
        {"year": year, "messages": count}
        for year, count in sorted(stats["messages_by_year"].items())
    ]

    people_rows: List[ParticipantRow] = []
    for person, message_count in stats["messages_by_person"].items():
        people_rows.append(
            {
                "name": person,
                "messages": message_count,
                "characters": stats["char_by_person"].get(person, 0),
                "longest": stats["longest_text_by_person"].get(person, 0),
                "voice": stats["voice_by_person"].get(person, 0),
                "videos": stats["video_by_person"].get(person, 0),
                "video_notes": stats["video_note_by_person"].get(person, 0),
                "photos": stats["photo_by_person"].get(person, 0),
                "stickers": stats["sticker_by_person"].get(person, 0),
            }
        )
    people_rows.sort(key=lambda row: (-row["messages"], row["name"]))

    top_words: List[WordRow] = [
        {"word": word, "count": count} for word, count in stats["top_words"]
    ]

    category_configs: Sequence[Tuple[str, Dict[str, int], str, str]] = [
        ("Yapper", stats["voice_by_person"], "🎙️", "voice notes"),
        ("Writer", stats["longest_text_by_person"], "✍️", "characters"),
        ("Sticky", stats["sticker_by_person"], "🧸", "stickers"),
        ("Photographer", stats["photo_by_person"], "📸", "photos"),
        ("Texter", stats["char_by_person"], "💬", "characters"),
    ]

    share_stats: List[HighlightEntry] = []
    for label, counter, emoji, unit in category_configs:
        person, value = _top_person(counter)
        if person == "N/A" or value == 0:
            share_value = "No data"
        elif label == "Writer":
            share_value = f"{person} · Longest message: {value} characters"
        elif label == "Texter":
            share_value = f"{person} · {value} characters typed"
        elif label == "Yapper":
            share_value = f"{person} · {value} voice notes"
        elif label == "Sticky":
            share_value = f"{person} · {value} stickers"
        elif label == "Photographer":
            share_value = f"{person} · {value} photos"
        else:
            share_value = f"{person} · {value} {unit}"
        share_stats.append({"label": label, "emoji": emoji, "value": share_value})

    def initials(name: str) -> str:
        parts = name.split()
        if not parts:
            return "NA"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    top_texter = _top_person(stats["char_by_person"])[0]
    summary_year = (
        max(stats["messages_by_year"]) if stats["messages_by_year"] else datetime.now().year
    )
    share_payload: WrappedPayload = {
        "chat_name": filename,
        "year": summary_year,
        "user_initials": initials(top_texter),
        "stats": share_stats,
    }

    return {
        "filename": filename,
        "totals": totals,
        "year_rows": year_rows,
        "people_rows": people_rows,
        "show_video_notes": show_video_notes,
        "top_words": top_words,
        "highlights": share_stats,
        "share_payload": share_payload,
    }


def render_summary(
    container: ui.column,
    summary: SummaryContext,
    download_btn: ui.button,
    summary_state: dict[str, Optional[WrappedPayload]],
) -> None:
    container.clear()
    summary_state["share"] = summary["share_payload"]
    download_btn.visible = True
    with container:
        with ui.card().classes("w-full"):
            ui.label(f"Totals · {summary['filename']}").classes("text-xl font-semibold")
            with ui.grid(columns=3).classes("gap-3 w-full"):
                for label, value in summary["totals"]:
                    with ui.card().classes("bg-blue-50 w-full"):
                        ui.label(label).classes("text-sm text-gray-600")
                        ui.label(f"{value:,}").classes("text-lg font-semibold")

        year_columns = [
            {"name": "year", "label": "Year", "field": "year", "sortable": True},
            {"name": "messages", "label": "Messages", "field": "messages", "sortable": True},
        ]
        with ui.card().classes("w-full"):
            ui.label("Messages by Year").classes("text-lg font-semibold mb-2")
            ui.table(
                columns=year_columns,
                rows=[dict(row) for row in summary["year_rows"]],
                row_key="year",
            ).props("flat")

        with ui.card().classes("w-full"):
            ui.label("Highlights").classes("text-lg font-semibold mb-2")
            for entry in summary["highlights"]:
                ui.label(f"{entry['emoji']} {entry['label']}: {entry['value']}").classes("text-md")

        people_columns = [
            {"name": "name", "label": "Person", "field": "name", "sortable": True},
            {"name": "messages", "label": "Messages", "field": "messages", "sortable": True},
            {"name": "characters", "label": "Characters", "field": "characters", "sortable": True},
            {"name": "longest", "label": "Longest text", "field": "longest", "sortable": True},
            {"name": "voice", "label": "Voice notes", "field": "voice", "sortable": True},
            {"name": "videos", "label": "Videos", "field": "videos", "sortable": True},
        ]
        if summary["show_video_notes"]:
            people_columns.append(
                {
                    "name": "video_notes",
                    "label": "Video notes",
                    "field": "video_notes",
                    "sortable": True,
                }
            )
        people_columns.extend(
            [
                {"name": "photos", "label": "Photos", "field": "photos", "sortable": True},
                {"name": "stickers", "label": "Stickers", "field": "stickers", "sortable": True},
            ]
        )

        with ui.card().classes("w-full"):
            ui.label("Messages by Person").classes("text-lg font-semibold mb-2")
            ui.table(
                columns=people_columns,
                rows=[dict(row) for row in summary["people_rows"]],
                row_key="name",
            ).props("flat wrap-cells")

        word_columns = [
            {"name": "word", "label": "Word", "field": "word"},
            {"name": "count", "label": "Count", "field": "count"},
        ]
        with ui.card().classes("w-full"):
            ui.label("Most Frequent Words").classes("text-lg font-semibold mb-2")
            ui.table(
                columns=word_columns,
                rows=[dict(row) for row in summary["top_words"]],
                row_key="word",
            ).props("flat")


@ui.page("/")
def main_page() -> None:
    ui.label("WhatsApp Chat Summary").classes("text-3xl font-semibold")
    ui.label(
        "Upload an exported chat text file from Android or iOS to view message, media, and character statistics."
    ).classes("text-gray-600 mb-4")

    summary_container = ui.column().classes("gap-4 w-full")
    summary_state: dict[str, Optional[WrappedPayload]] = {"share": None}

    format_select = ui.select(
        {
            "vertical": "Vertical (1080x1920)",
            "square": "Square (1080x1080)",
        },
        value="vertical",
        label="Image format",
    )

    async def download_card() -> None:
        if not summary_state["share"]:
            ui.notify("Generate a summary first", type="warning")
            return
        try:
            buffer = generate_wrapped_image(summary_state["share"], format_select.value)
        except Exception as exc:
            ui.notify(str(exc), type="warning", close_button="OK")
            return
        ui.download(buffer.getvalue(), filename=f"chat-summary-{format_select.value}.png")

    download_btn = ui.button("Download summary card", on_click=download_card).props("outline")
    download_btn.visible = False

    async def handle_upload(event: events.UploadEventArguments) -> None:
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            tmp_path = Path(tmp_file.name)
            tmp_file.close()
            await event.file.save(tmp_path)
            conversation = ChatParser().parse(tmp_path, chat_name=event.file.name or "chat")
            stats = ConversationSummarizer().summarize(conversation, top_n=20)
            summary = build_summary_context(stats, event.file.name or "chat.txt")
            render_summary(summary_container, summary, download_btn, summary_state)
            ui.notify("Summary generated", type="positive")
        except Exception as exc:  # pragma: no cover - UI feedback
            ui.notify(f"Unable to process file: {exc}", type="negative")
        finally:
            if "tmp_path" in locals() and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    ui.upload(on_upload=handle_upload, label="Select chat file").props("accept=.txt max-files=1")

    ui.separator()

    with summary_container:
        ui.label("No summary generated yet. Upload a chat export to begin.").classes(
            "text-gray-500"
        )


if __name__ == "__main__":
    ui.run_with(fastapi_app)
    ui.run(title="Chat Summary", reload=False)
