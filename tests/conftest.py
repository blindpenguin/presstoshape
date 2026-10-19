import pytest

from presstoshape import i18n
from presstoshape.editing.session import Session
from presstoshape.i18n.catalog import Catalog
from presstoshape.i18n.languages import SHIPPED_FOLDER, Language, load_catalog


@pytest.fixture(autouse=True)
def english():
    """Every test starts in English (the source texts), whatever a previous test installed."""
    i18n.install(Catalog("en"))
    yield
    i18n.install(Catalog("en"))


@pytest.fixture
def german():
    i18n.install(load_catalog(Language("de", shipped=SHIPPED_FOLDER / "de.po")))


@pytest.fixture
def session() -> Session:
    return Session()
