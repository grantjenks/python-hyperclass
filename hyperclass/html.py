"""HTML elements, semantic subclasses, rendering, and pages."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from html import escape
from typing import Any

from .css import PSEUDO_STATES, Media, Style

HTMX_SRC = "https://cdn.jsdelivr.net/npm/htmx.org@4.0.0"
HTMX_INTEGRITY = (
    "sha384-BvJpBiO8Kh31EqtJe5DRIeWrHWnCGkwytKs9NKFi86Hhw96dEqdEMzZDeK9iEGTc"
)
HTMX_EXTENSIONS = {
    "sse": "https://cdn.jsdelivr.net/npm/htmx.org@4.0.0/dist/ext/hx-sse.min.js",
}


def class_name(value: type) -> str:
    return value.__name__.replace("_", "-")


@dataclass(frozen=True)
class Id:
    """A first-class HTML id which is also usable as a selector."""

    name: str

    @property
    def selector(self) -> str:
        return f"#{self.name}"

    def __str__(self) -> str:
        return self.name

    def __getitem__(self, value: Any) -> Id:
        """Return an interned child id, e.g. ``id.message[42]``."""

        return id._intern(f"{self.name}-{str(value).replace('_', '-')}")


class IdNamespace:
    def __init__(self) -> None:
        self._values: dict[str, Id] = {}

    def __getattr__(self, name: str) -> Id:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._intern(name.replace("_", "-"))

    def _intern(self, value: str) -> Id:
        try:
            return self._values[value]
        except KeyError:
            identity = Id(value)
            self._values[value] = identity
            return identity


id = IdNamespace()


@dataclass(frozen=True)
class Name:
    """A first-class form name which is also usable as a selector."""

    name: str

    @property
    def selector(self) -> str:
        return f'[name="{self.name}"]'

    def __str__(self) -> str:
        return self.name


class NameNamespace:
    def __init__(self) -> None:
        self._values: dict[str, Name] = {}

    def __getattr__(self, value: str) -> Name:
        if value.startswith("_"):
            raise AttributeError(value)
        try:
            return self._values[value]
        except KeyError:
            field_name = Name(value)
            self._values[value] = field_name
            return field_name


name = NameNamespace()


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

    if isinstance(value, (Id, Name)):
        return value.selector
    if isinstance(value, str):
        return value
    if isinstance(value, element):
        attributes = _class_attributes(type(value))
        attributes.update(getattr(value, "_attrs", {}))
        identity = attributes.get("id")
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


@dataclass(frozen=True)
class Fragment:
    """A renderable sequence of sibling nodes."""

    children: tuple[Any, ...]

    def __iter__(self):
        return iter(self.children)

    def render(self) -> str:
        return render(self)


def fragment(*children: Any) -> Fragment:
    return Fragment(children)


class RenderContext:
    def __init__(self, url_resolver: Callable[[Any], str] | None = None) -> None:
        self.url_resolver = url_resolver
        self.styled_elements: list[type] = []
        self._seen_elements: set[type] = set()
        self.extensions: list[str] = []
        self._seen_extensions: set[str] = set()

    def register(self, value: type) -> None:
        if value in self._seen_elements:
            return
        classes = semantic_classes(value)
        if any(
            isinstance(rule, (Style, Media))
            for semantic_class in classes
            for rule in semantic_class.__dict__.values()
        ):
            self._seen_elements.add(value)
            self.styled_elements.append(value)

    def register_extensions(self, values: Iterable[str]) -> None:
        for value in values:
            if value not in self._seen_extensions:
                self._seen_extensions.add(value)
                self.extensions.append(value)

    def stylesheet(self) -> str:
        rules: list[str] = []
        for element_type in self.styled_elements:
            classes = semantic_classes(element_type)
            base = "".join(f".{class_name(value)}" for value in classes)
            for value in classes:
                for name, rule in value.__dict__.items():
                    if name == "style" and isinstance(rule, Style):
                        rules.append(f"{base}{{{rule.render()}}}")
                    elif name in PSEUDO_STATES and isinstance(rule, Style):
                        state = name.replace("_", "-")
                        rules.append(f"{base}:{state}{{{rule.render()}}}")
                    elif isinstance(rule, Media):
                        rules.append(
                            f"@media {rule.query()}"
                            f"{{{base}{{{rule.style.render()}}}}}"
                        )
        return "".join(rules)


def _attribute_name(name: str) -> str:
    if name.endswith("_"):
        name = name[:-1]
    return name.replace("_", "-")


def _attribute_value(value: Any, context: RenderContext) -> str:
    resolve = getattr(value, "__hyperclass_url__", None)
    if callable(resolve):
        return resolve(context.url_resolver)
    if isinstance(value, Style):
        return value.render()
    if isinstance(value, type) or isinstance(value, element):
        return selector(value)
    return str(value)


def _attribute(target: dict[str, Any], name: str, value: Any) -> None:
    if name == "hx" and isinstance(value, Mapping):
        target.update(value)
        extensions = getattr(value, "extensions", ())
        if extensions:
            existing = target.setdefault("_hyperclass_extensions", set())
            existing.update(extensions)
    else:
        target[_attribute_name(name)] = value


def _class_attributes(value: type) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    for semantic_class in semantic_classes(value):
        for name, default in semantic_class.__dict__.items():
            if name.startswith("_") or isinstance(default, (Style, Media, type)):
                continue
            if isinstance(default, (classmethod, staticmethod, property)):
                continue
            if callable(default):
                continue
            _attribute(attributes, name, default)
    return attributes


class element(metaclass=ElementMeta):
    """Base class for all rendered HTML elements."""

    def __init__(self, *children: Any, **attributes: Any):
        self._children = children
        self._attrs: dict[str, Any] = {}
        for name, value in attributes.items():
            _attribute(self._attrs, name, value)

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
    "aside div span p a h1 h2 h3 h4 h5 h6 ul ol li dl dt dd form fieldset legend label input "
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

# htmx 4 uses this custom element to route one response fragment elsewhere.
partial = ElementMeta(
    "partial",
    (element,),
    {"_tag": "hx-partial", "_is_tag": True, "__module__": __name__},
)


def _render_attributes(
    node: element, classes: tuple[type, ...], context: RenderContext
) -> str:
    attributes = _class_attributes(type(node))
    attributes.update(getattr(node, "_attrs", {}))
    context.register_extensions(attributes.pop("_hyperclass_extensions", ()))
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
        rendered.append(
            f'{name}="{escape(_attribute_value(value, context), quote=True)}"'
        )
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
        context.register(value_type)
        attributes = _render_attributes(value, classes, context)
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
        body_attributes: Mapping[str, Any] | None = None,
    ):
        self.children = children
        self.title = title
        self.lang = lang
        self.head = tuple(head)
        self.htmx = htmx
        self.body_attributes = dict(body_attributes or {})

    def render(
        self,
        *,
        url_resolver: Callable[[Any], str] | None = None,
        body_attributes: Mapping[str, Any] | None = None,
    ) -> str:
        context = RenderContext(url_resolver=url_resolver)
        attributes = {**self.body_attributes, **dict(body_attributes or {})}
        body_node = globals()["body"](*self.children, **attributes)
        body_html = _render(body_node, context)
        head_html = _render(self.head, context)
        stylesheet = context.stylesheet()
        style_html = (
            f'<style id="{id.hyperclass_styles}">{stylesheet}</style>'
        )
        script_html = ""
        if self.htmx:
            script_html = (
                f'<script src="{HTMX_SRC}" integrity="{HTMX_INTEGRITY}" '
                'crossorigin="anonymous"></script>'
            )
            script_html += "".join(
                f'<script src="{escape(HTMX_EXTENSIONS[value], quote=True)}"></script>'
                for value in context.extensions
            )
        return (
            "<!doctype html>"
            f'<html lang="{escape(self.lang, quote=True)}"><head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{escape(self.title)}</title>{head_html}{style_html}{script_html}"
            f"</head>{body_html}</html>"
        )

    def __html__(self) -> str:
        return self.render()

    def __str__(self) -> str:
        return self.render()


def page(*children: Any, **options: Any) -> Page:
    return Page(*children, **options)


__all__ = [
    "Element",
    "Fragment",
    "HTMX_INTEGRITY",
    "HTMX_EXTENSIONS",
    "HTMX_SRC",
    "Id",
    "IdNamespace",
    "Markup",
    "Name",
    "NameNamespace",
    "Page",
    "class_name",
    "element",
    "fragment",
    "id",
    "markup",
    "name",
    "page",
    "partial",
    "render",
    "selector",
    "semantic_classes",
    *TAG_NAMES,
]
