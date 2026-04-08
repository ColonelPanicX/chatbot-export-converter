# chatgpt-export-converter

Convert a ChatGPT data export into browsable per-conversation markdown folders.

## Install

```bash
pipx install .
```

## Usage

**Interactive menu** (no flags):
```bash
chatgpt-convert
```

**Direct mode:**
```bash
chatgpt-convert --input /path/to/chatgpt-export.zip --output ./chats
chatgpt-convert --input /path/to/unzipped-export/  --output ./chats
```

**Options:**
```
--input       Path to ChatGPT export (zip file or unzipped directory)
--output      Path to output folder
--incremental Skip conversations unchanged since last run
--dry-run     Parse and report without writing any files
--wizard      Interactive prompt mode (legacy)
```

## Output

One folder per conversation:

```
chats/
└── 2025-03-14__my-python-question__abc123uuid/
    ├── transcript.md
    ├── metadata.json
    └── assets/
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/
ruff check src/
```
