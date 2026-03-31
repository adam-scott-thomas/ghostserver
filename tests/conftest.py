import pytest
from spine import Core


@pytest.fixture(autouse=True)
def reset_spine():
    """Reset spine singleton between every test."""
    Core._reset_instance()
    yield
    Core._reset_instance()
