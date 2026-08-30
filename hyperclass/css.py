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
