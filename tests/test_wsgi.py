from io import BytesIO
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from hyperclass import (
    App,
    button,
    closest,
    div,
    form,
    hidden,
    hx,
    input,
    outer_morph,
    output,
)


class counter(div):
    def __init__(self, value):
        self.value = value

    def content(self):
        yield output(str(self.value))
        yield form(
            input(type=hidden, name="value", value=self.value),
            button("+1", type="submit"),
            hx=hx.post("/counter", target=closest(counter), swap=outer_morph),
        )


def make_app():
    app = App(title="Counter")

    @app.get("/")
    def index(request):
        return counter(0)

    @app.post("/counter")
    def increment(request):
        return counter(request.form.int("value") + 1)

    return app


def request(app, method="GET", path="/", data=None, htmx=False):
    environ = {}
    setup_testing_defaults(environ)
    body = urlencode(data or {}).encode()
    environ.update(
        REQUEST_METHOD=method,
        PATH_INFO=path,
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


def test_get_returns_a_complete_page():
    captured, payload = request(make_app())
    assert captured["status"] == "200 OK"
    assert payload.startswith("<!doctype html>")
    assert "<title>Counter</title>" in payload
    assert '<div class="counter"><output>0</output>' in payload
    assert 'hx-target="closest .counter"' in payload


def test_htmx_post_returns_only_the_replacement_fragment():
    captured, payload = request(
        make_app(), "POST", "/counter", {"value": "4"}, htmx=True
    )
    assert captured["status"] == "200 OK"
    assert payload.startswith('<div class="counter"><output>5</output>')
    assert "<!doctype html>" not in payload


def test_bad_form_value_is_a_bad_request():
    captured, payload = request(
        make_app(), "POST", "/counter", {"value": "nope"}, htmx=True
    )
    assert captured["status"] == "400 Bad Request"
    assert "invalid integer form value" in payload


def test_missing_route_is_not_found():
    captured, payload = request(make_app(), path="/missing")
    assert captured["status"] == "404 Not Found"
    assert payload == "Not Found"
