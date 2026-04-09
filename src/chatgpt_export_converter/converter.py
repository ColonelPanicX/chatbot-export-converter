#!/usr/bin/env python3
"""Convert a ChatGPT data export into browsable per-conversation markdown folders."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ASSET_ID_RE = re.compile(r"(file[-_][A-Za-z0-9]+)")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


@dataclass
class Summary:
    conversations_processed: int = 0
    assets_copied: int = 0
    conversations_skipped_unchanged: int = 0
    skipped: list[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        if self.skipped is None:
            self.skipped = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert ChatGPT export JSON into per-chat markdown folders."
    )
    parser.add_argument("--input", help="Path to ChatGPT export (.zip file or unzipped directory)")
    parser.add_argument("--output", help="Path to output folder")
    parser.add_argument(
        "--dry-run",
        "--dryrun",
        action="store_true",
        help="Parse and report actions without writing files.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only rebuild new/changed conversations; skip unchanged ones.",
    )
    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Launch interactive prompt mode.",
    )
    return parser.parse_args()


def _output_folder_name() -> str:
    """Return the dated output folder name: chatgpt-convert-MM.DD.YYYY"""
    return datetime.now().strftime("chatgpt-convert-%m.%d.%Y")


def prompt_bool(prompt: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please answer y or n.")


def _prompt_input_path() -> Path:
    """Prompt for a zip file or directory path, validate, and return it."""
    while True:
        raw = input("Path to your ChatGPT export (.zip file or directory):\n> ").strip()
        if not raw:
            print("  A path is required.")
            continue
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            print(f"  Not found: {path}")
            continue
        if path.is_dir():
            return path
        if path.is_file() and path.suffix.lower() == ".zip":
            return path
        print("  Must be a .zip file or an unzipped directory.")


def _prompt_output_dir(input_path: Path) -> Path:
    """
    Ask where to save the converted chats.
    Option 1 is always the same folder as the input.
    Option 2 lets the user enter a custom location.
    Returns the full output path (parent / folder-name).
    """
    folder_name = _output_folder_name()
    default_parent = input_path.parent
    default_output = default_parent / folder_name

    print(f"\nWhere would you like to save the converted chats?")
    print(f"  [1] Same folder as the input  ({default_output})")
    print(f"  [2] Choose a different location")

    while True:
        choice = input("> ").strip()
        if choice in {"", "1"}:
            return default_output
        if choice == "2":
            while True:
                raw = input("Enter output directory path:\n> ").strip()
                if not raw:
                    print("  A path is required.")
                    continue
                return Path(raw).expanduser().resolve() / folder_name
        print("  Please enter 1 or 2.")


def run_menu(args: argparse.Namespace) -> tuple[Path, Path, bool, bool]:
    """
    Interactive menu. Returns (input_path, output_dir, incremental, dry_run).
    Replaces the old run_wizard.
    """
    print()
    print("=" * 56)
    print("  ChatGPT Export Converter")
    print("=" * 56)
    print()

    input_path = _prompt_input_path()
    output_dir = _prompt_output_dir(input_path)

    print()
    incremental = prompt_bool("Use incremental mode (skip unchanged chats)?", default=True)
    dry_run = prompt_bool("Dry run only (no files written)?", default=False)

    print()
    print("Ready to convert.")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_dir}")
    mode_flags = []
    if incremental:
        mode_flags.append("incremental")
    if dry_run:
        mode_flags.append("dry-run")
    print(f"  Mode:   {', '.join(mode_flags) if mode_flags else 'standard'}")
    print()

    if not prompt_bool("Proceed?", default=True):
        print("Cancelled.")
        raise SystemExit(0)

    return input_path, output_dir, incremental, dry_run


def run_wizard(args: argparse.Namespace) -> tuple[Path, Path]:
    """Deprecated: use run_menu (invoked automatically with no flags)."""
    print("Note: --wizard is deprecated. Running interactive menu.", file=sys.stderr)
    input_path, output_dir, incremental, dry_run = run_menu(args)
    args.incremental = incremental
    args.dry_run = dry_run
    return input_path, output_dir


@contextlib.contextmanager
def extracted_input(input_path: Path):
    """Yield the input directory, extracting a .zip to a temp dir if needed."""
    if input_path.is_dir():
        yield input_path
        return

    with tempfile.TemporaryDirectory(prefix="chatgpt-export-") as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(tmp_dir)
        yield tmp_dir


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def discover_conversation_files(input_dir: Path) -> list[Path]:
    exact = sorted(input_dir.rglob("conversations.json"))
    if exact:
        return exact

    shards = sorted(input_dir.rglob("conversations-*.json"))
    if shards:
        return shards

    fallback: list[Path] = []
    for candidate in sorted(input_dir.rglob("*.json")):
        name = candidate.name
        if name in {"shared_conversations.json", "message_feedback.json", "user.json", "sora.json"}:
            continue
        fallback.append(candidate)
    return fallback


def extract_conversations(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("conversations"), list):
            return [x for x in data["conversations"] if isinstance(x, dict)]
        if isinstance(data.get("items"), list):
            return [x for x in data["items"] if isinstance(x, dict)]
    return []


def load_all_conversations(input_dir: Path) -> tuple[list[dict[str, Any]], list[Path]]:
    files = discover_conversation_files(input_dir)
    all_conversations: list[dict[str, Any]] = []

    for path in files:
        try:
            data = load_json(path)
        except Exception as exc:
            print(f"warning: skipping {path}: {exc}", file=sys.stderr)
            continue
        convs = extract_conversations(data)
        if convs:
            all_conversations.extend(convs)

    return all_conversations, files


def to_iso(value: Any) -> str:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except Exception:
            return ""
    if isinstance(value, str):
        return value
    return ""


def date_from_timestamp(value: Any) -> str:
    iso = to_iso(value)
    if iso:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            pass
    return "undated"


def safe_title(raw: Any) -> str:
    title = str(raw or "untitled").strip().lower()
    title = re.sub(r"\s+", "-", title)
    title = re.sub(r"[^a-z0-9-]", "", title)
    title = re.sub(r"-+", "-", title).strip("-")
    if not title:
        title = "untitled"
    return title[:80]


def build_asset_index(input_dir: Path) -> tuple[dict[str, list[Path]], list[Path]]:
    by_asset_id: dict[str, list[Path]] = defaultdict(list)
    all_files: list[Path] = []

    for root, _, files in os.walk(input_dir):
        root_path = Path(root)
        for file_name in files:
            p = root_path / file_name
            all_files.append(p)
            match = ASSET_ID_RE.match(file_name)
            if match:
                by_asset_id[match.group(1)].append(p)

    return by_asset_id, all_files


def extract_asset_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = ASSET_ID_RE.search(value)
    if not match:
        return None
    return match.group(1)


def collect_asset_ids_from_obj(obj: Any, out: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            lkey = key.lower()
            if lkey in {"asset_pointer", "watermarked_asset_pointer", "asset_pointer_link", "file_id", "asset_id"}:
                asset_id = extract_asset_id(value)
                if asset_id:
                    out.append(asset_id)
            if lkey == "id" and isinstance(value, str) and value.startswith(("file-", "file_")):
                out.append(value)
            collect_asset_ids_from_obj(value, out)
    elif isinstance(obj, list):
        for item in obj:
            collect_asset_ids_from_obj(item, out)
    elif isinstance(obj, str):
        asset_id = extract_asset_id(obj)
        if asset_id:
            out.append(asset_id)


def collect_message_asset_ids(message: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    metadata = message.get("metadata") or {}
    attachments = metadata.get("attachments") or []
    for attachment in attachments:
        if isinstance(attachment, dict):
            aid = attachment.get("id")
            if isinstance(aid, str):
                ids.append(aid)

    content = message.get("content") or {}
    collect_asset_ids_from_obj(content, ids)

    seen = set()
    unique: list[str] = []
    for aid in ids:
        if aid not in seen:
            unique.append(aid)
            seen.add(aid)
    return unique


def resolve_asset_paths(
    asset_id: str,
    input_dir: Path,
    by_asset_id: dict[str, list[Path]],
    all_files: list[Path],
) -> list[Path]:
    candidates: list[Path] = []

    data_dir = input_dir / f"{asset_id}_data"
    if data_dir.is_dir():
        candidates.extend(sorted(p for p in data_dir.rglob("*") if p.is_file()))

    direct = input_dir / asset_id
    if direct.is_file():
        candidates.append(direct)

    for p in by_asset_id.get(asset_id, []):
        candidates.append(p)

    if not candidates:
        prefix_a = asset_id + "-"
        prefix_b = asset_id + "_"
        for p in all_files:
            name = p.name
            if name.startswith(prefix_a) or name.startswith(prefix_b):
                candidates.append(p)

    deduped: list[Path] = []
    seen = set()
    for p in candidates:
        rp = str(p.resolve())
        if rp not in seen:
            deduped.append(p)
            seen.add(rp)
    return deduped


def choose_conversation_path(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        return []

    current_node = conversation.get("current_node")
    if not current_node or current_node not in mapping:
        nodes = [n for n in mapping.values() if isinstance(n, dict)]
        nodes.sort(key=lambda n: (n.get("message") or {}).get("create_time") or 0)
        return [n for n in nodes if isinstance(n.get("message"), dict)]

    chain: list[dict[str, Any]] = []
    node_id = current_node
    visited = set()

    while node_id and node_id not in visited and node_id in mapping:
        visited.add(node_id)
        node = mapping[node_id]
        if isinstance(node, dict):
            chain.append(node)
            node_id = node.get("parent")
        else:
            break

    chain.reverse()
    return [n for n in chain if isinstance(n.get("message"), dict)]


def role_heading(role: str) -> str:
    if role == "user":
        return "User"
    if role == "assistant":
        return "Assistant"
    if role == "system":
        return "System"
    if role == "tool":
        return "Tool"
    return role.title() if role else "Unknown"


def fence(text: str, lang: str = "") -> str:
    safe = text.replace("\r\n", "\n")
    return f"```{lang}\n{safe}\n```"


def unique_target_path(target_dir: Path, file_name: str) -> Path:
    candidate = target_dir / file_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    i = 2
    while True:
        alt = target_dir / f"{stem}-{i}{suffix}"
        if not alt.exists():
            return alt
        i += 1


def copy_assets_for_conversation(
    conv_asset_ids: list[str],
    chat_dir: Path,
    input_dir: Path,
    by_asset_id: dict[str, list[Path]],
    all_files: list[Path],
    dry_run: bool,
) -> tuple[dict[str, list[str]], int, list[str]]:
    copied_count = 0
    unresolved: list[str] = []
    mapped: dict[str, list[str]] = {}

    if not conv_asset_ids:
        return mapped, copied_count, unresolved

    assets_dir = chat_dir / "assets"
    if not dry_run:
        assets_dir.mkdir(parents=True, exist_ok=True)

    for asset_id in conv_asset_ids:
        source_paths = resolve_asset_paths(asset_id, input_dir, by_asset_id, all_files)
        if not source_paths:
            unresolved.append(asset_id)
            continue

        rels: list[str] = []
        for source_path in source_paths:
            target_name = source_path.name
            target_path = assets_dir / target_name
            if not dry_run:
                target_path = unique_target_path(assets_dir, target_name)
                shutil.copy2(source_path, target_path)
            rel = f"assets/{target_path.name}"
            rels.append(rel)
            copied_count += 1
        mapped[asset_id] = rels

    return mapped, copied_count, unresolved


def link_for_asset(rel_path: str) -> str:
    suffix = Path(rel_path).suffix.lower()
    if suffix in IMAGE_EXTS:
        return f"![image]({rel_path})"
    if suffix in {".wav", ".mp3", ".m4a", ".ogg"}:
        return f"[audio file]({rel_path})"
    return f"[download file]({rel_path})"


def sanitize_text_block(text: str) -> str:
    """Escape placeholder asset patterns that are not real links."""
    text = re.sub(r"assets/<([^>]+)>", r"assets/&lt;\1&gt;", text)
    text = text.replace("![image](assets/&lt;", "!\\[image\\](assets/&lt;")
    text = text.replace("[download file](assets/&lt;", "\\[download file\\](assets/&lt;")
    return text


def message_to_markdown(message: dict[str, Any], asset_links: dict[str, list[str]]) -> str:
    author = message.get("author") or {}
    role = str(author.get("role") or "unknown")
    heading = role_heading(role)
    content = message.get("content") or {}
    ctype = content.get("content_type") or "text"
    metadata = message.get("metadata") or {}

    lines: list[str] = [f"## {heading}"]

    if role == "tool" or ctype.startswith("tether_") or ctype in {"execution_output", "system_error"}:
        cmd = metadata.get("command")
        cmd_txt = f" {cmd}" if isinstance(cmd, str) and cmd else ""
        lines.append(f"> [tool] {ctype}{cmd_txt}")

    emitted_ids: set[str] = set()

    if ctype == "code":
        language = content.get("language")
        language = "" if not isinstance(language, str) or language == "unknown" else language
        code = str(content.get("text") or "")
        lines.append(fence(code, language))
    elif ctype == "execution_output":
        text = str(content.get("text") or "")
        lines.append(fence(text, "text"))
    elif ctype in {"thoughts", "reasoning_recap"}:
        text = str(content.get("text") or "")
        lines.append(f"> [{ctype}] {text}")
    else:
        parts = content.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, str):
                    if part.strip():
                        lines.append(sanitize_text_block(part))
                    continue

                if not isinstance(part, dict):
                    continue

                p_ctype = str(part.get("content_type") or "")
                p_text = part.get("text")
                if isinstance(p_text, str) and p_text.strip():
                    lines.append(sanitize_text_block(p_text))

                potential_ids: list[str] = []
                collect_asset_ids_from_obj(part, potential_ids)
                for aid in potential_ids:
                    if aid in emitted_ids:
                        continue
                    for rel in asset_links.get(aid, []):
                        lines.append(link_for_asset(rel))
                    if aid in asset_links:
                        emitted_ids.add(aid)
        else:
            text_value = content.get("text")
            if isinstance(text_value, str) and text_value.strip():
                lines.append(sanitize_text_block(text_value))

    attachments = metadata.get("attachments") or []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        aid = attachment.get("id")
        if not isinstance(aid, str) or aid in emitted_ids:
            continue
        for rel in asset_links.get(aid, []):
            lines.append(link_for_asset(rel))
        if aid in asset_links:
            emitted_ids.add(aid)

    if len(lines) == 1:
        lines.append("(no content)")

    return "\n\n".join(lines)


def dump_yaml_front_matter(conversation: dict[str, Any]) -> str:
    title = str(conversation.get("title") or "untitled").replace('"', '\\"')
    cid = str(conversation.get("id") or conversation.get("conversation_id") or "")
    created_at = to_iso(conversation.get("create_time"))
    updated_at = to_iso(conversation.get("update_time"))
    archived = bool(conversation.get("is_archived", False))

    return "\n".join(
        [
            "---",
            f'title: "{title}"',
            f'conversation_id: "{cid}"',
            f'created_at: "{created_at}"',
            f'updated_at: "{updated_at}"',
            f'archived: "{str(archived).lower()}"',
            'source: "chatgpt-data-export"',
            "---",
            "",
        ]
    )


def conversation_id(conv: dict[str, Any]) -> str:
    cid = conv.get("id") or conv.get("conversation_id")
    if isinstance(cid, str) and cid.strip():
        return cid
    return "unknown-conversation-id"


def find_existing_chat_dir(output_dir: Path, cid: str) -> Path | None:
    if not output_dir.exists():
        return None
    suffix = f"__{cid}"
    matches = [p for p in output_dir.iterdir() if p.is_dir() and p.name.endswith(suffix)]
    if not matches:
        return None
    return sorted(matches, key=lambda p: p.name)[0]


def conversation_signature(
    conversation: dict[str, Any],
    selected_messages: list[dict[str, Any]],
    conv_asset_ids: list[str],
    total_message_nodes: int,
) -> str:
    payload = {
        "id": conversation_id(conversation),
        "title": conversation.get("title"),
        "create_time": conversation.get("create_time"),
        "update_time": conversation.get("update_time"),
        "current_node": conversation.get("current_node"),
        "total_message_nodes": total_message_nodes,
        "selected_message_ids": [m.get("id") for m in selected_messages],
        "selected_message_update_times": [m.get("update_time") for m in selected_messages],
        "asset_ids": conv_asset_ids,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def render_conversation(
    conversation: dict[str, Any],
    input_dir: Path,
    output_dir: Path,
    by_asset_id: dict[str, list[Path]],
    all_files: list[Path],
    summary: Summary,
    dry_run: bool,
    incremental: bool,
) -> None:
    cid = conversation_id(conversation)
    title = conversation.get("title") or "untitled"

    convo_path_nodes = choose_conversation_path(conversation)
    if not convo_path_nodes:
        summary.skipped.append((cid, "missing or invalid conversation mapping"))
        return

    conv_create_time = conversation.get("create_time")
    if conv_create_time is None:
        first_msg = convo_path_nodes[0].get("message") or {}
        conv_create_time = first_msg.get("create_time")

    folder_name = f"{date_from_timestamp(conv_create_time)}__{safe_title(title)}__{cid}"
    desired_chat_dir = output_dir / folder_name
    existing_chat_dir = find_existing_chat_dir(output_dir, cid)
    chat_dir = desired_chat_dir

    selected_messages: list[dict[str, Any]] = [n.get("message") for n in convo_path_nodes if isinstance(n.get("message"), dict)]

    conv_asset_ids: list[str] = []
    seen_assets = set()
    for msg in selected_messages:
        for aid in collect_message_asset_ids(msg):
            if aid not in seen_assets:
                conv_asset_ids.append(aid)
                seen_assets.add(aid)

    mapping = conversation.get("mapping") or {}
    total_message_nodes = sum(1 for node in mapping.values() if isinstance((node or {}).get("message"), dict))
    has_prior_versions = total_message_nodes > len(selected_messages)
    signature = conversation_signature(conversation, selected_messages, conv_asset_ids, total_message_nodes)

    if incremental and existing_chat_dir and not dry_run:
        metadata_path = existing_chat_dir / "metadata.json"
        transcript_path = existing_chat_dir / "transcript.md"
        if metadata_path.exists() and transcript_path.exists():
            try:
                existing_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
                if existing_meta.get("source_signature") == signature:
                    if existing_chat_dir != desired_chat_dir:
                        if desired_chat_dir.exists():
                            shutil.rmtree(desired_chat_dir)
                        existing_chat_dir.rename(desired_chat_dir)
                    summary.conversations_skipped_unchanged += 1
                    return
            except Exception:
                pass

    if not dry_run:
        # If an existing dir needs to be renamed (title/date changed), do that first.
        if existing_chat_dir and existing_chat_dir != desired_chat_dir and existing_chat_dir.exists():
            if desired_chat_dir.exists():
                shutil.rmtree(desired_chat_dir)
            existing_chat_dir.rename(desired_chat_dir)
        # Write into a temp dir; rename to desired_chat_dir only after all writes
        # succeed — prevents a partially-written directory from replacing good output
        # if the process is interrupted mid-render.
        tmp_dir = desired_chat_dir.parent / f".tmp-{cid}"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        chat_dir = tmp_dir

    try:
        asset_links, copied_count, unresolved_assets = copy_assets_for_conversation(
            conv_asset_ids,
            chat_dir,
            input_dir,
            by_asset_id,
            all_files,
            dry_run,
        )
        summary.assets_copied += copied_count

        transcript_parts: list[str] = [dump_yaml_front_matter(conversation)]

        if has_prior_versions:
            transcript_parts.append(
                "> [note] Conversation contained edited/branched history. This transcript follows the final path to `current_node`."
            )

        for message in selected_messages:
            transcript_parts.append(message_to_markdown(message, asset_links))

        transcript = "\n\n".join(transcript_parts).strip() + "\n"

        if not dry_run:
            (chat_dir / "transcript.md").write_text(transcript, encoding="utf-8")

            metadata_out = {
                "conversation_id": cid,
                "title": title,
                "source_files": {
                    "has_chat_html": (input_dir / "chat.html").exists(),
                },
                "stats": {
                    "selected_messages": len(selected_messages),
                    "total_message_nodes": total_message_nodes,
                    "has_prior_versions": has_prior_versions,
                    "asset_ids_detected": len(conv_asset_ids),
                    "asset_ids_resolved": len(asset_links),
                    "asset_ids_unresolved": len(unresolved_assets),
                },
                "source_signature": signature,
                "unresolved_asset_ids": unresolved_assets,
            }
            (chat_dir / "metadata.json").write_text(
                json.dumps(metadata_out, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            # Atomic swap: fully-written tmp_dir replaces desired_chat_dir.
            if desired_chat_dir.exists():
                shutil.rmtree(desired_chat_dir)
            chat_dir.rename(desired_chat_dir)

    except Exception:
        if not dry_run:
            shutil.rmtree(chat_dir, ignore_errors=True)
        raise

    summary.conversations_processed += 1


def print_summary(summary: Summary) -> None:
    print("\nConversion summary")
    print(f"- conversations processed: {summary.conversations_processed}")
    print(f"- conversations skipped unchanged: {summary.conversations_skipped_unchanged}")
    print(f"- asset files copied: {summary.assets_copied}")
    if summary.skipped:
        print(f"- conversations skipped: {len(summary.skipped)}")
        for cid, reason in summary.skipped[:50]:
            print(f"  - {cid}: {reason}")
        if len(summary.skipped) > 50:
            print(f"  - ... and {len(summary.skipped) - 50} more")
    else:
        print("- conversations skipped: 0")


def main() -> int:
    args = parse_args()
    if args.wizard:
        # --wizard is deprecated; delegates to run_menu and patches args
        input_path, output_dir = run_wizard(args)
    elif not args.input and not args.output:
        input_path, output_dir, args.incremental, args.dry_run = run_menu(args)
    else:
        if not args.input or not args.output:
            print("error: both --input and --output are required unless using --wizard", file=sys.stderr)
            return 1
        input_path = Path(args.input).expanduser().resolve()
        output_dir = Path(args.output).expanduser().resolve()

    if not input_path.exists():
        print(f"error: input not found: {input_path}", file=sys.stderr)
        return 1
    if not input_path.is_dir() and not (input_path.is_file() and input_path.suffix.lower() == ".zip"):
        print(f"error: input must be a .zip file or a directory: {input_path}", file=sys.stderr)
        return 1

    with extracted_input(input_path) as input_dir:
        conversations, convo_files = load_all_conversations(input_dir)
        if not conversations:
            print("error: no conversations found. Expected conversations.json or conversations-*.json", file=sys.stderr)
            return 1

        unique_by_id: dict[str, dict[str, Any]] = {}
        for conv in conversations:
            cid = conversation_id(conv)
            if cid in unique_by_id:
                print(
                    f"warning: duplicate conversation ID '{cid}' — keeping last occurrence",
                    file=sys.stderr,
                )
            unique_by_id[cid] = conv

        by_asset_id, all_files = build_asset_index(input_dir)

        if not args.dry_run:
            output_dir.mkdir(parents=True, exist_ok=True)

        summary = Summary()

        for conv in unique_by_id.values():
            try:
                render_conversation(
                    conv,
                    input_dir,
                    output_dir,
                    by_asset_id,
                    all_files,
                    summary,
                    args.dry_run,
                    args.incremental,
                )
            except Exception as exc:  # keep processing on bad records
                summary.skipped.append((conversation_id(conv), f"exception: {exc}"))

    if args.dry_run:
        print("dry-run mode: no files written")

    print(f"discovered conversation files: {len(convo_files)}")
    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
