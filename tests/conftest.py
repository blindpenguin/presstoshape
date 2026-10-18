import pytest

from presstoshape.editing.session import Session


@pytest.fixture
def session() -> Session:
    return Session()
