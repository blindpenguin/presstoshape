import pytest

from veccy.editing import registry


@pytest.fixture
def clean_registry(monkeypatch):
    monkeypatch.setattr(registry, "_OPERATIONS", {})


def test_registration_order_and_lookup(clean_registry):
    registry.register("test.b", "&B", lambda session: None)

    @registry.operation("test.a", "&A")
    def run_a(session):
        pass

    assert [entry.id for entry in registry.operations()] == ["test.b", "test.a"]
    assert registry.find("test.a").run is run_a


def test_duplicate_id_raises(clean_registry):
    registry.register("test.a", "&A", lambda session: None)
    with pytest.raises(ValueError):
        registry.register("test.a", "&A again", lambda session: None)


def test_invoke_respects_can_run(clean_registry, session):
    calls = []
    entry = registry.register("test.a", "&A", lambda s: calls.append(1), can_run=lambda s: bool(s.state.selection))
    entry.invoke(session)
    assert calls == []
    session.state.selection = {1}
    entry.invoke(session)
    assert calls == [1]


def test_decorator_returns_plain_function(clean_registry):
    @registry.operation("test.a", "&A")
    def run_a(session):
        return "ran"

    assert run_a(None) == "ran"
