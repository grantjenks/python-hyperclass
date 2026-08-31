import sys
import types
from contextlib import contextmanager
from threading import Thread
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

from examples.chat import ChatRoutes, create_app
from hyperclass.lite import ThreadingWSGIServer


def model(prompt):
    yield "First "
    yield "second "
    yield f"finished for {prompt}."


def make_backend(name, database):
    if name == "lite":
        app = create_app(database, model=model, token_delay=0.15)
        return app, app
    if name == "flask":
        from hyperclass.flask import App

        class FlaskChat(ChatRoutes, App):
            pass

        app = FlaskChat(database, model=model, token_delay=0.15)
        return app, app

    from django.conf import settings

    if not settings.configured:
        settings.configure(
            SECRET_KEY="hyperclass-browser-contract",
            DEBUG=False,
            ALLOWED_HOSTS=["127.0.0.1"],
            ROOT_URLCONF="hyperclass_browser_urls",
            MIDDLEWARE=["django.middleware.csrf.CsrfViewMiddleware"],
        )
        import django

        django.setup()

    from django.core.handlers.wsgi import WSGIHandler
    from django.urls import clear_url_caches, include, path
    from hyperclass.django import App

    class DjangoChat(ChatRoutes, App):
        pass

    app = DjangoChat(database, model=model, token_delay=0.15, namespace="chat")
    urlconf = types.ModuleType("hyperclass_browser_urls")
    urlconf.urlpatterns = [path("", include(app.urls))]
    sys.modules[urlconf.__name__] = urlconf
    clear_url_caches()
    return WSGIHandler(), app


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


@contextmanager
def serve(app):
    server = make_server(
        "127.0.0.1",
        0,
        app,
        server_class=ThreadingWSGIServer,
        handler_class=QuietHandler,
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize("backend", ["lite", "flask", "django"])
def test_stream_stop_regenerate_and_persist(page: Page, tmp_path, backend):
    wsgi, app = make_backend(backend, tmp_path / f"{backend}-chat.db")

    with serve(wsgi) as base_url:
        response = page.goto(base_url)
        assert response is not None and response.ok
        expect(page.get_by_role("heading", name="What can we build?" )).to_be_visible()

        page.get_by_label("Message", exact=True).fill("a useful chat")
        page.get_by_role("button", name="Send message").click()
        expect(page.locator(".user-message")).to_contain_text("a useful chat")
        assistant = page.locator(".assistant-message")
        expect(assistant).to_contain_text("First")
        assistant.get_by_role("button", name="Stop generating").click()
        expect(assistant).to_contain_text("stopped", ignore_case=True)

        assistant.get_by_role("button", name="Regenerate response").click()
        expect(assistant).to_contain_text("finished for a useful chat.")
        expect(assistant.get_by_role("button", name="Regenerate response")).to_be_visible()

        page.reload()
        expect(page.locator(".user-message")).to_contain_text("a useful chat")
        expect(page.locator(".assistant-message")).to_contain_text(
            "finished for a useful chat."
        )
        assert app.store.messages(app.store.latest_or_create().id)[-1].status == "complete"
