# WhatsApp Chat Summary

Generate high-level stats and shareable summary cards from exported WhatsApp chats.

## Features

- Upload Android/iOS text exports and see totals, per-year, and per-participant stats.
- Download a pre-styled vertical “wrapped” card highlighting the most talkative participants.
- FastAPI + NiceGUI front-end with responsive tables and cards.

## Getting Started

1. Install Python 3.13 (matching the version used in `pyproject.toml`).
2. Install [uv](https://docs.astral.sh/uv/) if you don’t have it yet (`pip install uv`).
3. Install project dependencies with uv:
   ```bash
   uv sync
   ```
4. Run the app from the project root:
   ```bash
   python app/main.py
   ```
5. Open the URL printed in the terminal (typically `http://127.0.0.1:8080`) and upload a `.txt` chat export.

## CLI Summary Tool

You can also summarize chats via CLI:

```bash
python app/summarize_chat.py path/to/chat.txt
```

## Project Structure

- `app/main.py` – NiceGUI UI entrypoint.
- `app/infrastructure/parser.py` – WhatsApp chat parser.
- `app/application/services.py` – Summary aggregations.
- `app/wrapped_image.py` – Shareable card renderer.
