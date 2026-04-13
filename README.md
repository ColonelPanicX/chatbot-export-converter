# chatbot-export-converter

Convert ChatGPT and Claude data exports into browsable per-conversation markdown folders.

## Install

```bash
pipx install .
```

## Usage

**Interactive menu** (no flags — auto-detects export format):
```bash
chatbot-convert
```

**Direct mode:**
```bash
chatbot-convert --input /path/to/export.zip --output ./chats
chatbot-convert --input /path/to/unzipped-export/ --output ./chats
```

**Options:**
```
--input                Path to export (zip file or unzipped directory)
--output               Path to output folder
--incremental          Skip conversations unchanged since last run (ChatGPT only)
--include-tool-blocks  Include tool_use/tool_result blocks in Claude transcripts
--dry-run              Parse and report without writing any files
--wizard               Interactive prompt mode (legacy)
```

## Output

One folder per conversation:

```
chats/
└── 2025-03-14__my-python-question__abc123uuid/
    ├── transcript.md
    └── metadata.json
```

## Supported Formats

| Source | Input | Notes |
|--------|-------|-------|
| ChatGPT | `chatgpt-export.zip` or unzipped directory | Includes asset copying |
| Claude | Claude data export `.zip` or unzipped directory | No media files in Claude exports |

Format is auto-detected — no flag required.

## Known Limitations

### Unresolved assets in `metadata.json` (ChatGPT)

Each ChatGPT conversation's `metadata.json` includes an `unresolved_asset_ids` list. An ID appears there when a conversation references a file that isn't present in the export zip. This is a ChatGPT export limitation — the transcript is still complete; only those specific attachments are missing.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run black --check .
uv run mypy src/chatbot_export_converter/
```
