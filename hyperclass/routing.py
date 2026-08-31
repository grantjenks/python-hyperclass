"""Framework-neutral route declarations and lazy URL references."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import update_wrapper
from typing import Any
from urllib.parse import quote, urlencode

Handler = Callable[..., Any]
URLResolver = Callable[["RouteURL"], str]

_PARAMETER = re.compile(r"<(?:(int|str):)?([A-Za-z_]\w*)>")


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


@dataclass(frozen=True, eq=False)
class RouteURL:
    """A URL reference resolved by whichever host renders the component."""

    endpoint: Endpoint | BoundEndpoint
    method: str | None = None
    parameters: Mapping[str, Any] | None = None
    query: Mapping[str, Any] | None = None

    @property
    def route(self) -> Route:
        return self.endpoint.route(self.method)

    def resolve(self, resolver: URLResolver | None = None) -> str:
        if resolver is not None:
            return resolver(self)
        return self.route.url(query=self.query, **dict(self.parameters or {}))

    def __hyperclass_url__(self, resolver: URLResolver | None = None) -> str:
        return self.resolve(resolver)

    def __str__(self) -> str:
        return self.resolve()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if not isinstance(other, RouteURL):
            return NotImplemented
        return (
            self.endpoint is other.endpoint
            and self.method == other.method
            and dict(self.parameters or {}) == dict(other.parameters or {})
            and dict(self.query or {}) == dict(other.query or {})
        )


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
    ) -> RouteURL:
        route = self.route(method)
        missing = set(route.parameters) - parameters.keys()
        if missing:
            name = min(missing)
            raise TypeError(f"missing route parameter: {name}")
        unexpected = parameters.keys() - set(route.parameters)
        if unexpected:
            names = ", ".join(sorted(unexpected))
            raise TypeError(f"unexpected route parameter(s): {names}")
        return RouteURL(self, method, dict(parameters), query)

    def __hyperclass_url__(self, resolver: URLResolver | None = None) -> str:
        return self.url().resolve(resolver)

    def __str__(self) -> str:
        return str(self.url())


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
    ) -> RouteURL:
        self.endpoint.url(method=method, query=query, **parameters)
        return RouteURL(self, method, dict(parameters), query)

    def __hyperclass_url__(self, resolver: URLResolver | None = None) -> str:
        return self.url().resolve(resolver)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.endpoint, name)

    def __str__(self) -> str:
        return str(self.endpoint)


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
            pieces.append(rf"(?P<{name}>-?\d+)")
            converters[name] = int
        else:
            pieces.append(rf"(?P<{name}>[^/]+)")
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


def class_endpoints(cls: type) -> dict[str, Endpoint]:
    endpoints: dict[str, Endpoint] = {}
    for base in reversed(cls.__mro__):
        for name, value in base.__dict__.items():
            if isinstance(value, Endpoint):
                endpoints[name] = value
            elif name in endpoints:
                del endpoints[name]
    return endpoints


__all__ = [
    "BoundEndpoint",
    "Endpoint",
    "Handler",
    "Route",
    "RouteURL",
    "URLResolver",
    "class_endpoints",
    "delete",
    "get",
    "patch",
    "post",
    "put",
    "route",
]
