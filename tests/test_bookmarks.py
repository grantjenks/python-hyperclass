from io import BytesIO
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from examples.bookmarks import create_app


def request(app, method="GET", path="/", data=None, htmx=False):
    environ = {}
    setup_testing_defaults(environ)
    route, _, query = path.partition("?")
    body = urlencode(data or {}).encode()
    environ.update(
        REQUEST_METHOD=method,
        PATH_INFO=route,
        QUERY_STRING=query,
        CONTENT_TYPE="application/x-www-form-urlencoded",
        CONTENT_LENGTH=str(len(body)),
        **{"wsgi.input": BytesIO(body)},
    )
    if htmx:
        environ["HTTP_HX_REQUEST"] = "true"
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response)).decode()
    return captured, payload


def test_bookmark_lifecycle(tmp_path):
    app = create_app(tmp_path / "bookmarks.db")

    captured, payload = request(app)
    assert captured["status"] == "200 OK"
    assert payload.startswith("<!doctype html>")
    assert "Bookmark inbox" in payload
    assert "0 unread bookmarks" in payload
    assert 'content="width=device-width, initial-scale=1"' in payload
    assert (
        "@media (max-width:40rem){.bookmark-form{grid-template-columns:1fr}}"
        in payload
    )

    captured, payload = request(
        app,
        "POST",
        "/bookmarks",
        {"url": "https://example.com/read", "title": "Read this"},
        htmx=True,
    )
    assert captured["status"] == "200 OK"
    assert "<!doctype html>" not in payload
    assert "Read this" in payload
    assert "1 unread bookmark" in payload
    assert 'hx-patch="/bookmarks/1"' in payload
    bookmark = app.store.list()[0]

    captured, payload = request(
        app, "PATCH", f"/bookmarks/{bookmark.id}", htmx=True
    )
    assert captured["status"] == "200 OK"
    assert "read-bookmark" in payload
    assert 'id="bookmark-results"' in payload
    assert "0 unread bookmarks" in payload
    assert app.store.get(bookmark.id).is_read

    captured, payload = request(app, path="/bookmarks?filter=unread", htmx=True)
    assert captured["status"] == "200 OK"
    assert "No unread bookmarks yet." in payload

    captured, payload = request(
        app, "DELETE", f"/bookmarks/{bookmark.id}", htmx=True
    )
    assert captured["status"] == "200 OK"
    assert "No bookmarks yet." in payload
    assert app.store.list() == []


def test_invalid_url_returns_form_error(tmp_path):
    app = create_app(tmp_path / "bookmarks.db")
    captured, payload = request(
        app, "POST", "/bookmarks", {"url": "not a url"}, htmx=True
    )
    # Python 3.13 renamed the standard reason phrase to "Unprocessable Content".
    assert captured["status"].startswith("422 ")
    assert "Enter a full http:// or https:// URL." in payload
    assert 'role="alert"' in payload


def test_missing_bookmark_is_not_found(tmp_path):
    app = create_app(tmp_path / "bookmarks.db")
    captured, payload = request(app, "PATCH", "/bookmarks/999", htmx=True)
    assert captured["status"] == "404 Not Found"
    assert payload == "Bookmark not found"


def test_live_search_and_filter_context(tmp_path):
    app = create_app(tmp_path / "bookmarks.db")
    app.store.add("https://python.org", "Python")
    app.store.add("https://htmx.org", "htmx")

    captured, payload = request(app, path="/bookmarks?q=python", htmx=True)
    assert captured["status"] == "200 OK"
    assert "Python" in payload
    assert ">htmx</a>" not in payload
    assert 'value="python"' in payload
    assert 'hx-trigger="input changed delay:250ms, search"' in payload

    captured, payload = request(
        app, path="/bookmarks?filter=unread&q=python", htmx=True
    )
    assert 'hx-patch="/bookmarks/1?filter=unread&amp;q=python"' in payload

    captured, payload = request(
        app,
        "PATCH",
        "/bookmarks/1?filter=unread&q=python",
        htmx=True,
    )
    assert captured["status"] == "200 OK"
    assert "No bookmarks matching &quot;python&quot;." in payload


def test_inline_edit_uses_typed_form_binding(tmp_path):
    app = create_app(tmp_path / "bookmarks.db")
    bookmark = app.store.add("https://example.com/old", "Old title")

    captured, payload = request(
        app, path=f"/bookmarks/{bookmark.id}/edit", htmx=True
    )
    assert captured["status"] == "200 OK"
    assert '<form class="bookmark-editor"' in payload
    assert 'value="Old title"' in payload
    assert f'hx-put="/bookmarks/{bookmark.id}"' in payload

    captured, payload = request(
        app,
        "PUT",
        f"/bookmarks/{bookmark.id}",
        {"url": "https://example.com/new", "title": "New title"},
        htmx=True,
    )
    assert captured["status"] == "200 OK"
    assert "New title" in payload
    assert app.store.get(bookmark.id).url == "https://example.com/new"

    captured, payload = request(
        app,
        "PUT",
        f"/bookmarks/{bookmark.id}",
        {"url": "not a url", "title": "Nope"},
        htmx=True,
    )
    assert captured["status"].startswith("422 ")
    assert "Enter a full http:// or https:// URL." in payload
    assert '<form class="bookmark-editor"' in payload
