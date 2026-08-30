"""HTML elements, semantic subclasses, rendering, and pages."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from html import escape
from typing import Any

from .css import Style

HTMX_SRC = "https://cdn.jsdelivr.net/npm/htmx.org@4.0.0"
HTMX_INTEGRITY = (
    "sha384-BvJpBiO8Kh31EqtJe5DRIeWrHWnCGkwytKs9NKFi86Hhw96dEqdEMzZDeK9iEGTc"
)


def class_name(value: type) -> str:
    return value.__name__.replace("_", "-")


class ElementMeta(type):
    @property
    def selector(cls) -> str:
        return selector(cls)

    def __str__(cls) -> str:
        return selector(cls)


def _tag_class(value: type) -> bool:
    return bool(value.__dict__.get("_is_tag", False))


def _tag_for(value: type) -> str:
    for ancestor in value.__mro__:
        if _tag_class(ancestor):
            return ancestor.__dict__["_tag"]
    raise TypeError(f"{value.__name__} does not inherit from an HTML element")


def semantic_classes(value: type) -> tuple[type, ...]:
    """Return semantic classes in base-to-derived declaration order."""

    found: list[type] = []
    seen: set[type] = set()

    def visit(current: type) -> None:
        if current in seen or current in (object, element):
            return
        seen.add(current)
        for base in current.__bases__:
            visit(base)
        if not _tag_class(current):
            found.append(current)

    visit(value)
    return tuple(found)


def selector(value: Any) -> str:
    """Turn a selector string, element class, or element instance into CSS."""

    if isinstance(value, str):
        return value
    if isinstance(value, element):
        identity = getattr(value, "_attrs", {}).get("id")
        if identity:
            return f"#{identity}"
        return selector(type(value))
    if isinstance(value, type):
        if _tag_class(value):
            return value.__dict__["_tag"]
        return f".{class_name(value)}"
    raise TypeError(f"cannot use {value!r} as a selector")


@dataclass(frozen=True)
class Markup:
    value: str


def markup(value: str) -> Markup:
    """Mark trusted HTML so it is not escaped during rendering."""

    return Markup(value)


class RenderContext:
    def __init__(self) -> None:
        self.styled_classes: list[type] = []
        self._seen_styles: set[type] = set()

    def register(self, value: type) -> None:
        if value in self._seen_styles:
            return
        style = value.__dict__.get("style")
        if isinstance(style, Style):
            self._seen_styles.add(value)
            self.styled_classes.append(value)

    def stylesheet(self) -> str:
        return "".join(
            f".{class_name(value)}{{{value.__dict__['style'].render()}}}"
            for value in self.styled_classes
        )


def _attribute_name(name: str) -> str:
    if name.endswith("_"):
        name = name[:-1]
    return name.replace("_", "-")


def _attribute_value(value: Any) -> str:
    if isinstance(value, Style):
        return value.render()
    if isinstance(value, type) or isinstance(value, element):
        return selector(value)
    return str(value)


class element(metaclass=ElementMeta):
    """Base class for all rendered HTML elements."""

    def __init__(self, *children: Any, **attributes: Any):
        self._children = children
        self._attrs: dict[str, Any] = {}
        for name, value in attributes.items():
            if name == "hx" and isinstance(value, Mapping):
                self._attrs.update(value)
            else:
                self._attrs[_attribute_name(name)] = value

    @property
    def selector(self) -> str:
        return selector(self)

    def content(self) -> Iterable[Any]:
        return getattr(self, "_children", ())

    def render(self) -> str:
        return render(self)

    def __html__(self) -> str:
        return self.render()

    def __str__(self) -> str:
        return self.render()


Element = element


TAG_NAMES = (
    "html head body title meta link style script main header footer nav section "
    "article "
    "aside div span p a h1 h2 h3 h4 h5 h6 ul ol li dl dt dd form label input "
    "button output textarea select option table thead tbody tfoot tr th td figure "
    "figcaption picture source img video audio canvas template details summary dialog "
    "blockquote pre code strong em small br hr"
).split()

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}

for _name in TAG_NAMES:
    globals()[_name] = ElementMeta(
        _name,
        (element,),
        {"_tag": _name, "_is_tag": True, "__module__": __name__},
    )


def _render_attributes(node: element, classes: tuple[type, ...]) -> str:
    attributes = dict(getattr(node, "_attrs", {}))
    generated = [class_name(value) for value in classes]
    explicit = attributes.pop("class", attributes.pop("class-", None))
    if explicit:
        if isinstance(explicit, (list, tuple, set)):
            generated.extend(str(value) for value in explicit)
        else:
            generated.append(str(explicit))
    if generated:
        attributes = {"class": " ".join(generated), **attributes}

    rendered: list[str] = []
    for name, value in attributes.items():
        if value is None or value is False:
            continue
        if value is True:
            rendered.append(name)
            continue
        rendered.append(f'{name}="{escape(_attribute_value(value), quote=True)}"')
    return "" if not rendered else " " + " ".join(rendered)


def _render(value: Any, context: RenderContext) -> str:
    if value is None:
        return ""
    if isinstance(value, Markup):
        return value.value
    if isinstance(value, element):
        value_type = type(value)
        tag = _tag_for(value_type)
        classes = semantic_classes(value_type)
        for semantic_class in classes:
            context.register(semantic_class)
        attributes = _render_attributes(value, classes)
        if tag in VOID_TAGS:
            return f"<{tag}{attributes}>"
        content = value.content()
        children = _render(content, context)
        return f"<{tag}{attributes}>{children}</{tag}>"
    if isinstance(value, str):
        return escape(value)
    if isinstance(value, bytes):
        return escape(value.decode())
    if isinstance(value, Iterable):
        return "".join(_render(item, context) for item in value)
    return escape(str(value))


def render(value: Any, *, context: RenderContext | None = None) -> str:
    return _render(value, context or RenderContext())


class Page:
    """A complete HTML document around one or more elements."""

    def __init__(
        self,
        *children: Any,
        title: str = "Hyperclass",
        lang: str = "en",
        head: Iterable[Any] = (),
        htmx: bool = True,
    ):
        self.children = children
        self.title = title
        self.lang = lang
        self.head = tuple(head)
        self.htmx = htmx

    def render(self) -> str:
        context = RenderContext()
        body_html = _render(self.children, context)
        head_html = _render(self.head, context)
        stylesheet = context.stylesheet()
        style_html = f"<style>{stylesheet}</style>" if stylesheet else ""
        script_html = ""
        if self.htmx:
            script_html = (
                f'<script src="{HTMX_SRC}" integrity="{HTMX_INTEGRITY}" '
                'crossorigin="anonymous"></script>'
            )
        return (
            "<!doctype html>"
            f'<html lang="{escape(self.lang, quote=True)}"><head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{escape(self.title)}</title>{head_html}{style_html}{script_html}"
            f"</head><body>{body_html}</body></html>"
        )

    def __html__(self) -> str:
        return self.render()

    def __str__(self) -> str:
        return self.render()


def page(*children: Any, **options: Any) -> Page:
    return Page(*children, **options)


__all__ = [
    "Element",
    "HTMX_INTEGRITY",
    "HTMX_SRC",
    "Markup",
    "Page",
    "class_name",
    "element",
    "markup",
    "page",
    "render",
    "selector",
    "semantic_classes",
    *TAG_NAMES,
]
