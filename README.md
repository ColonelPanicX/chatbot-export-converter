# chatbot-export-converter

Convert ChatGPT and Claude data exports into browsable per-conversation markdown folders.

---

## Windows

### 1. Get your export

**ChatGPT:** Settings → Data Controls → Export Data → download the `.zip`

**Claude:** Settings → Privacy → Export Data → download the `.zip`

### 2. Download the exe

Grab `chatbot-convert.exe` from the [latest release](https://github.com/ColonelPanicX/chatbot-export-converter/releases/latest).

### 3. Run

Double-click `chatbot-convert.exe`. The GUI opens automatically — no install, no terminal required.

<!-- screenshot -->

---

## Mac / Linux

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

The interactive menu will ask for your export file and where to save the output. Format (ChatGPT vs Claude) is auto-detected.

---

## Output

One folder per conversation, named by date, title, and ID:

```
chatgpt-convert-04.13.2026/
└── 2025-03-14__my-python-question__abc123uuid/
    └── transcript.md

claude-convert-04.13.2026/
└── 2025-03-14__my-claude-chat__abc123uuid/
    └── transcript.md
```

Each `transcript.md` opens as a readable markdown file with full conversation history and a YAML frontmatter block containing stats and metadata.

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

### Unresolved assets (ChatGPT)

When a conversation references a file that isn't present in the export zip, its ID is recorded in the transcript frontmatter under `unresolved_asset_ids`. The transcript is still complete — only those specific attachments are missing. This is a ChatGPT export limitation.

---

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run black --check .
uv run mypy src/chatbot_export_converter/
```
