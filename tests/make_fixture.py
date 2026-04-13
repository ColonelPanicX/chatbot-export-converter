#!/usr/bin/env python3
"""
Synthetic ChatGPT export generator.

Produces a small, realistic .zip file that exercises all major converter
code paths. Use as a test fixture or a manual dev tool.

Usage:
    python tests/make_fixture.py              # writes test-export.zip in cwd
    python tests/make_fixture.py ./my.zip     # writes to specified path
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixed timestamps for deterministic output
# 1700000000 = 2023-11-14 22:13:20 UTC
# ---------------------------------------------------------------------------
T0 = 1700000000.0


def _node(
    node_id: str,
    parent_id: str | None,
    children: list[str],
    role: str,
    content: dict,
    create_time: float | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": node_id,
        "parent": parent_id,
        "children": children,
        "message": {
            "id": node_id,
            "author": {"role": role, "name": None, "metadata": {}},
            "create_time": create_time,
            "update_time": None,
            "content": content,
            "status": "finished_successfully",
            "end_turn": role == "assistant",
            "weight": 1.0,
            "metadata": metadata or {},
            "recipient": "all",
        },
    }


def _text_content(text: str) -> dict:
    return {"content_type": "text", "parts": [text]}


def _conv(
    conv_id: str,
    title: str,
    mapping: dict,
    current_node: str,
    create_time: float | None = T0,
    is_archived: bool = False,
) -> dict:
    return {
        "id": conv_id,
        "conversation_id": conv_id,
        "title": title,
        "create_time": create_time,
        "update_time": create_time,
        "current_node": current_node,
        "is_archived": is_archived,
        "mapping": mapping,
        "moderation_results": [],
        "plugin_ids": None,
        "gizmo_id": None,
    }


# ---------------------------------------------------------------------------
# Conversation builders
# ---------------------------------------------------------------------------


def _conv_plain_text() -> dict:
    """1. Simple user/assistant text exchange."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0),
        "msg-1": _node(
            "msg-1",
            "root",
            ["msg-2"],
            "user",
            _text_content("What is the capital of France?"),
            T0 + 1,
        ),
        "msg-2": _node(
            "msg-2",
            "msg-1",
            [],
            "assistant",
            _text_content("The capital of France is Paris."),
            T0 + 2,
        ),
    }
    return _conv("conv-plain-text-001", "Capital of France", mapping, "msg-2", T0)


def _conv_code_block() -> dict:
    """2. Code block (code content_type)."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0 + 100),
        "msg-1": _node(
            "msg-1",
            "root",
            ["msg-2"],
            "user",
            _text_content("Write a Python hello world."),
            T0 + 101,
        ),
        "msg-2": _node(
            "msg-2",
            "msg-1",
            [],
            "assistant",
            {"content_type": "code", "language": "python", "text": 'print("Hello, world!")'},
            T0 + 102,
        ),
    }
    return _conv("conv-code-block-002", "Python Hello World", mapping, "msg-2", T0 + 100)


def _conv_image_attachment() -> dict:
    """3. Image attachment (image_asset_pointer + asset file in zip)."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0 + 200),
        "msg-1": _node(
            "msg-1",
            "root",
            ["msg-2"],
            "user",
            {
                "content_type": "multimodal_text",
                "parts": [
                    "Here is an image:",
                    {
                        "asset_pointer": "file-service://file-TESTASSET001",
                        "content_type": "image_asset_pointer",
                        "fovea": None,
                        "height": 100,
                        "metadata": None,
                        "size_bytes": 100,
                        "width": 100,
                    },
                ],
            },
            T0 + 201,
            metadata={
                "attachments": [{"id": "file-TESTASSET001", "name": "test.png", "size": 100}]
            },
        ),
        "msg-2": _node(
            "msg-2",
            "msg-1",
            [],
            "assistant",
            _text_content("I can see the image you attached."),
            T0 + 202,
        ),
    }
    return _conv("conv-image-attach-003", "Image Attachment Test", mapping, "msg-2", T0 + 200)


def _conv_execution_output() -> dict:
    """4. Tool / execution output."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0 + 300),
        "msg-1": _node(
            "msg-1", "root", ["msg-2"], "user", _text_content("Run 2 + 2 in Python."), T0 + 301
        ),
        "msg-2": _node(
            "msg-2",
            "msg-1",
            ["msg-3"],
            "assistant",
            {"content_type": "code", "language": "python", "text": "print(2 + 2)"},
            T0 + 302,
        ),
        "msg-3": _node(
            "msg-3",
            "msg-2",
            ["msg-4"],
            "tool",
            {"content_type": "execution_output", "text": "4"},
            T0 + 303,
        ),
        "msg-4": _node(
            "msg-4", "msg-3", [], "assistant", _text_content("The result is 4."), T0 + 304
        ),
    }
    return _conv("conv-exec-output-004", "Code Execution", mapping, "msg-4", T0 + 300)


def _conv_archived() -> dict:
    """5. Archived conversation."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0 + 400),
        "msg-1": _node(
            "msg-1", "root", ["msg-2"], "user", _text_content("Old question I archived."), T0 + 401
        ),
        "msg-2": _node("msg-2", "msg-1", [], "assistant", _text_content("Old answer."), T0 + 402),
    }
    return _conv("conv-archived-005", "Archived Chat", mapping, "msg-2", T0 + 400, is_archived=True)


def _conv_missing_timestamp() -> dict:
    """6. Missing create_time — should produce 'undated' folder prefix."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), None),
        "msg-1": _node(
            "msg-1", "root", ["msg-2"], "user", _text_content("When was this created?"), None
        ),
        "msg-2": _node(
            "msg-2",
            "msg-1",
            [],
            "assistant",
            _text_content("I have no idea — my timestamp is missing."),
            None,
        ),
    }
    return _conv(
        "conv-no-timestamp-006", "Undated Conversation", mapping, "msg-2", create_time=None
    )


def _conv_branched_history() -> dict:
    """7. Branched history — extra nodes exist off the final path."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0 + 600),
        "msg-1": _node(
            "msg-1", "root", ["msg-2a", "msg-2b"], "user", _text_content("What's 1 + 1?"), T0 + 601
        ),
        # edited branch (not on final path)
        "msg-2a": _node(
            "msg-2a", "msg-1", [], "assistant", _text_content("One plus one is eleven."), T0 + 602
        ),
        # final path
        "msg-2b": _node("msg-2b", "msg-1", [], "assistant", _text_content("1 + 1 = 2."), T0 + 603),
    }
    return _conv("conv-branched-007", "Branched History", mapping, "msg-2b", T0 + 600)


def _conv_thoughts() -> dict:
    """8. Thoughts / reasoning content type with multi-paragraph text."""
    multiline = "First line of reasoning.\n\nSecond paragraph.\n\nThird paragraph."
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0 + 700),
        "msg-1": _node(
            "msg-1",
            "root",
            ["msg-2"],
            "user",
            _text_content("Solve this step by step: 17 * 13"),
            T0 + 701,
        ),
        "msg-2": _node(
            "msg-2",
            "msg-1",
            ["msg-3"],
            "assistant",
            {"content_type": "thoughts", "text": multiline},
            T0 + 702,
        ),
        "msg-3": _node("msg-3", "msg-2", [], "assistant", _text_content("17 * 13 = 221"), T0 + 703),
    }
    return _conv("conv-thoughts-008", "Reasoning Example", mapping, "msg-3", T0 + 700)


def _conv_duplicate_id() -> dict:
    """9. Same ID as conv-plain-text-001 — exercises dedup warning path."""
    mapping = {
        "root": _node("root", None, ["msg-1"], "system", _text_content(""), T0 + 800),
        "msg-1": _node(
            "msg-1",
            "root",
            ["msg-2"],
            "user",
            _text_content("This conversation has a duplicate ID."),
            T0 + 801,
        ),
        "msg-2": _node("msg-2", "msg-1", [], "assistant", _text_content("So it does."), T0 + 802),
    }
    # Intentionally reuse conv-plain-text-001's ID
    return _conv("conv-plain-text-001", "Duplicate ID Conversation", mapping, "msg-2", T0 + 800)


def _conv_empty_mapping() -> dict:
    """10. Empty mapping — should be skipped with a reason."""
    return _conv(
        "conv-empty-mapping-010", "Empty Mapping", mapping={}, current_node="", create_time=T0 + 900
    )


# ---------------------------------------------------------------------------
# Zip builder
# ---------------------------------------------------------------------------


def build_export(output_path: Path) -> Path:
    """
    Write a synthetic ChatGPT export zip to output_path.
    Returns the path written.
    """
    conversations = [
        _conv_plain_text(),
        _conv_code_block(),
        _conv_image_attachment(),
        _conv_execution_output(),
        _conv_archived(),
        _conv_missing_timestamp(),
        _conv_branched_history(),
        _conv_thoughts(),
        _conv_duplicate_id(),  # duplicate ID — lands in same conversations.json
        _conv_empty_mapping(),
    ]

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Main conversations file
        zf.writestr("conversations.json", json.dumps(conversations, indent=2))

        # Minimal supporting files present in a real export
        zf.writestr("user.json", json.dumps({"id": "user-test-001", "email": "test@example.com"}))
        zf.writestr("chat.html", "<html><body>ChatGPT Export</body></html>")

        # Synthetic image asset referenced by conv #3
        # A 1x1 PNG (minimal valid PNG bytes)
        png_1x1 = (
            b"\x89PNG\r\n\x1a\n"  # PNG signature
            b"\x00\x00\x00\rIHDR"  # IHDR chunk length + type
            b"\x00\x00\x00\x01"  # width: 1
            b"\x00\x00\x00\x01"  # height: 1
            b"\x08\x02"  # bit depth 8, color type RGB
            b"\x00\x00\x00"  # compression, filter, interlace
            b"\x90wS\xde"  # IHDR CRC
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"  # IDAT chunk
            b"\x00\x00\x00\x01\x00\x05\x18\xd8N"  # IDAT data + CRC
            b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND chunk
        )
        zf.writestr("file-TESTASSET001-test.png", png_1x1)

    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("test-export.zip")
    build_export(dest)
    print(f"Written: {dest.resolve()}")
