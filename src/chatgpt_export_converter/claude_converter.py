"""Convert a Claude data export into per-conversation markdown folders."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_claude_export(input_dir: Path) -> bool:
    """Return True if input_dir contains a Claude export (conversations with chat_messages)."""
    conv_path = input_dir / "conversations.json"
    if not conv_path.exists():
        return False
    try:
        with conv_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            first = data[0]
            return isinstance(first, dict) and "chat_messages" in first
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_conversations(input_dir: Path) -> list[dict[str, Any]]:
    """Load all conversations from a Claude export directory."""
    conv_path = input_dir / "conversations.json"
    with conv_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [c for c in data if isinstance(c, dict)]
    return []


# ---------------------------------------------------------------------------
# Thread path resolution
# ---------------------------------------------------------------------------

_ROOT_SENTINEL = "00000000-0000-4000-8000-000000000000"


def choose_main_path(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """
    Resolve a flat message list (potentially branched) into a linear path.

    Returns (path_messages, had_branches).  When branches exist, follows the
    path that leads to the greatest number of subsequent messages.
    """
    if not messages:
        return [], False

    by_uuid: dict[str, dict[str, Any]] = {}
    for m in messages:
        uid = m.get("uuid")
        if isinstance(uid, str) and uid:
            by_uuid[uid] = m

    children: dict[str, list[str]] = {}
    for m in messages:
        parent = m.get("parent_message_uuid") or ""
        uid = m.get("uuid") or ""
        if uid:
            children.setdefault(parent, []).append(uid)

    had_branches = any(len(kids) > 1 for kids in children.values())

    # Find entry points: messages whose parent is the sentinel or not in by_uuid
    roots = children.get(_ROOT_SENTINEL, [])
    if not roots:
        roots = [
            m["uuid"]
            for m in messages
            if m.get("parent_message_uuid") not in by_uuid and m.get("uuid")
        ]
    if not roots:
        # Last resort: sort by created_at
        sorted_msgs = sorted(
            [m for m in messages if m.get("uuid")],
            key=lambda m: m.get("created_at") or "",
        )
        return sorted_msgs, had_branches

    # Iterative DFS — find the longest path from each root to avoid recursion
    # depth limits on large conversations.
    def longest_path_from(start: str) -> list[str]:
        best: list[str] = []
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            node, path = stack.pop()
            kids = children.get(node, [])
            if not kids:
                if len(path) > len(best):
                    best = path
            else:
                for kid in kids:
                    if kid not in by_uuid:
                        continue
                    stack.append((kid, path + [kid]))
        return best

    best_path: list[str] = []
    for root in roots:
        candidate = longest_path_from(root)
        if len(candidate) > len(best_path):
            best_path = candidate

    path_messages = [by_uuid[uid] for uid in best_path if uid in by_uuid]
    return path_messages, had_branches


# ---------------------------------------------------------------------------
# Content block rendering
# ---------------------------------------------------------------------------

def _render_thinking_block(block: dict[str, Any]) -> str:
    """Render a thinking block as a collapsed <details> section."""
    thinking = (block.get("thinking") or "").strip()
    if not thinking:
        return ""
    return (
        "<details>\n"
        "<summary>💭 Thinking</summary>\n\n"
        f"{thinking}\n\n"
        "</details>"
    )


def _render_tool_use_block(block: dict[str, Any]) -> str:
    """Render a tool_use block as a labeled fenced code block."""
    name = block.get("name") or "tool"
    inp = block.get("input") or {}

    if isinstance(inp, dict) and "code" in inp:
        # REPL-style tool: show as a code block
        code = str(inp["code"])
        return f"> **[Tool: {name}]**\n\n```\n{code}\n```"

    inp_text = (
        json.dumps(inp, indent=2, ensure_ascii=False) if isinstance(inp, (dict, list)) else str(inp)
    )
    return f"> **[Tool: {name}]**\n\n```json\n{inp_text}\n```"


def _render_tool_result_block(block: dict[str, Any]) -> str:
    """Render a tool_result block as a labeled fenced code block."""
    name = block.get("name") or "tool_result"
    is_error = bool(block.get("is_error"))
    content = block.get("content") or []

    texts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text") or ""
                if t:
                    texts.append(t)
    elif isinstance(content, str) and content:
        texts.append(content)

    combined = "\n".join(texts).strip()
    error_tag = "  ⚠ error" if is_error else ""
    label = f"> **[Tool result: {name}{error_tag}]**"

    if combined:
        _MAX = 2000
        truncated = combined[:_MAX] + ("…" if len(combined) > _MAX else "")
        return f"{label}\n\n```\n{truncated}\n```"
    return label


def render_message(msg: dict[str, Any], include_tool_blocks: bool) -> str:
    """Render a single Claude message to markdown."""
    sender = msg.get("sender") or "unknown"
    heading = "## You" if sender == "human" else "## Claude"

    lines: list[str] = [heading]
    has_content = False

    for block in msg.get("content") or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")

        if btype == "text":
            text = (block.get("text") or "").strip()
            if text:
                lines.append(text)
                has_content = True

        elif btype == "thinking":
            rendered = _render_thinking_block(block)
            if rendered:
                lines.append(rendered)
                has_content = True

        elif btype == "tool_use" and include_tool_blocks:
            lines.append(_render_tool_use_block(block))
            has_content = True

        elif btype == "tool_result" and include_tool_blocks:
            lines.append(_render_tool_result_block(block))
            has_content = True

        elif btype in {"token_budget"}:
            pass  # always skip

    for att in msg.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        fname = att.get("file_name") or "attachment"
        extracted = (att.get("extracted_content") or "").strip()
        if extracted:
            lines.append(f"> **[Attached: {fname}]**\n\n{extracted}")
        else:
            lines.append(f"> **[Attached: {fname}]**")
        has_content = True

    for f in msg.get("files") or []:
        if not isinstance(f, dict):
            continue
        fname = f.get("file_name") or "file"
        lines.append(
            f"> **[File referenced: {fname} — content not included in export]**"
        )
        has_content = True

    if not has_content:
        lines.append("*(empty)*")

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# YAML front matter
# ---------------------------------------------------------------------------

def _yaml_str(value: str) -> str:
    """Wrap a string value in double quotes with internal quotes escaped."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump_yaml_front_matter(conv: dict[str, Any]) -> str:
    title = str(conv.get("name") or "untitled")
    cid = str(conv.get("uuid") or "")
    created_at = str(conv.get("created_at") or "")
    updated_at = str(conv.get("updated_at") or "")

    return "\n".join([
        "---",
        f"title: {_yaml_str(title)}",
        f"conversation_id: {_yaml_str(cid)}",
        f"created_at: {_yaml_str(created_at)}",
        f"updated_at: {_yaml_str(updated_at)}",
        'source: "claude-data-export"',
        "---",
        "",
    ])


# ---------------------------------------------------------------------------
# Path / slug helpers
# ---------------------------------------------------------------------------

def conversation_id(conv: dict[str, Any]) -> str:
    cid = conv.get("uuid")
    if isinstance(cid, str) and cid.strip():
        return cid
    return "unknown-id"


def safe_title(raw: Any) -> str:
    title = str(raw or "untitled").strip().lower()
    title = re.sub(r"\s+", "-", title)
    title = re.sub(r"[^a-z0-9-]", "", title)
    title = re.sub(r"-+", "-", title).strip("-")
    if not title:
        title = "untitled"
    return title[:80]


def date_from_iso(value: Any) -> str:
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            pass
    return "undated"


def output_folder_name() -> str:
    return datetime.now().strftime("claude-convert-%m.%d.%Y")


# ---------------------------------------------------------------------------
# Conversation rendering
# ---------------------------------------------------------------------------

def render_conversation(
    conv: dict[str, Any],
    output_dir: Path,
    summary: Any,
    dry_run: bool,
    include_tool_blocks: bool,
) -> None:
    """Render one Claude conversation to a transcript.md + metadata.json directory."""
    cid = conversation_id(conv)
    title = conv.get("name") or "untitled"
    messages = conv.get("chat_messages") or []

    if not messages:
        summary.skipped.append((cid, "no messages"))
        return

    path_messages, had_branches = choose_main_path(messages)

    if not path_messages:
        summary.skipped.append((cid, "could not resolve message path"))
        return

    date_str = date_from_iso(conv.get("created_at"))
    folder_name = f"{date_str}__{safe_title(title)}__{cid}"
    chat_dir = output_dir / folder_name

    transcript_parts: list[str] = [dump_yaml_front_matter(conv)]

    if had_branches:
        transcript_parts.append(
            "> **Note:** This conversation contained branched responses. "
            "The longest path from root is shown."
        )

    for msg in path_messages:
        transcript_parts.append(render_message(msg, include_tool_blocks))

    transcript = "\n\n".join(transcript_parts).strip() + "\n"

    if not dry_run:
        tmp_dir = output_dir / f".tmp-{cid}"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        try:
            (tmp_dir / "transcript.md").write_text(transcript, encoding="utf-8")
            metadata: dict[str, Any] = {
                "conversation_id": cid,
                "title": title,
                "stats": {
                    "messages_in_path": len(path_messages),
                    "total_messages": len(messages),
                    "had_branches": had_branches,
                },
            }
            (tmp_dir / "metadata.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            if chat_dir.exists():
                shutil.rmtree(chat_dir)
            tmp_dir.rename(chat_dir)
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

    summary.conversations_processed += 1


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------

def run_conversion(
    input_dir: Path,
    output_dir: Path,
    summary: Any,
    dry_run: bool,
    include_tool_blocks: bool,
) -> int:
    """
    Convert all conversations in a Claude export directory.

    Mutates *summary* in place (same Summary dataclass used by converter.py).
    Returns the total number of conversations found (including skipped/failed).
    """
    conversations = load_conversations(input_dir)
    total = len(conversations)

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for i, conv in enumerate(conversations, start=1):
        prev_processed = summary.conversations_processed
        prev_skipped = len(summary.skipped)

        try:
            render_conversation(conv, output_dir, summary, dry_run, include_tool_blocks)
        except Exception as exc:
            summary.skipped.append((conversation_id(conv), f"exception: {exc}"))

        if summary.conversations_processed > prev_processed:
            print(f"  {i}/{total} converted")
        elif len(summary.skipped) > prev_skipped:
            reason = summary.skipped[-1][1]
            short = reason[:60] + ("…" if len(reason) > 60 else "")
            print(f"  {i}/{total} FAILED  ({short})")

    return total
