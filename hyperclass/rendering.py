"""Shared HTML result rendering for every host."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .html import Fragment, Page, RenderContext, element, id, markup, partial, render
from .routing import URLResolver


def render_result(
    body: Any,
    *,
    title: str,
    is_htmx: bool,
    url_resolver: URLResolver | None = None,
    body_attributes: Mapping[str, Any] | None = None,
) -> str:
    if isinstance(body, Page):
        return body.render(
            url_resolver=url_resolver,
            body_attributes=body_attributes,
        )
    if isinstance(body, (element, Fragment)):
        if not is_htmx:
            return Page(
                body,
                title=title,
                body_attributes=body_attributes,
            ).render(url_resolver=url_resolver)
        context = RenderContext(url_resolver=url_resolver)
        text = render(body, context=context)
        stylesheet = context.stylesheet()
        if stylesheet:
            text += render(
                partial(
                    markup(stylesheet),
                    id=id.hyperclass_styles,
                    hx_swap="append",
                ),
                context=context,
            )
        return text
    return str(body)


def unpack_result(result: Any) -> tuple[Any, int, tuple[tuple[str, str], ...]]:
    if not isinstance(result, tuple):
        return result, 200, ()
    if len(result) == 2:
        body, status = result
        return body, int(status), ()
    if len(result) == 3:
        body, status, headers = result
        return body, int(status), tuple(headers)
    raise TypeError("response tuple must have two or three items")


__all__ = ["render_result", "unpack_result"]
