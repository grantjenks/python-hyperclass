"""Native Flask hosting for Hyperclass components and routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from flask import Flask, request, stream_with_context, url_for
from flask import Response as FlaskResponse

from .html import Fragment, Page, element
from .lite import call_handler
from .rendering import render_result, unpack_result
from .routing import Endpoint, Handler, Route, RouteURL, class_endpoints, route
from .streaming import EventStream


class App(Flask):
    """A Flask application which understands Hyperclass route methods."""

    def __init__(
        self,
        import_name: str | None = None,
        *,
        title: str = "Hyperclass",
        **options: Any,
    ):
        options.setdefault("static_folder", None)
        super().__init__(import_name or type(self).__module__, **options)
        self.title = title
        self._route_names: dict[tuple[int, str, str], str] = {}
        for name, endpoint in class_endpoints(type(self)).items():
            bound = endpoint.__get__(self, type(self))
            for declared in endpoint.routes:
                self._register_hyperclass_route(name, endpoint, declared, bound)

    def _register_hyperclass_route(
        self,
        name: str,
        endpoint: Endpoint,
        declared: Route,
        handler: Handler,
        **options: Any,
    ) -> None:
        route_name = f"hyperclass_{name}_{len(self._route_names)}"
        self._route_names[(id(endpoint), declared.method, declared.path)] = route_name

        def view(**parameters: Any) -> Any:
            try:
                return call_handler(handler, request, parameters, request.form)
            except ValueError as error:
                return str(error), 400

        view.__name__ = route_name
        self.add_url_rule(
            declared.path,
            endpoint=route_name,
            view_func=view,
            methods=[declared.method],
            **options,
        )

    def route(self, path: str, *methods: str, **options: Any) -> Callable:
        """Register a Hyperclass handler on an application instance."""

        declared_methods = methods or tuple(options.pop("methods", ("GET",)))

        def decorator(handler: Handler) -> Endpoint:
            endpoint = handler if isinstance(handler, Endpoint) else Endpoint(handler)
            first = len(endpoint.routes)
            endpoint = route(path, *declared_methods)(endpoint)
            for declared in endpoint.routes[first:]:
                self._register_hyperclass_route(
                    endpoint.__name__, endpoint, declared, endpoint, **options
                )
            return endpoint

        return decorator

    def get(self, path: str, **options: Any) -> Callable:
        return self.route(path, "GET", **options)

    def post(self, path: str, **options: Any) -> Callable:
        return self.route(path, "POST", **options)

    def put(self, path: str, **options: Any) -> Callable:
        return self.route(path, "PUT", **options)

    def patch(self, path: str, **options: Any) -> Callable:
        return self.route(path, "PATCH", **options)

    def delete(self, path: str, **options: Any) -> Callable:
        return self.route(path, "DELETE", **options)

    def resolve_url(self, reference: RouteURL) -> str:
        endpoint = getattr(reference.endpoint, "endpoint", reference.endpoint)
        declared = reference.route
        name = self._route_names[(id(endpoint), declared.method, declared.path)]
        url = url_for(name, **dict(reference.parameters or {}))
        if reference.query:
            url = f"{url}?{urlencode(reference.query, doseq=True)}"
        return url

    def make_response(self, rv: Any) -> FlaskResponse:
        if isinstance(rv, FlaskResponse):
            return super().make_response(rv)

        body, status, headers = unpack_result(rv)
        if isinstance(body, EventStream):
            response = FlaskResponse(
                stream_with_context(
                    body.iter_text(title=self.title, url_resolver=self.resolve_url)
                ),
                status=status,
                headers=headers,
                content_type="text/event-stream; charset=utf-8",
            )
            response.headers.setdefault("Cache-Control", "no-cache")
            response.headers.setdefault("X-Accel-Buffering", "no")
            return response
        if isinstance(body, (element, Fragment, Page)):
            body = render_result(
                body,
                title=self.title,
                is_htmx=request.headers.get("HX-Request", "").lower() == "true",
                url_resolver=self.resolve_url,
            )
        return super().make_response((body, status, headers))


__all__ = ["App"]
