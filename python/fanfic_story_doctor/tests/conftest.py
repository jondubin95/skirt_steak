"""Shared test setup. Tests never read a real DOCTOR_HOME."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_doctor_home(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("doctor-home")
    monkeypatch.setenv("DOCTOR_HOME", str(home))
    return home
