import sys
import types
from dataclasses import dataclass
from html import unescape

from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY="hyperclass-tests",
        DEBUG=False,
        ALLOWED_HOSTS=["testserver"],
        ROOT_URLCONF="hyperclass_test_urls",
        MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
    )
    import django

    django.setup()

from django.http import HttpRequest, HttpResponse
from django.test import Client
from django.urls import clear_url_caches, include, path

from hyperclass import div, form, get, hx, post
from hyperclass.django import App


@dataclass
class Entry:
    title: str


class DjangoRoutes(App):
    seen_request = None

    @get("/")
    def index(self, request):
        return form(
            "Create",
            action=DjangoRoutes.create.url(item_id=7),
            hx=hx.post(DjangoRoutes.create, item_id=7),
        )

    @post("/items/<int:item_id>")
    def create(self, request, item_id, form: Entry):
        type(self).seen_request = request
        return div(f"{item_id}:{form.title}")

    @get("/native")
    def native(self, request):
        return HttpResponse("native django", status=201)


def mounted(app):
    module = types.ModuleType("hyperclass_test_urls")
    module.urlpatterns = [path("mounted/", include(app.urls))]
    sys.modules[module.__name__] = module
    clear_url_caches()
    return Client(enforce_csrf_checks=True)


def test_django_reverses_namespaced_routes_and_supplies_csrf():
    client = mounted(DjangoRoutes(namespace="examples"))
    response = client.get("/mounted/")
    assert response.status_code == 200
    text = response.content.decode()
    assert 'action="/mounted/items/7"' in text
    assert 'hx-post="/mounted/items/7"' in text
    assert "hx-headers=" in text
    assert "X-CSRFToken" in unescape(text)
    assert "csrftoken" in response.cookies


def test_django_passes_native_requests_and_binds_querydict_forms():
    client = mounted(DjangoRoutes(namespace="forms"))
    csrf = client.get("/mounted/").cookies["csrftoken"].value
    response = client.post(
        "/mounted/items/3",
        {"title": "Python"},
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    assert response.content.decode() == "<div>3:Python</div>"
    assert isinstance(DjangoRoutes.seen_request, HttpRequest)


def test_django_native_responses_pass_through():
    response = mounted(DjangoRoutes(namespace="native")).get("/mounted/native")
    assert response.status_code == 201
    assert response.content == b"native django"


def test_django_dispatches_methods_on_one_url_pattern():
    client = mounted(DjangoRoutes(namespace="methods"))
    response = client.get("/mounted/items/3")
    assert response.status_code == 405
