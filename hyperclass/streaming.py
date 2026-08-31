"""Host-neutral server-sent event responses."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from .html import (
    Fragment,
    Markup,
    Page,
    RenderContext,
    element,
    id as html_id,
    markup,
    partial,
    render,
)
from .rendering import render_result
from .routing import URLResolver


@dataclass(frozen=True)
class SSEEvent:
    """One server-sent event containing a renderable Hyperclass value."""

    content: Any
    name: str | None = None
    id: str | None = None
    retry: int | None = None


def event(
    content: Any,
    *,
    name: str | None = None,
    id: str | None = None,
    retry: int | None = None,
) -> SSEEvent:
    return SSEEvent(content, name=name, id=id, retry=retry)


class EventStream:
    """An iterable response rendered as ``text/event-stream``."""

    def __init__(self, events: Iterable[Any]):
        self.events = events

    def iter_text(
        self,
        *,
        title: str = "Hyperclass",
        url_resolver: URLResolver | None = None,
    ) -> Iterator[str]:
        context = RenderContext(url_resolver=url_resolver)
        emitted_styles = ""
        for value in self.events:
            current = value if isinstance(value, SSEEvent) else SSEEvent(value)
            content = current.content
            if isinstance(content, Page):
                text = render_result(
                    content,
                    title=title,
                    is_htmx=True,
                    url_resolver=url_resolver,
                )
            elif isinstance(content, (element, Fragment, Markup)):
                text = render(content, context=context)
                stylesheet = context.stylesheet()
                if stylesheet.startswith(emitted_styles):
                    new_styles = stylesheet[len(emitted_styles) :]
                else:
                    new_styles = stylesheet
                emitted_styles = stylesheet
                if new_styles:
                    text += render(
                        partial(
                            markup(new_styles),
                            id=html_id.hyperclass_styles,
                            hx_swap="append",
                        ),
                        context=context,
                    )
            else:
                text = render(content)
            fields: list[str] = []
            if current.name is not None:
                fields.append(f"event: {current.name}")
            if current.id is not None:
                fields.append(f"id: {current.id}")
            if current.retry is not None:
                fields.append(f"retry: {current.retry}")
            fields.extend(f"data: {line}" for line in text.splitlines() or [""])
            yield "\n".join(fields) + "\n\n"

    def iter_bytes(
        self,
        *,
        title: str = "Hyperclass",
        url_resolver: URLResolver | None = None,
    ) -> Iterator[bytes]:
        for value in self.iter_text(title=title, url_resolver=url_resolver):
            yield value.encode("utf-8")


def stream(events: Iterable[Any]) -> EventStream:
    """Create a streaming response from renderable values or ``event`` objects."""

    return EventStream(events)


__all__ = ["EventStream", "SSEEvent", "event", "stream"]
