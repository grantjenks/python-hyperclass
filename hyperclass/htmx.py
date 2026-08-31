"""Python objects for htmx 4 attributes and extended selectors."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
import json
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
    def __init__(self, values: Mapping[str, Any], *, extensions: tuple[str, ...] = ()):
        self.values = dict(values)
        self.extensions = extensions

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __or__(self, other: Mapping[str, Any]) -> Attributes:
        values = {**self.values, **dict(other)}
        extensions = tuple(
            dict.fromkeys((*self.extensions, *getattr(other, "extensions", ())))
        )
        return Attributes(values, extensions=extensions)

    def __ror__(self, other: Mapping[str, Any]) -> Attributes:
        return Attributes(other) | self


def _option_name(value: str) -> str:
    return f"hx-{value.rstrip('_').replace('_', '-')}"


class HtmxAttribute:
    def __init__(self, *parts: str):
        self.parts = parts

    def __getattr__(self, name: str) -> HtmxAttribute:
        if name.startswith("_"):
            raise AttributeError(name)
        return HtmxAttribute(*self.parts, name)

    def __call__(self, value: Any = True) -> Attributes:
        root, *modifiers = self.parts
        extension = ("sse",) if root == "sse" else ()
        if root == "on":
            suffix = ":".join(part.replace("_", ":") for part in modifiers)
            attribute = f"hx-on::{suffix}"
        else:
            attribute = _option_name(root)
            if modifiers:
                attribute += ":" + ":".join(
                    part.rstrip("_").replace("_", "-") for part in modifiers
                )
        if isinstance(value, Mapping):
            value = json.dumps(value, separators=(",", ":"))
        return Attributes({attribute: value}, extensions=extension)


class Htmx:
    def __getattr__(self, name: str) -> HtmxAttribute:
        if name.startswith("_"):
            raise AttributeError(name)
        return HtmxAttribute(name)

    def request(self, method: str, url: Any, **options: Any) -> Attributes:
        stream = bool(options.pop("stream", False))
        route_url = getattr(url, "url", None)
        route_parameters = getattr(url, "parameters", None)
        if callable(route_url) and callable(route_parameters):
            parameters = {
                name: options.pop(name)
                for name in route_parameters(method)
                if name in options
            }
            query = options.pop("query", None)
            url = route_url(method=method, query=query, **parameters)
        values: dict[str, Any] = {f"hx-{method.lower()}": url}
        for name, value in options.items():
            if value is None:
                continue
            if name in {
                "disable",
                "include",
                "target",
                "select",
                "select_oob",
                "sync",
            }:
                value = selector(value) if not isinstance(value, Target) else value
            values[_option_name(name)] = value
        return Attributes(values, extensions=("sse",) if stream else ())

    def get(self, url: Any, **options: Any) -> Attributes:
        return self.request("get", url, **options)

    def post(self, url: Any, **options: Any) -> Attributes:
        return self.request("post", url, **options)

    def put(self, url: Any, **options: Any) -> Attributes:
        return self.request("put", url, **options)

    def patch(self, url: Any, **options: Any) -> Attributes:
        return self.request("patch", url, **options)

    def delete(self, url: Any, **options: Any) -> Attributes:
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
