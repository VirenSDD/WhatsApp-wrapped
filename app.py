"""FastAPI + NiceGUI interface for chat summaries."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import FastAPI
from nicegui import events, ui

from summarize_chat import read_messages, summarize

fastapi_app = FastAPI()
app = fastapi_app


def build_summary_context(stats: Dict[str, object], filename: str) -> Dict[str, object]:
    show_video_notes = stats.get("export_format") != "ios" and stats["video_note_total"] > 0
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

    year_rows = [{"year": year, "messages": count} for year, count in sorted(stats["messages_by_year"].items())]

    people_rows: List[Dict[str, object]] = []
    for person, message_count in stats["messages_by_person"].items():
        people_rows.append(
            {
                "name": person,
                "messages": message_count,
                "characters": stats["char_by_person"].get(person, 0),
                "voice": stats["voice_by_person"].get(person, 0),
                "videos": stats["video_by_person"].get(person, 0),
                "video_notes": stats["video_note_by_person"].get(person, 0),
                "photos": stats["photo_by_person"].get(person, 0),
                "stickers": stats["sticker_by_person"].get(person, 0),
            }
        )
    people_rows.sort(key=lambda row: (-row["messages"], row["name"]))

    top_words = [{"word": word, "count": count} for word, count in stats["top_words"]]

    return {
        "filename": filename,
        "totals": totals,
        "year_rows": year_rows,
        "people_rows": people_rows,
        "show_video_notes": show_video_notes,
        "top_words": top_words,
    }


def render_summary(container: ui.column, summary: Dict[str, object]) -> None:
    container.clear()
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
            ui.table(columns=year_columns, rows=summary["year_rows"], row_key="year").props("flat")

        people_columns = [
            {"name": "name", "label": "Person", "field": "name", "sortable": True},
            {"name": "messages", "label": "Messages", "field": "messages", "sortable": True},
            {"name": "characters", "label": "Characters", "field": "characters", "sortable": True},
            {"name": "voice", "label": "Voice notes", "field": "voice", "sortable": True},
            {"name": "videos", "label": "Videos", "field": "videos", "sortable": True},
        ]
        if summary["show_video_notes"]:
            people_columns.append({"name": "video_notes", "label": "Video notes", "field": "video_notes", "sortable": True})
        people_columns.extend(
            [
                {"name": "photos", "label": "Photos", "field": "photos", "sortable": True},
                {"name": "stickers", "label": "Stickers", "field": "stickers", "sortable": True},
            ]
        )

        with ui.card().classes("w-full"):
            ui.label("Messages by Person").classes("text-lg font-semibold mb-2")
            ui.table(columns=people_columns, rows=summary["people_rows"], row_key="name").props("flat wrap-cells")

        word_columns = [
            {"name": "word", "label": "Word", "field": "word"},
            {"name": "count", "label": "Count", "field": "count"},
        ]
        with ui.card().classes("w-full"):
            ui.label("Most Frequent Words").classes("text-lg font-semibold mb-2")
            ui.table(columns=word_columns, rows=summary["top_words"], row_key="word").props("flat")


@ui.page("/")
def main_page():
    ui.label("WhatsApp Chat Summary").classes("text-3xl font-semibold")
    ui.label(
        "Upload an exported chat text file from Android or iOS to view message, media, and character statistics."
    ).classes("text-gray-600 mb-4")

    summary_container = ui.column().classes("gap-4 w-full")

    async def handle_upload(event: events.UploadEventArguments) -> None:
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            tmp_path = Path(tmp_file.name)
            tmp_file.close()
            await event.file.save(tmp_path)
            messages, _ = read_messages(tmp_path)
            stats = summarize(messages, top_n=20)
            summary = build_summary_context(stats, event.file.name or "chat.txt")
            render_summary(summary_container, summary)
            ui.notify("Summary generated", type="positive")
        except Exception as exc:  # pragma: no cover - UI feedback
            ui.notify(f"Unable to process file: {exc}", type="negative")
        finally:
            if "tmp_path" in locals() and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    ui.upload(on_upload=handle_upload, label="Select chat file").props("accept=.txt max-files=1")

    ui.separator()

    with summary_container:
        ui.label("No summary generated yet. Upload a chat export to begin.").classes("text-gray-500")


if __name__ == "__main__":
    ui.run_with(fastapi_app)
    ui.run(title="Chat Summary", reload=False)
