"""FastAPI + NiceGUI interface for chat summaries."""

from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import FastAPI
from nicegui import events, ui
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - pillow optional until user installs
    Image = ImageDraw = ImageFont = None  # type: ignore[assignment]

from summarize_chat import read_messages, summarize

fastapi_app = FastAPI()
app = fastapi_app


def _top_person(counter: Dict[str, int]) -> Tuple[str, int]:
    if not counter:
        return ("N/A", 0)
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0]


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
                "longest": stats["longest_text_by_person"].get(person, 0),
                "voice": stats["voice_by_person"].get(person, 0),
                "videos": stats["video_by_person"].get(person, 0),
                "video_notes": stats["video_note_by_person"].get(person, 0),
                "photos": stats["photo_by_person"].get(person, 0),
                "stickers": stats["sticker_by_person"].get(person, 0),
            }
        )
    people_rows.sort(key=lambda row: (-row["messages"], row["name"]))

    top_words = [{"word": word, "count": count} for word, count in stats["top_words"]]

    categories = [
        ("Most Yapper", _top_person(stats["voice_by_person"])),
        ("Writer", _top_person(stats["longest_text_by_person"])),
        ("Most Sticky", _top_person(stats["sticker_by_person"])),
        ("Photographer", _top_person(stats["photo_by_person"])),
        ("Texter", _top_person(stats["char_by_person"])),
    ]

    return {
        "filename": filename,
        "totals": totals,
        "year_rows": year_rows,
        "people_rows": people_rows,
        "show_video_notes": show_video_notes,
        "top_words": top_words,
        "categories": categories,
    }


def generate_shareable_card(summary: Dict[str, object]) -> bytes:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise RuntimeError("Pillow is required for generating shareable cards. Install it with `uv add pillow`.")
    width, height = 1000, 600
    background = (244, 247, 255)
    img = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(img)
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()

    draw.text((40, 30), "WhatsApp Chat Summary", fill=(20, 40, 80), font=title_font)
    draw.text((40, 60), summary["filename"], fill=(80, 80, 80), font=subtitle_font)

    y = 120
    draw.text((40, y), "Highlights", fill=(30, 60, 120), font=title_font)
    y += 30
    for label, (person, value) in summary["categories"]:
        draw.text(
            (60, y),
            f"{label}: {person} ({value if value else 0})",
            fill=(0, 0, 0),
            font=subtitle_font,
        )
        y += 24

    y += 20
    draw.text((40, y), "Totals", fill=(30, 60, 120), font=title_font)
    y += 30
    for label, value in summary["totals"]:
        draw.text((60, y), f"{label}: {value}", fill=(0, 0, 0), font=subtitle_font)
        y += 24

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def render_summary(container: ui.column, summary: Dict[str, object], download_btn: ui.button, summary_state: dict) -> None:
    container.clear()
    summary_state["data"] = summary
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
            ui.table(columns=year_columns, rows=summary["year_rows"], row_key="year").props("flat")

        with ui.card().classes("w-full"):
            ui.label("Highlights").classes("text-lg font-semibold mb-2")
            for label, (person, value) in summary["categories"]:
                ui.label(f"{label}: {person} ({value})").classes("text-md")

        people_columns = [
            {"name": "name", "label": "Person", "field": "name", "sortable": True},
            {"name": "messages", "label": "Messages", "field": "messages", "sortable": True},
            {"name": "characters", "label": "Characters", "field": "characters", "sortable": True},
            {"name": "longest", "label": "Longest text", "field": "longest", "sortable": True},
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
    summary_state = {"data": None}

    async def download_card() -> None:
        if not summary_state["data"]:
            ui.notify("Generate a summary first", type="warning")
            return
        try:
            data = generate_shareable_card(summary_state["data"])
        except RuntimeError as exc:
            ui.notify(str(exc), type="warning", close_button="OK")
            return
        ui.download(data, filename="chat-summary.png")

    download_btn = ui.button("Download summary card", on_click=download_card).props("outline")
    download_btn.visible = False

    async def handle_upload(event: events.UploadEventArguments) -> None:
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            tmp_path = Path(tmp_file.name)
            tmp_file.close()
            await event.file.save(tmp_path)
            messages, _ = read_messages(tmp_path)
            stats = summarize(messages, top_n=20)
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
        ui.label("No summary generated yet. Upload a chat export to begin.").classes("text-gray-500")


if __name__ == "__main__":
    ui.run_with(fastapi_app)
    ui.run(title="Chat Summary", reload=False)
