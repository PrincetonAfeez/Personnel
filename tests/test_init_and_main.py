"""Tests for ``personnel`` package surface and ``personnel.__main__``."""

from __future__ import annotations

import importlib
import runpy
from unittest.mock import patch

import personnel


def test_package_all_exports_are_importable() -> None:
    for name in personnel.__all__:
        assert hasattr(personnel, name), f"missing export: {name}"
        assert getattr(personnel, name) is not None


def test_package_docstring_present() -> None:
    assert "Vault OS" in (personnel.__doc__ or "")


def test_run_module_main_invokes_run_cli() -> None:
    with patch("personnel.cli.run_cli") as mock_run:
        runpy.run_module("personnel.__main__", run_name="__main__")
    mock_run.assert_called_once()


def test_main_module_importable() -> None:
    mod = importlib.import_module("personnel.__main__")
    assert hasattr(mod, "run_cli")
