"""The zero-dependency Hyperclass WSGI host."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, is_dataclass
from http import HTTPStatus
from typing import Any, get_type_hints
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from .binding import Values, bind
from .rendering import render_result, unpack_result
from .routing import (
    BoundEndpoint,
    Endpoint,
    Handler,
    Route,
    RouteURL,
    class_endpoints,
    delete,
    get,
    patch,
    post,
    put,
    route,
)

StartResponse = Callable[[str, list[tuple[str, str]]], Any]


class Request:
    def __init__(self, environ: Mapping[str, Any]):
        self.environ = environ
        self.method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        self.path = str(environ.get("PATH_INFO", "/"))
        self.query = Values(
            parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        )
        self._form: Values | None = None

    @property
    def is_htmx(self) -> bool:
        return str(self.environ.get("HTTP_HX_REQUEST", "")).lower() == "true"

    @property
    def form(self) -> Values:
        if self._form is None:
            content_type = str(self.environ.get("CONTENT_TYPE", "")).split(";", 1)[0]
            if content_type != "application/x-www-form-urlencoded":
                self._form = Values()
            else:
                length = int(self.environ.get("CONTENT_LENGTH") or 0)
                body = self.environ["wsgi.input"].read(length).decode("utf-8")
                self._form = Values(parse_qs(body, keep_blank_values=True))
        return self._form


@dataclass
class Response:
    body: Any = ""
    status: int = 200
    headers: tuple[tuple[str, str], ...] = ()


def call_handler(
    handler: Handler,
    request: Any,
    parameters: Mapping[str, Any],
    values: Any,
) -> Any:
    """Call a route and inject dataclass arguments from a native multidict."""

    target = getattr(handler, "handler", handler)
    signature = inspect.signature(target)
    hints = get_type_hints(target)
    arguments = dict(parameters)
    for name, parameter in signature.parameters.items():
        if name in {"self", "request"} or name in arguments:
            continue
        annotation = hints.get(name, parameter.annotation)
        if isinstance(annotation, type) and is_dataclass(annotation):
            arguments[name] = bind(values, annotation)
    return handler(request, **arguments)


class App:
    """A tiny WSGI callable with method routing and typed path parameters."""

    def __init__(self, *, title: str = "Hyperclass"):
        self.title = title
        self.routes: dict[tuple[str, str], Handler] = {}
        self.dynamic_routes: list[Route] = []
        for endpoint in class_endpoints(type(self)).values():
            bound = endpoint.__get__(self, type(self))
            for declared in endpoint.routes:
                self._register_route(declared, bound)

    def _register_route(self, declared: Route, handler: Handler) -> None:
        registered = Route(
            declared.method,
            declared.path,
            declared.pattern,
            declared.converters,
            handler,
        )
        if declared.parameters:
            self.dynamic_routes = [
                candidate
                for candidate in self.dynamic_routes
                if (candidate.method, candidate.path)
                != (registered.method, registered.path)
            ]
            self.dynamic_routes.append(registered)
        else:
            self.routes[(registered.method, registered.path)] = handler

    def route(self, path: str, *methods: str) -> Callable[[Handler], Endpoint]:
        methods = methods or ("GET",)

        def decorator(handler: Handler) -> Endpoint:
            endpoint = handler if isinstance(handler, Endpoint) else Endpoint(handler)
            first = len(endpoint.routes)
            endpoint = route(path, *methods)(endpoint)
            for declared in endpoint.routes[first:]:
                self._register_route(declared, endpoint)
            return endpoint

        return decorator

    def get(self, path: str) -> Callable[[Handler], Endpoint]:
        return self.route(path, "GET")

    def post(self, path: str) -> Callable[[Handler], Endpoint]:
        return self.route(path, "POST")

    def put(self, path: str) -> Callable[[Handler], Endpoint]:
        return self.route(path, "PUT")

    def patch(self, path: str) -> Callable[[Handler], Endpoint]:
        return self.route(path, "PATCH")

    def delete(self, path: str) -> Callable[[Handler], Endpoint]:
        return self.route(path, "DELETE")

    def __call__(
        self, environ: Mapping[str, Any], start_response: StartResponse
    ) -> list[bytes]:
        request = Request(environ)
        handler = self.routes.get((request.method, request.path))
        parameters: dict[str, Any] = {}
        path_exists = any(path == request.path for _, path in self.routes)
        if handler is None:
            for candidate in self.dynamic_routes:
                matched = candidate.match(request.path)
                if matched is None:
                    continue
                path_exists = True
                if candidate.method == request.method:
                    handler = candidate.handler
                    parameters = matched
                    break
        if handler is None:
            status = 405 if path_exists else 404
            return self._respond(
                start_response, Response(HTTPStatus(status).phrase, status), request
            )
        try:
            result = call_handler(handler, request, parameters, request.form)
        except ValueError as error:
            result = Response(str(error), 400)
        if isinstance(result, Response):
            response = result
        else:
            body, status, headers = unpack_result(result)
            response = Response(body, status, headers)
        return self._respond(start_response, response, request)

    def _respond(
        self, start_response: StartResponse, response: Response, request: Request
    ) -> list[bytes]:
        text = render_result(
            response.body,
            title=self.title,
            is_htmx=request.is_htmx,
            url_resolver=self.resolve_url,
        )
        payload = text.encode("utf-8")
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(payload))),
        ]
        headers.extend(response.headers)
        start_response(
            f"{response.status} {HTTPStatus(response.status).phrase}", headers
        )
        return [payload]

    @staticmethod
    def resolve_url(reference: RouteURL) -> str:
        return reference.route.url(
            query=reference.query,
            **dict(reference.parameters or {}),
        )

    def run(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        with make_server(host, port, self) as server:
            print(f"Serving on http://{host}:{port}")
            server.serve_forever()


__all__ = [
    "App",
    "BoundEndpoint",
    "Endpoint",
    "Request",
    "Response",
    "Route",
    "RouteURL",
    "Values",
    "call_handler",
    "delete",
    "get",
    "patch",
    "post",
    "put",
    "route",
]
