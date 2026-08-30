"""Python objects for htmx 4 attributes and extended selectors."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from .html import selector


class Target:
    def __init__(self, value: str):
        self.value = value

    def __str__(self) -> str:
        return self.value


def closest(value: Any) -> Target:
    return Target(f"closest {selector(value)}")


def find(value: Any) -> Target:
    return Target(f"find {selector(value)}")


def next(value: Any | None = None) -> Target:
    return Target("next" if value is None else f"next {selector(value)}")


def previous(value: Any | None = None) -> Target:
    return Target("previous" if value is None else f"previous {selector(value)}")


class Attributes(Mapping[str, Any]):
    def __init__(self, values: Mapping[str, Any]):
        self.values = dict(values)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def _option_name(value: str) -> str:
    return f"hx-{value.rstrip('_').replace('_', '-')}"


class Htmx:
    def request(self, method: str, url: str, **options: Any) -> Attributes:
        values: dict[str, Any] = {f"hx-{method.lower()}": url}
        for name, value in options.items():
            if value is None:
                continue
            if name in {"target", "select", "select_oob", "sync"}:
                value = selector(value) if not isinstance(value, Target) else value
            values[_option_name(name)] = value
        return Attributes(values)

    def get(self, url: str, **options: Any) -> Attributes:
        return self.request("get", url, **options)

    def post(self, url: str, **options: Any) -> Attributes:
        return self.request("post", url, **options)

    def put(self, url: str, **options: Any) -> Attributes:
        return self.request("put", url, **options)

    def patch(self, url: str, **options: Any) -> Attributes:
        return self.request("patch", url, **options)

    def delete(self, url: str, **options: Any) -> Attributes:
        return self.request("delete", url, **options)

    def query(self, url: str, **options: Any) -> Attributes:
        return self.request("query", url, **options)

    def action(self, url: str, method: str = "GET", **options: Any) -> Attributes:
        values = {"hx-action": url, "hx-method": method.upper()}
        values.update(self.request("action-options", "", **options).values)
        values.pop("hx-action-options")
        return Attributes(values)


hx = Htmx()

inner_html = "innerHTML"
outer_html = "outerHTML"
outer_sync = "outerSync"
inner_morph = "innerMorph"
outer_morph = "outerMorph"
before = "before"
prepend = "prepend"
append = "append"
after = "after"
delete = "delete"
