# chatbot-export-converter

Convert ChatGPT and Claude data exports into browsable per-conversation markdown folders.

## Quick Start

### 1. Get your export

**ChatGPT:** Settings → Data Controls → Export Data → download the `.zip`

**Claude:** Settings → Privacy → Export Data → download the `.zip`

### 2. Install

```bash
pipx install .
# or, if you have uv:
uv tool install .
```

### 3. Run

```bash
chatbot-convert
```

The tool opens an interactive menu. It will ask for your export file and where to save the output — no flags needed. Format (ChatGPT vs Claude) is auto-detected.

---

## Output

One folder per conversation, named by date, title, and ID:

```
chatgpt-convert-04.13.2026/
└── 2025-03-14__my-python-question__abc123uuid/
    ├── transcript.md
    └── metadata.json
```

Claude exports use the same structure under a `claude-convert-MM.DD.YYYY/` folder.

---

## Direct Mode (no menu)

Pass `--input` and `--output` to skip the interactive menu entirely:

```bash
chatbot-convert --input /path/to/export.zip --output ./chats
chatbot-convert --input /path/to/unzipped-export/ --output ./chats
```

---

## All Options

| Flag | Description |
|------|-------------|
| `--input` | Path to export (`.zip` file or unzipped directory) |
| `--output` | Path to output folder |
| `--incremental` | Skip conversations unchanged since last run *(ChatGPT only)* |
| `--include-tool-blocks` | Include `tool_use`/`tool_result` blocks in transcripts *(Claude only)* |
| `--dry-run` | Parse and report without writing any files |

---

## Supported Formats

| Source | Input | Notes |
|--------|-------|-------|
| ChatGPT | `.zip` or unzipped directory | Includes asset copying |
| Claude | `.zip` or unzipped directory | No media files in Claude exports |

---

## Known Limitations

### Unresolved assets in `metadata.json` (ChatGPT)

Each ChatGPT conversation's `metadata.json` includes an `unresolved_asset_ids` list. An ID appears there when a conversation references a file that isn't present in the export zip. This is a ChatGPT export limitation — the transcript is still complete; only those specific attachments are missing.

---

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run black --check .
uv run mypy src/chatbot_export_converter/
```
