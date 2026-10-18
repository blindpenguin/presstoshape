import pytest

from veccy.editing.session import Session


@pytest.fixture
def session() -> Session:
    return Session()
