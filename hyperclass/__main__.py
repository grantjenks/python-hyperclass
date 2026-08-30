"""Run a Hyperclass WSGI application."""

from __future__ import annotations

import argparse
from importlib import import_module
from typing import Any


def load(target: str) -> Any:
    try:
        module_name, attribute_path = target.split(":", 1)
    except ValueError as error:
        raise ValueError("application must be written as module:attribute") from error
    value: Any = import_module(module_name)
    for name in attribute_path.split("."):
        value = getattr(value, name)
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m hyperclass")
    parser.add_argument("application", help="WSGI application as module:attribute")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args(argv)
    app = load(options.application)
    try:
        run = app.run
    except AttributeError as error:
        parser.error(f"{options.application} is not a Hyperclass application")
        raise AssertionError from error
    run(host=options.host, port=options.port)


if __name__ == "__main__":
    main()
