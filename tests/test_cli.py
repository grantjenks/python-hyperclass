import pytest

from hyperclass.__main__ import load, main


def test_load_application():
    app = load("examples.counter:app")
    assert app.title == "Hyperclass Counter"


def test_application_requires_module_and_attribute():
    with pytest.raises(ValueError, match="module:attribute"):
        load("examples.counter")


def test_main_runs_loaded_application(monkeypatch):
    app = load("examples.counter:app")
    called = {}

    def run(*, host, port):
        called.update(host=host, port=port)

    monkeypatch.setattr(app, "run", run)
    main(["examples.counter:app", "--host", "0.0.0.0", "--port", "9000"])
    assert called == {"host": "0.0.0.0", "port": 9000}
