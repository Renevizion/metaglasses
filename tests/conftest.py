"""Shared pytest fixtures for the metaglasses test suite."""

import pytest

from metaglasses.glasses import Glasses


@pytest.fixture
def connected_glasses() -> Glasses:
    """Return an already-connected Glasses instance."""
    g = Glasses()
    g.connect()
    return g
