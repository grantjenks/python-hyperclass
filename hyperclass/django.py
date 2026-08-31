"""Native Django hosting for Hyperclass components and routes."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, QueryDict, StreamingHttpResponse
from django.middleware.csrf import get_token
from django.urls import URLPattern, reverse
from django.urls import path as django_path

from .html import Fragment, Page, element
from .lite import call_handler
from .rendering import render_result, unpack_result
from .routing import Endpoint, Handler, Route, RouteURL, class_endpoints, route
from .streaming import EventStream

_BARE_PARAMETER = re.compile(r"<([A-Za-z_]\w*)>")


def _django_path(path: str) -> str:
    return _BARE_PARAMETER.sub(r"<str:\1>", path.lstrip("/"))


def _form_values(request: HttpRequest) -> QueryDict:
    if request.method == "POST":
        return request.POST
    content_type = request.content_type or ""
    if request.method in {"PUT", "PATCH", "DELETE"} and content_type == (
        "application/x-www-form-urlencoded"
    ):
        return QueryDict(request.body, encoding=request.encoding)
    return QueryDict("", mutable=False)


class App:
    """A Django URL application with method-aware Hyperclass handlers."""

    def __init__(
        self,
        *,
        title: str = "Hyperclass",
        namespace: str | None = None,
    ):
        self.title = title
        self.app_name = namespace or type(self).__name__.replace("_", "-")
        self.namespace = self.app_name
        self.urlpatterns: list[URLPattern] = []
        self._route_names: dict[tuple[int, str, str], str] = {}
        self._dispatchers: dict[str, dict[str, Handler]] = {}
        self._views: dict[str, Callable[..., HttpResponse]] = {}
        for name, endpoint in class_endpoints(type(self)).items():
            bound = endpoint.__get__(self, type(self))
            for declared in endpoint.routes:
                self._register_route(name, endpoint, declared, bound)

    @property
    def urls(self) -> tuple[list[URLPattern], str]:
        """Return the value expected by ``django.urls.include``."""

        return self.urlpatterns, self.app_name

    def _register_route(
        self,
        name: str,
        endpoint: Endpoint,
        declared: Route,
        handler: Handler,
    ) -> None:
        route_name = f"{name}-{len(self._route_names)}"
        key = (id(endpoint), declared.method, declared.path)
        self._route_names[key] = route_name
        handlers = self._dispatchers.setdefault(declared.path, {})
        handlers[declared.method] = handler

        if declared.path not in self._views:

            def view(request: HttpRequest, **parameters: Any) -> HttpResponse:
                return self._dispatch(declared.path, request, parameters)

            self._views[declared.path] = view

        self.urlpatterns.append(
            django_path(
                _django_path(declared.path),
                self._views[declared.path],
                name=route_name,
            )
        )

    def route(self, path: str, *methods: str) -> Callable[[Handler], Endpoint]:
        methods = methods or ("GET",)

        def decorator(handler: Handler) -> Endpoint:
            endpoint = handler if isinstance(handler, Endpoint) else Endpoint(handler)
            first = len(endpoint.routes)
            endpoint = route(path, *methods)(endpoint)
            for declared in endpoint.routes[first:]:
                self._register_route(endpoint.__name__, endpoint, declared, endpoint)
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

    def _dispatch(
        self,
        declared_path: str,
        request: HttpRequest,
        parameters: dict[str, Any],
    ) -> HttpResponse:
        handler = self._dispatchers[declared_path].get(request.method)
        if handler is None:
            return HttpResponse("Method Not Allowed", status=405)
        try:
            result = call_handler(handler, request, parameters, _form_values(request))
        except ValueError as error:
            result = str(error), 400
        if isinstance(result, HttpResponse):
            return result

        body, status, headers = unpack_result(result)
        if isinstance(body, EventStream):
            response = StreamingHttpResponse(
                body.iter_bytes(title=self.title, url_resolver=self.resolve_url),
                status=status,
                content_type="text/event-stream; charset=utf-8",
            )
            response["Cache-Control"] = "no-cache"
            response["X-Accel-Buffering"] = "no"
            for name, value in headers:
                response[name] = value
            return response
        if isinstance(body, (element, Fragment, Page)):
            body = render_result(
                body,
                title=self.title,
                is_htmx=request.headers.get("HX-Request", "").lower() == "true",
                url_resolver=self.resolve_url,
                body_attributes={
                    "hx-headers:inherited": json.dumps(
                        {"X-CSRFToken": get_token(request)}, separators=(",", ":")
                    )
                },
            )
        response = HttpResponse(
            body, status=status, content_type="text/html; charset=utf-8"
        )
        for name, value in headers:
            response[name] = value
        return response

    def resolve_url(self, reference: RouteURL) -> str:
        endpoint = getattr(reference.endpoint, "endpoint", reference.endpoint)
        declared = reference.route
        key = (id(endpoint), declared.method, declared.path)
        name = self._route_names[key]
        url = reverse(
            f"{self.namespace}:{name}",
            kwargs=dict(reference.parameters or {}),
        )
        if reference.query:
            url = f"{url}?{urlencode(reference.query, doseq=True)}"
        return url


__all__ = ["App"]
