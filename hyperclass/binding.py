"""Bind form-like multidicts to typed dataclasses."""

from __future__ import annotations

import inspect
from collections.abc import Iterator, Mapping
from dataclasses import MISSING, fields, is_dataclass
from types import UnionType
from typing import Any, Protocol, Union, get_args, get_origin, get_type_hints


class MultiValues(Protocol):
    def getlist(self, key: Any) -> list[Any]: ...


class Values(Mapping[str, str]):
    def __init__(self, values: Mapping[str, list[str]] | None = None):
        self._values = dict(values or {})

    def __getitem__(self, key: Any) -> str:
        return self._values[str(key)][-1]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def get(self, key: Any, default: Any = None) -> Any:
        values = self._values.get(str(key))
        return values[-1] if values else default

    def getlist(self, key: Any) -> list[str]:
        return list(self._values.get(str(key), ()))

    def int(self, key: Any, default: int | None = None) -> int:
        value = self.get(key)
        if value is None:
            if default is not None:
                return default
            raise ValueError(f"missing integer form value: {key}")
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(
                f"invalid integer form value for {key}: {value!r}"
            ) from error

    def bind(self, model: type[Any]) -> Any:
        return bind(self, model)


def bind(values: MultiValues, model: type[Any]) -> Any:
    """Build a dataclass from any Werkzeug/Django-style multidict."""

    if not isinstance(model, type) or not is_dataclass(model):
        raise TypeError("values can only bind to a dataclass type")
    hints = get_type_hints(model)
    arguments: dict[str, Any] = {}
    for field in fields(model):
        annotation = hints.get(field.name, field.type)
        raw = [str(value) for value in values.getlist(field.name)]
        if not raw:
            if field.default is not MISSING or field.default_factory is not MISSING:
                continue
            if _optional(annotation):
                arguments[field.name] = None
            elif annotation is bool:
                arguments[field.name] = False
            else:
                raise ValueError(f"missing form value: {field.name}")
            continue
        try:
            arguments[field.name] = _convert_values(raw, annotation)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"invalid form value for {field.name}: {raw[-1]!r}"
            ) from error
    return model(**arguments)


def _optional(annotation: Any) -> bool:
    return get_origin(annotation) in (Union, UnionType) and type(None) in get_args(
        annotation
    )


def _convert_values(values: list[str], annotation: Any) -> Any:
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (list, tuple):
        item_type = arguments[0] if arguments else str
        converted = [_convert_value(value, item_type) for value in values]
        return converted if origin is list else tuple(converted)
    if _optional(annotation):
        item_type = next(value for value in arguments if value is not type(None))
        return None if values[-1] == "" else _convert_value(values[-1], item_type)
    return _convert_value(values[-1], annotation)


def _convert_value(value: str, annotation: Any) -> Any:
    if annotation in (Any, inspect.Parameter.empty, str):
        return value
    if annotation is bool:
        normalized = value.lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        raise ValueError(value)
    if annotation in (int, float):
        return annotation(value)
    raise TypeError(f"unsupported form type: {annotation!r}")


__all__ = ["MultiValues", "Values", "bind"]
