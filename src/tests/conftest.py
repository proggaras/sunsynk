"""Global fixtures."""

import sys
from importlib import import_module as _import_module
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

from sunsynk.state import InverterState

#
# Pytest Mark: https://stackoverflow.com/a/61193490
#

MARKERS = ("mqtt",)


def pytest_addoption(parser: Any) -> None:
    """Support command line marks."""
    for mrk in MARKERS:
        parser.addoption(
            f"--{mrk}", action="store_true", help=f"include the {mrk} tests"
        )


def pytest_configure(config: Any) -> None:
    """Enable configuration."""
    for mrk in MARKERS:
        config.addinivalue_line("markers", f"{mrk}: include the {mrk} tests")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip tests."""
    for mrk in MARKERS:
        if not config.getoption(f"--{mrk}", None):
            skip_mrk = pytest.mark.skip(reason=f"need --{mrk} option to run")
            for item in items:
                if mrk in item.keywords:
                    item.add_marker(skip_mrk)


def import_module(mod_name: str, folder: str) -> ModuleType:
    """import_module."""
    here = Path.cwd() / folder
    sys.path.insert(0, str(here))
    try:
        mod_obj = _import_module(mod_name)
        return mod_obj
    finally:
        sys.path.pop(0)


@pytest.fixture
def state() -> InverterState:
    """Sunsynk inverter state."""
    return InverterState(onchange=MagicMock())
