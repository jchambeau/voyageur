"""Shared fixtures for all test modules."""
import datetime

import pytest

UTC = datetime.timezone.utc


@pytest.fixture
def now() -> datetime.datetime:
    """A fixed UTC datetime for use in tests."""
    return datetime.datetime(2026, 3, 29, 8, 0, tzinfo=UTC)
