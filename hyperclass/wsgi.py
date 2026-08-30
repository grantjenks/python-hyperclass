"""A deliberately small WSGI application and request object."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import MISSING, dataclass, fields, is_dataclass
from functools import update_wrapper
from http import HTTPStatus
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints
from urllib.parse import parse_qs, quote, urlencode
from wsgiref.simple_server import make_server

from .html import (
    Fragment,
    Page,
    RenderContext,
    element,
    id,
    markup,
    partial,
    render,
)

Handler = Callable[..., Any]
StartResponse = Callable[[str, list[tuple[str, str]]], Any]


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    pattern: re.Pattern[str]
    converters: Mapping[str, Callable[[str], Any]]
    handler: Handler

    @property
    def parameters(self) -> tuple[str, ...]:
        return tuple(self.converters)

    def match(self, path: str) -> dict[str, Any] | None:
        matched = self.pattern.fullmatch(path)
        if matched is None:
            return None
        return {
            name: self.converters[name](value)
            for name, value in matched.groupdict().items()
        }

    def url(
        self,
        *,
        query: Mapping[str, Any] | None = None,
        **parameters: Any,
    ) -> str:
        remaining = dict(parameters)

        def replace(parameter: re.Match[str]) -> str:
            kind, name = parameter.groups()
            if name not in remaining:
                raise TypeError(f"missing route parameter: {name}")
            value = remaining.pop(name)
            if kind == "int":
                try:
                    value = int(value)
                except (TypeError, ValueError) as error:
                    raise TypeError(
                        f"invalid integer route parameter: {name}"
                    ) from error
            return quote(str(value), safe="")

        path = _PARAMETER.sub(replace, self.path)
        if remaining:
            names = ", ".join(sorted(remaining))
            raise TypeError(f"unexpected route parameter(s): {names}")
        if query:
            path = f"{path}?{urlencode(query, doseq=True)}"
        return path


class Endpoint:
    """A callable handler carrying enough metadata to generate its URLs."""

    def __init__(self, handler: Handler):
        self.handler = handler
        self.routes: list[Route] = []
        update_wrapper(self, handler)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.handler(*args, **kwargs)

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return BoundEndpoint(self, instance)

    def route(self, method: str | None = None) -> Route:
        candidates = self.routes
        if method is not None:
            candidates = [
                route for route in candidates if route.method == method.upper()
            ]
        elif len(candidates) > 1:
            get_routes = [route for route in candidates if route.method == "GET"]
            if len(get_routes) == 1:
                candidates = get_routes
        if len(candidates) != 1:
            detail = f" for {method.upper()}" if method else ""
            raise TypeError(f"handler does not have exactly one route{detail}")
        return candidates[0]

    def parameters(self, method: str | None = None) -> tuple[str, ...]:
        return self.route(method).parameters

    @property
    def path(self) -> str:
        return self.route().path

    def url(
        self,
        *,
        method: str | None = None,
        query: Mapping[str, Any] | None = None,
        **parameters: Any,
    ) -> str:
        return self.route(method).url(query=query, **parameters)

    def __str__(self) -> str:
        return self.url()


class BoundEndpoint:
    """An endpoint whose handler is bound to an application instance."""

    def __init__(self, endpoint: Endpoint, instance: Any):
        self.endpoint = endpoint
        self.instance = instance

    @property
    def handler(self) -> Handler:
        return self.endpoint.handler.__get__(self.instance, type(self.instance))

    @property
    def routes(self) -> list[Route]:
        return self.endpoint.routes

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.handler(*args, **kwargs)

    def route(self, method: str | None = None) -> Route:
        return self.endpoint.route(method)

    def parameters(self, method: str | None = None) -> tuple[str, ...]:
        return self.endpoint.parameters(method)

    @property
    def path(self) -> str:
        return self.endpoint.path

    def url(
        self,
        *,
        method: str | None = None,
        query: Mapping[str, Any] | None = None,
        **parameters: Any,
    ) -> str:
        return self.endpoint.url(method=method, query=query, **parameters)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.endpoint, name)

    def __str__(self) -> str:
        return str(self.endpoint)


_PARAMETER = re.compile(r"<(?:(int|str):)?([A-Za-z_]\w*)>")


def _compile_path(path: str) -> tuple[re.Pattern[str], dict[str, Callable]]:
    pieces: list[str] = []
    converters: dict[str, Callable[[str], Any]] = {}
    position = 0
    for parameter in _PARAMETER.finditer(path):
        pieces.append(re.escape(path[position : parameter.start()]))
        kind, name = parameter.groups()
        if name in converters:
            raise ValueError(f"duplicate route parameter: {name}")
        if kind == "int":
            pieces.append(fr"(?P<{name}>-?\d+)")
            converters[name] = int
        else:
            pieces.append(fr"(?P<{name}>[^/]+)")
            converters[name] = str
        position = parameter.end()
    pieces.append(re.escape(path[position:]))
    return re.compile("".join(pieces)), converters


def route(path: str, *methods: str) -> Callable[[Handler], Endpoint]:
    """Declare one or more routes on an application method."""

    methods = methods or ("GET",)

    def decorator(handler: Handler) -> Endpoint:
        endpoint = handler if isinstance(handler, Endpoint) else Endpoint(handler)
        for method in methods:
            pattern, converters = _compile_path(path)
            endpoint.routes.append(
                Route(method.upper(), path, pattern, converters, endpoint)
            )
        return endpoint

    return decorator


def get(path: str) -> Callable[[Handler], Endpoint]:
    return route(path, "GET")


def post(path: str) -> Callable[[Handler], Endpoint]:
    return route(path, "POST")


def put(path: str) -> Callable[[Handler], Endpoint]:
    return route(path, "PUT")


def patch(path: str) -> Callable[[Handler], Endpoint]:
    return route(path, "PATCH")


def delete(path: str) -> Callable[[Handler], Endpoint]:
    return route(path, "DELETE")


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
        """Build a dataclass from form or query values."""

        if not isinstance(model, type) or not is_dataclass(model):
            raise TypeError("values can only bind to a dataclass type")
        hints = get_type_hints(model)
        values: dict[str, Any] = {}
        for field in fields(model):
            annotation = hints.get(field.name, field.type)
            raw = self._values.get(field.name)
            if raw is None:
                if field.default is not MISSING or field.default_factory is not MISSING:
                    continue
                if _optional(annotation):
                    values[field.name] = None
                elif annotation is bool:
                    values[field.name] = False
                else:
                    raise ValueError(f"missing form value: {field.name}")
                continue
            try:
                values[field.name] = _convert_values(raw, annotation)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"invalid form value for {field.name}: {raw[-1]!r}"
                ) from error
        return model(**values)


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


class App:
    """A WSGI callable with method routing and typed path parameters."""

    def __init__(self, *, title: str = "Hyperclass"):
        self.title = title
        self.routes: dict[tuple[str, str], Handler] = {}
        self.dynamic_routes: list[Route] = []
        for name, endpoint in self._class_endpoints().items():
            bound = endpoint.__get__(self, type(self))
            for declared in endpoint.routes:
                self._register_route(declared, bound)

    @classmethod
    def _class_endpoints(cls) -> dict[str, Endpoint]:
        endpoints: dict[str, Endpoint] = {}
        for base in reversed(cls.__mro__):
            for name, value in base.__dict__.items():
                if isinstance(value, Endpoint):
                    endpoints[name] = value
                elif name in endpoints:
                    del endpoints[name]
        return endpoints

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
                route
                for route in self.dynamic_routes
                if (route.method, route.path)
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
            for route in self.dynamic_routes:
                matched = route.match(request.path)
                if matched is None:
                    continue
                path_exists = True
                if route.method == request.method:
                    handler = route.handler
                    parameters = matched
                    break
        if handler is None:
            status = 405 if path_exists else 404
            return self._respond(
                start_response, Response(HTTPStatus(status).phrase, status), request
            )
        try:
            result = self._call(handler, request, parameters)
        except ValueError as error:
            result = Response(str(error), 400)
        if not isinstance(result, Response):
            result = Response(result)
        return self._respond(start_response, result, request)

    @staticmethod
    def _call(
        handler: Handler, request: Request, parameters: Mapping[str, Any]
    ) -> Any:
        target = getattr(handler, "handler", handler)
        signature = inspect.signature(target)
        hints = get_type_hints(target)
        arguments = dict(parameters)
        for name, parameter in signature.parameters.items():
            if name == "request" or name in arguments:
                continue
            annotation = hints.get(name, parameter.annotation)
            if isinstance(annotation, type) and is_dataclass(annotation):
                arguments[name] = request.form.bind(annotation)
        return handler(request, **arguments)

    def _respond(
        self, start_response: StartResponse, response: Response, request: Request
    ) -> list[bytes]:
        body = response.body
        if isinstance(body, Page):
            text = body.render()
        elif isinstance(body, (element, Fragment)):
            if request.is_htmx:
                context = RenderContext()
                text = render(body, context=context)
                stylesheet = context.stylesheet()
                if stylesheet:
                    text += render(
                        partial(
                            markup(stylesheet),
                            id=id.hyperclass_styles,
                            hx_swap="append",
                        )
                    )
            else:
                text = Page(body, title=self.title).render()
        else:
            text = str(body)
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

    def run(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        with make_server(host, port, self) as server:
            print(f"Serving on http://{host}:{port}")
            server.serve_forever()
