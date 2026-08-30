"""Small Python values for authoring CSS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@dataclass(frozen=True)
class Unit:
    """A CSS unit which can be multiplied by a number."""

    suffix: str

    def __rmul__(self, value: int | float) -> Length:
        return Length(value, self)


@dataclass(frozen=True)
class Length:
    value: int | float
    unit: Unit

    def __str__(self) -> str:
        return f"{_number(self.value)}{self.unit.suffix}"


@dataclass(frozen=True)
class Color:
    name: str
    rgb: tuple[int, int, int] | None = None

    def __str__(self) -> str:
        return self.name

    def fade(self, alpha: float) -> AlphaColor:
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between 0 and 1")
        if self.rgb is None:
            return AlphaColor(self.name, alpha)
        red, green, blue = self.rgb
        return AlphaColor(f"{red} {green} {blue}", alpha, rgb=True)


@dataclass(frozen=True)
class AlphaColor:
    color: str
    alpha: float
    rgb: bool = False

    def __str__(self) -> str:
        if self.rgb:
            return f"rgb({self.color} / {_number(self.alpha)})"
        return f"color-mix(in srgb, {self.color} {self.alpha * 100:g}%, transparent)"


def css_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class Style:
    """An ordered collection of CSS declarations."""

    def __init__(self, **declarations: Any):
        self.declarations = tuple(
            (name.replace("_", "-"), value)
            for name, value in declarations.items()
            if value is not None
        )

    def render(self) -> str:
        return ";".join(
            f"{name}:{css_value(value)}" for name, value in self.declarations
        )

    def __str__(self) -> str:
        return self.render()


def css(**declarations: Any) -> Style:
    return Style(**declarations)


@dataclass(frozen=True)
class Media:
    """A stylesheet rule guarded by a CSS media query."""

    conditions: tuple[tuple[str, Any], ...]
    style: Style

    def query(self) -> str:
        return " and ".join(
            f"({name.replace('_', '-')}:{css_value(value)})"
            for name, value in self.conditions
        )


def media(
    *,
    min_width: Any = None,
    max_width: Any = None,
    orientation: str | None = None,
    prefers_color_scheme: str | None = None,
    **declarations: Any,
) -> Media:
    """Create a media rule with Python-named conditions and declarations."""

    conditions = tuple(
        (name, value)
        for name, value in (
            ("min_width", min_width),
            ("max_width", max_width),
            ("orientation", orientation),
            ("prefers_color_scheme", prefers_color_scheme),
        )
        if value is not None
    )
    if not conditions:
        raise ValueError("media requires at least one condition")
    return Media(conditions, css(**declarations))


PSEUDO_STATES = {
    "active",
    "checked",
    "disabled",
    "focus",
    "focus_visible",
    "focus_within",
    "hover",
    "invalid",
    "visited",
}


px = Unit("px")
rem = Unit("rem")
em = Unit("em")
percent = Unit("%")
vh = Unit("vh")
vw = Unit("vw")

orange = Color("orange", (255, 165, 0))

grid = "grid"
flex = "flex"
block = "block"
inline = "inline"
none = "none"
pointer = "pointer"
