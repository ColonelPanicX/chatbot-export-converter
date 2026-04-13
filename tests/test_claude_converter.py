"""Tests for claude_converter module."""

from __future__ import annotations

import json
import re
from pathlib import Path

from chatbot_export_converter.claude_converter import (
    _render_thinking_block,
    _render_tool_result_block,
    _render_tool_use_block,
    choose_main_path,
    conversation_id,
    date_from_iso,
    detect_claude_export,
    dump_yaml_front_matter,
    load_conversations,
    render_conversation,
    render_message,
    run_conversion,
    safe_title,
)
from chatbot_export_converter.converter import Summary

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_ROOT = "00000000-0000-4000-8000-000000000000"


def _msg(uid: str, sender: str, content: list, parent: str = _ROOT) -> dict:
    return {
        "uuid": uid,
        "sender": sender,
        "content": content,
        "parent_message_uuid": parent,
        "attachments": [],
        "files": [],
    }


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _simple_conv(uid: str = "conv-1", messages: list | None = None) -> dict:
    if messages is None:
        messages = [
            _msg("m1", "human", [_text_block("Hello")]),
            _msg("m2", "assistant", [_text_block("Hi there")], parent="m1"),
        ]
    return {
        "uuid": uid,
        "name": "Test Conversation",
        "created_at": "2025-09-24T12:00:00+00:00",
        "updated_at": "2025-09-24T12:01:00+00:00",
        "chat_messages": messages,
    }


# ---------------------------------------------------------------------------
# detect_claude_export
# ---------------------------------------------------------------------------


class TestDetectClaudeExport:
    def test_returns_true_for_claude_export(self, tmp_path: Path) -> None:
        conversations = [{"uuid": "x", "chat_messages": []}]
        (tmp_path / "conversations.json").write_text(json.dumps(conversations))
        assert detect_claude_export(tmp_path) is True

    def test_returns_false_for_chatgpt_export(self, tmp_path: Path) -> None:
        conversations = [{"uuid": "x", "mapping": {}}]
        (tmp_path / "conversations.json").write_text(json.dumps(conversations))
        assert detect_claude_export(tmp_path) is False

    def test_returns_false_when_no_file(self, tmp_path: Path) -> None:
        assert detect_claude_export(tmp_path) is False

    def test_returns_false_for_empty_list(self, tmp_path: Path) -> None:
        (tmp_path / "conversations.json").write_text("[]")
        assert detect_claude_export(tmp_path) is False

    def test_returns_false_for_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "conversations.json").write_text("not json")
        assert detect_claude_export(tmp_path) is False


# ---------------------------------------------------------------------------
# load_conversations
# ---------------------------------------------------------------------------


class TestLoadConversations:
    def test_loads_list(self, tmp_path: Path) -> None:
        data = [_simple_conv("a"), _simple_conv("b")]
        (tmp_path / "conversations.json").write_text(json.dumps(data))
        result = load_conversations(tmp_path)
        assert len(result) == 2

    def test_skips_non_dicts(self, tmp_path: Path) -> None:
        data = [_simple_conv(), "not-a-dict", 42]
        (tmp_path / "conversations.json").write_text(json.dumps(data))
        result = load_conversations(tmp_path)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# conversation_id / safe_title / date_from_iso
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_conversation_id_returns_uuid(self) -> None:
        assert conversation_id({"uuid": "abc-123"}) == "abc-123"

    def test_conversation_id_fallback(self) -> None:
        assert conversation_id({}) == "unknown-id"

    def test_safe_title_basic(self) -> None:
        assert safe_title("Hello World") == "hello-world"

    def test_safe_title_strips_special_chars(self) -> None:
        result = safe_title("My Convo: #1!")
        assert re.match(r"^[a-z0-9-]+$", result)

    def test_safe_title_empty_becomes_untitled(self) -> None:
        assert safe_title("") == "untitled"

    def test_safe_title_truncates_at_80(self) -> None:
        assert len(safe_title("x" * 200)) <= 80

    def test_date_from_iso_parses_correctly(self) -> None:
        assert date_from_iso("2025-09-24T12:00:00+00:00") == "2025-09-24"

    def test_date_from_iso_zulu(self) -> None:
        assert date_from_iso("2025-09-24T12:00:00Z") == "2025-09-24"

    def test_date_from_iso_bad_value(self) -> None:
        assert date_from_iso("not-a-date") == "undated"

    def test_date_from_iso_none(self) -> None:
        assert date_from_iso(None) == "undated"


# ---------------------------------------------------------------------------
# choose_main_path
# ---------------------------------------------------------------------------


class TestChooseMainPath:
    def test_empty_returns_empty(self) -> None:
        path, branched = choose_main_path([])
        assert path == []
        assert branched is False

    def test_linear_chain(self) -> None:
        msgs = [
            _msg("m1", "human", [], parent=_ROOT),
            _msg("m2", "assistant", [], parent="m1"),
            _msg("m3", "human", [], parent="m2"),
        ]
        path, branched = choose_main_path(msgs)
        uids = [m["uuid"] for m in path]
        assert uids == ["m1", "m2", "m3"]
        assert branched is False

    def test_branched_follows_longest(self) -> None:
        # m1 -> m2a (dead end) | m2b -> m3 -> m4 (longer)
        msgs = [
            _msg("m1", "human", [], parent=_ROOT),
            _msg("m2a", "assistant", [], parent="m1"),
            _msg("m2b", "assistant", [], parent="m1"),
            _msg("m3", "human", [], parent="m2b"),
            _msg("m4", "assistant", [], parent="m3"),
        ]
        path, branched = choose_main_path(msgs)
        uids = [m["uuid"] for m in path]
        assert "m2b" in uids
        assert "m2a" not in uids
        assert branched is True

    def test_had_branches_true_when_fork_exists(self) -> None:
        msgs = [
            _msg("m1", "human", [], parent=_ROOT),
            _msg("m2a", "assistant", [], parent="m1"),
            _msg("m2b", "assistant", [], parent="m1"),
        ]
        _, branched = choose_main_path(msgs)
        assert branched is True


# ---------------------------------------------------------------------------
# Content block rendering
# ---------------------------------------------------------------------------


class TestRenderThinkingBlock:
    def test_renders_details_element(self) -> None:
        block = {"type": "thinking", "thinking": "I am reasoning."}
        result = _render_thinking_block(block)
        assert "<details>" in result
        assert "I am reasoning." in result

    def test_empty_thinking_returns_empty_string(self) -> None:
        assert _render_thinking_block({"type": "thinking", "thinking": ""}) == ""
        assert _render_thinking_block({"type": "thinking"}) == ""


class TestRenderToolUseBlock:
    def test_renders_named_tool(self) -> None:
        block = {"type": "tool_use", "name": "bash", "input": {"cmd": "ls"}}
        result = _render_tool_use_block(block)
        assert "**[Tool: bash]**" in result

    def test_repl_tool_shows_code_block(self) -> None:
        block = {"type": "tool_use", "name": "repl", "input": {"code": "print('hi')"}}
        result = _render_tool_use_block(block)
        assert "```" in result
        assert "print('hi')" in result

    def test_dict_input_rendered_as_json(self) -> None:
        block = {"type": "tool_use", "name": "lookup", "input": {"key": "val"}}
        result = _render_tool_use_block(block)
        assert "```json" in result
        assert '"key"' in result


class TestRenderToolResultBlock:
    def test_renders_result_with_text(self) -> None:
        block = {
            "type": "tool_result",
            "name": "bash",
            "is_error": False,
            "content": [{"type": "text", "text": "output here"}],
        }
        result = _render_tool_result_block(block)
        assert "**[Tool result: bash]**" in result
        assert "output here" in result

    def test_error_flag_shown(self) -> None:
        block = {
            "type": "tool_result",
            "name": "bash",
            "is_error": True,
            "content": [{"type": "text", "text": "error msg"}],
        }
        result = _render_tool_result_block(block)
        assert "⚠ error" in result

    def test_empty_content_returns_label_only(self) -> None:
        block = {"type": "tool_result", "name": "bash", "is_error": False, "content": []}
        result = _render_tool_result_block(block)
        assert "**[Tool result: bash]**" in result
        assert "```" not in result

    def test_truncates_long_output(self) -> None:
        long_text = "x" * 3000
        block = {
            "type": "tool_result",
            "name": "bash",
            "is_error": False,
            "content": [{"type": "text", "text": long_text}],
        }
        result = _render_tool_result_block(block)
        assert "…" in result
        # Content section should not exceed max + some overhead
        assert len(result) < 3000


# ---------------------------------------------------------------------------
# render_message
# ---------------------------------------------------------------------------


class TestRenderMessage:
    def test_human_heading(self) -> None:
        msg = _msg("m1", "human", [_text_block("Hello")])
        assert render_message(msg, False).startswith("## You")

    def test_assistant_heading(self) -> None:
        msg = _msg("m2", "assistant", [_text_block("Hi")])
        assert render_message(msg, False).startswith("## Claude")

    def test_text_block_rendered(self) -> None:
        msg = _msg("m1", "human", [_text_block("My question here")])
        assert "My question here" in render_message(msg, False)

    def test_thinking_block_rendered(self) -> None:
        msg = _msg("m2", "assistant", [{"type": "thinking", "thinking": "deep thought"}])
        result = render_message(msg, False)
        assert "<details>" in result

    def test_tool_use_skipped_by_default(self) -> None:
        block = {"type": "tool_use", "name": "bash", "input": {}}
        msg = _msg("m2", "assistant", [block])
        result = render_message(msg, include_tool_blocks=False)
        assert "Tool:" not in result
        assert "*(empty)*" in result

    def test_tool_use_included_when_flag_set(self) -> None:
        block = {"type": "tool_use", "name": "bash", "input": {}}
        msg = _msg("m2", "assistant", [block])
        result = render_message(msg, include_tool_blocks=True)
        assert "**[Tool: bash]**" in result

    def test_token_budget_always_skipped(self) -> None:
        msg = _msg("m2", "assistant", [{"type": "token_budget", "remaining": 500}])
        result = render_message(msg, include_tool_blocks=True)
        assert "token_budget" not in result
        assert "*(empty)*" in result

    def test_attachment_with_content(self) -> None:
        msg = _msg("m1", "human", [])
        msg["attachments"] = [{"file_name": "notes.md", "extracted_content": "Some notes"}]
        result = render_message(msg, False)
        assert "notes.md" in result
        assert "Some notes" in result

    def test_attachment_without_content(self) -> None:
        msg = _msg("m1", "human", [])
        msg["attachments"] = [{"file_name": "binary.bin", "extracted_content": ""}]
        result = render_message(msg, False)
        assert "binary.bin" in result

    def test_file_reference_shown(self) -> None:
        msg = _msg("m1", "human", [])
        msg["files"] = [{"file_name": "data.csv"}]
        result = render_message(msg, False)
        assert "data.csv" in result
        assert "content not included" in result

    def test_empty_content_shows_placeholder(self) -> None:
        msg = _msg("m2", "assistant", [])
        assert "*(empty)*" in render_message(msg, False)

    def test_multiple_text_blocks_all_rendered(self) -> None:
        msg = _msg(
            "m2",
            "assistant",
            [
                _text_block("First part."),
                _text_block("Second part."),
            ],
        )
        result = render_message(msg, False)
        assert "First part." in result
        assert "Second part." in result


# ---------------------------------------------------------------------------
# dump_yaml_front_matter
# ---------------------------------------------------------------------------


class TestDumpYamlFrontMatter:
    def test_contains_required_fields(self) -> None:
        conv = _simple_conv()
        result = dump_yaml_front_matter(conv)
        assert "title:" in result
        assert "conversation_id:" in result
        assert "created_at:" in result
        assert "updated_at:" in result
        assert 'source: "claude-data-export"' in result

    def test_fenced_with_triple_dashes(self) -> None:
        result = dump_yaml_front_matter(_simple_conv())
        assert result.startswith("---\n")
        assert "\n---\n" in result

    def test_title_with_quotes_escaped(self) -> None:
        conv = _simple_conv()
        conv["name"] = 'Say "hello"'
        result = dump_yaml_front_matter(conv)
        assert '\\"hello\\"' in result


# ---------------------------------------------------------------------------
# render_conversation
# ---------------------------------------------------------------------------


class TestRenderConversation:
    def test_creates_chat_dir(self, tmp_path: Path) -> None:
        conv = _simple_conv()
        output = tmp_path / "output"
        summary = Summary()
        render_conversation(conv, output, summary, dry_run=False, include_tool_blocks=False)
        dirs = list(output.iterdir())
        assert len(dirs) == 1
        assert (dirs[0] / "transcript.md").exists()
        assert (dirs[0] / "metadata.json").exists()

    def test_increments_summary_processed(self, tmp_path: Path) -> None:
        summary = Summary()
        render_conversation(
            _simple_conv(), tmp_path / "out", summary, dry_run=False, include_tool_blocks=False
        )
        assert summary.conversations_processed == 1

    def test_dry_run_no_files(self, tmp_path: Path) -> None:
        summary = Summary()
        render_conversation(
            _simple_conv(), tmp_path / "out", summary, dry_run=True, include_tool_blocks=False
        )
        assert not (tmp_path / "out").exists()
        assert summary.conversations_processed == 1

    def test_skips_conversation_with_no_messages(self, tmp_path: Path) -> None:
        conv = _simple_conv(messages=[])
        summary = Summary()
        render_conversation(
            conv, tmp_path / "out", summary, dry_run=False, include_tool_blocks=False
        )
        assert summary.conversations_processed == 0
        assert len(summary.skipped) == 1

    def test_transcript_contains_messages(self, tmp_path: Path) -> None:
        conv = _simple_conv()
        output = tmp_path / "output"
        summary = Summary()
        render_conversation(conv, output, summary, dry_run=False, include_tool_blocks=False)
        chat_dir = next(output.iterdir())
        transcript = (chat_dir / "transcript.md").read_text()
        assert "Hello" in transcript
        assert "Hi there" in transcript

    def test_transcript_has_front_matter(self, tmp_path: Path) -> None:
        output = tmp_path / "output"
        summary = Summary()
        render_conversation(
            _simple_conv(), output, summary, dry_run=False, include_tool_blocks=False
        )
        chat_dir = next(output.iterdir())
        transcript = (chat_dir / "transcript.md").read_text()
        assert transcript.startswith("---\n")

    def test_folder_name_includes_date_and_id(self, tmp_path: Path) -> None:
        conv = _simple_conv(uid="my-uuid-1234")
        output = tmp_path / "out"
        summary = Summary()
        render_conversation(conv, output, summary, dry_run=False, include_tool_blocks=False)
        chat_dir = next(output.iterdir())
        assert "my-uuid-1234" in chat_dir.name
        assert "2025-09-24" in chat_dir.name

    def test_metadata_json_structure(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        summary = Summary()
        render_conversation(
            _simple_conv(), output, summary, dry_run=False, include_tool_blocks=False
        )
        chat_dir = next(output.iterdir())
        meta = json.loads((chat_dir / "metadata.json").read_text())
        assert "conversation_id" in meta
        assert "stats" in meta
        assert "messages_in_path" in meta["stats"]

    def test_branched_note_in_transcript(self, tmp_path: Path) -> None:
        messages = [
            _msg("m1", "human", [_text_block("Q")], parent=_ROOT),
            _msg("m2a", "assistant", [_text_block("A1")], parent="m1"),
            _msg("m2b", "assistant", [_text_block("A2")], parent="m1"),
            _msg("m3", "human", [_text_block("Follow up")], parent="m2b"),
            _msg("m4", "assistant", [_text_block("Final")], parent="m3"),
        ]
        conv = _simple_conv(messages=messages)
        output = tmp_path / "out"
        summary = Summary()
        render_conversation(conv, output, summary, dry_run=False, include_tool_blocks=False)
        chat_dir = next(output.iterdir())
        transcript = (chat_dir / "transcript.md").read_text()
        assert "branched" in transcript.lower()


# ---------------------------------------------------------------------------
# run_conversion
# ---------------------------------------------------------------------------


class TestRunConversion:
    def _write_conversations(self, tmp_path: Path, data: list) -> Path:
        input_dir = tmp_path / "export"
        input_dir.mkdir()
        (input_dir / "conversations.json").write_text(json.dumps(data))
        return input_dir

    def test_converts_multiple_conversations(self, tmp_path: Path) -> None:
        convs = [_simple_conv("c1"), _simple_conv("c2"), _simple_conv("c3")]
        input_dir = self._write_conversations(tmp_path, convs)
        output_dir = tmp_path / "output"
        summary = Summary()
        total = run_conversion(
            input_dir, output_dir, summary, dry_run=False, include_tool_blocks=False
        )
        assert total == 3
        assert summary.conversations_processed == 3
        assert len(list(output_dir.iterdir())) == 3

    def test_returns_total_count(self, tmp_path: Path) -> None:
        convs = [_simple_conv("x1"), _simple_conv("x2")]
        input_dir = self._write_conversations(tmp_path, convs)
        summary = Summary()
        total = run_conversion(
            input_dir, tmp_path / "out", summary, dry_run=False, include_tool_blocks=False
        )
        assert total == 2

    def test_dry_run_no_output(self, tmp_path: Path) -> None:
        input_dir = self._write_conversations(tmp_path, [_simple_conv()])
        output_dir = tmp_path / "output"
        summary = Summary()
        run_conversion(input_dir, output_dir, summary, dry_run=True, include_tool_blocks=False)
        assert not output_dir.exists()

    def test_empty_conversations_skipped(self, tmp_path: Path) -> None:
        convs = [_simple_conv(messages=[]), _simple_conv("c2")]
        input_dir = self._write_conversations(tmp_path, convs)
        summary = Summary()
        run_conversion(
            input_dir, tmp_path / "out", summary, dry_run=False, include_tool_blocks=False
        )
        assert summary.conversations_processed == 1
        assert len(summary.skipped) == 1
