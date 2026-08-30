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
    assert '<hx-partial id="unread-count" hx-swap="outerMorph">' in payload
    assert "0 unread bookmarks" in payload
    assert app.store.get(bookmark.id).is_read

    captured, payload = request(app, path="/bookmarks?filter=unread", htmx=True)
    assert captured["status"] == "200 OK"
    assert "No unread bookmarks yet." in payload

    captured, payload = request(
        app, "DELETE", f"/bookmarks/{bookmark.id}", htmx=True
    )
    assert captured["status"] == "200 OK"
    assert "bookmark deleted" in payload
    assert "<hx-partial" in payload
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
