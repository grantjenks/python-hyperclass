import re
import sys
import types
from contextlib import contextmanager
from threading import Thread
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

from examples.bookmarks import BookmarkRoutes, create_app


def make_backend(name, database):
    if name == "lite":
        app = create_app(database)
        return app, app
    if name == "flask":
        from hyperclass.flask import App

        class FlaskBookmarks(BookmarkRoutes, App):
            pass

        app = FlaskBookmarks(database)
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

    class DjangoBookmarks(BookmarkRoutes, App):
        pass

    app = DjangoBookmarks(database, namespace="bookmarks")
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
    server = make_server("127.0.0.1", 0, app, handler_class=QuietHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize("backend", ["lite", "flask", "django"])
def test_bookmark_lifecycle_in_a_browser(page: Page, tmp_path, backend):
    wsgi, app = make_backend(backend, tmp_path / f"{backend}.db")

    with serve(wsgi) as base_url:
        response = page.goto(base_url)
        assert response is not None and response.ok
        expect(
            page.get_by_role("heading", name="Bookmark inbox", exact=True)
        ).to_be_visible()
        expect(page.get_by_text("No bookmarks yet.", exact=True)).to_be_visible()

        stylesheet = page.locator("#hyperclass-styles")
        assert ".bookmark-card" not in (stylesheet.text_content() or "")

        page.get_by_label("URL", exact=True).fill("https://example.com/read")
        page.get_by_label("Title (optional)", exact=True).fill("Read this")
        with page.expect_request(
            lambda request: (
                request.method == "POST" and request.url == f"{base_url}/bookmarks"
            )
        ) as request_info:
            page.get_by_role("button", name="Save", exact=True).click()

        assert request_info.value.headers.get("hx-request") == "true"
        assert page.url == f"{base_url}/"

        card = page.locator(".bookmark-card")
        expect(card).to_have_count(1)
        expect(card).to_contain_text("Read this")
        expect(card).to_have_css("display", "grid")
        assert ".bookmark-card.unread.unread-bookmark" in (
            stylesheet.text_content() or ""
        )

        card.get_by_role("button", name="Mark read", exact=True).click()
        expect(page.get_by_text("0 unread bookmarks", exact=True)).to_be_visible()
        card = page.locator(".bookmark-card")
        expect(card).to_have_class(re.compile(r"\bread-bookmark\b"))
        expect(
            card.get_by_role("button", name="Mark unread", exact=True)
        ).to_be_visible()

        card.get_by_role("button", name="Edit", exact=True).click()
        editor = page.locator(".bookmark-editor")
        expect(editor).to_be_visible()
        editor.get_by_label("Title", exact=True).fill("Edited title")
        editor.get_by_role("button", name="Save", exact=True).click()
        card = page.locator(".bookmark-card")
        expect(card).to_contain_text("Edited title")

        search = page.get_by_label("Search bookmarks", exact=True)
        search.fill("missing")
        expect(
            page.get_by_text('No bookmarks matching "missing".', exact=True)
        ).to_be_visible()

        search = page.get_by_label("Search bookmarks", exact=True)
        search.fill("Edited")
        expect(page.locator(".bookmark-card")).to_contain_text("Edited title")

        search = page.get_by_label("Search bookmarks", exact=True)
        search.fill("")
        card = page.locator(".bookmark-card")
        expect(card).to_be_visible()

        page.once("dialog", lambda dialog: dialog.accept())
        card.get_by_role("button", name="Delete", exact=True).click()
        expect(page.get_by_text("No bookmarks yet.", exact=True)).to_be_visible()
        assert app.store.list() == []
