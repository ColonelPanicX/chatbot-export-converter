"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.make_fixture import build_export


@pytest.fixture(scope="session")
def sample_export_zip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped synthetic ChatGPT export zip."""
    dest = tmp_path_factory.mktemp("fixtures") / "test-export.zip"
    return build_export(dest)
