from dataclasses import dataclass, field
from io import BytesIO
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from hyperclass import (
    App,
    Values,
    button,
    closest,
    div,
    form,
    get,
    hidden,
    hx,
    input,
    name,
    outer_morph,
    output,
    patch,
    post,
    render,
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


def test_typed_route_parameter_is_passed_to_handler():
    app = App()

    @app.get("/items/<int:item_id>")
    def item(request, item_id):
        return div(f"item {item_id}")

    captured, payload = request(app, path="/items/42", htmx=True)
    assert captured["status"] == "200 OK"
    assert payload == "<div>item 42</div>"


def test_dynamic_route_with_wrong_method_is_method_not_allowed():
    app = App()

    @app.patch("/items/<int:item_id>")
    def update(request, item_id):
        return div(item_id)

    captured, payload = request(app, method="DELETE", path="/items/42")
    assert captured["status"] == "405 Method Not Allowed"
    assert payload == "Method Not Allowed"


def test_decorated_handler_is_a_reversible_route_reference():
    app = App()

    @app.patch("/items/<int:item_id>")
    def update(request, item_id):
        return div(item_id)

    assert update.path == "/items/<int:item_id>"
    assert update.url(item_id=42) == "/items/42"
    assert update.handler.__name__ == "update"
    assert render(
        button(
            "Update",
            hx=hx.patch(update, item_id=42, target=counter),
        )
    ) == (
        '<button hx-patch="/items/42" hx-target=".counter">Update</button>'
    )


def test_route_reference_supports_query_parameters_and_html_attributes():
    app = App()

    @app.get("/items")
    def items(request):
        return div()

    assert items.url(query={"filter": "unread"}) == "/items?filter=unread"
    assert render(form(action=items)) == '<form action="/items"></form>'


def test_app_subclass_collects_method_routes_and_binds_state():
    class Items(App):
        def __init__(self):
            self.values = {7: "seven"}
            super().__init__(title="Items")

        @get("/")
        def index(self, request):
            return div("items")

        @patch("/items/<int:item_id>")
        def update(self, request, item_id):
            return div(self.values[item_id])

    app = Items()
    captured, payload = request(app, method="PATCH", path="/items/7", htmx=True)
    assert captured["status"] == "200 OK"
    assert payload == "<div>seven</div>"
    assert Items.update.url(item_id=7) == "/items/7"
    assert app.update.url(item_id=7) == "/items/7"


def test_app_subclass_routes_can_be_inherited_and_overridden():
    class Base(App):
        @get("/")
        def index(self, request):
            return div("base")

        @post("/save")
        def save(self, request):
            return div("saved")

    class Child(Base):
        @get("/")
        def index(self, request):
            return div("child")

    captured, payload = request(Child(), htmx=True)
    assert captured["status"] == "200 OK"
    assert payload == "<div>child</div>"
    captured, payload = request(Child(), method="POST", path="/save", htmx=True)
    assert captured["status"] == "200 OK"
    assert payload == "<div>saved</div>"


def test_annotated_dataclass_is_bound_from_form_values():
    @dataclass
    class Entry:
        title: str
        priority: int = 0
        published: bool = False
        tags: list[str] = field(default_factory=list)

    app = App()

    @app.post("/entries")
    def create(request, form: Entry):
        return div(
            form.title,
            f"/{form.priority}/{form.published}/",
            ",".join(form.tags),
        )

    captured, payload = request(
        app,
        "POST",
        "/entries",
        [
            ("title", "Python"),
            ("priority", "3"),
            ("published", "on"),
            ("tags", "web"),
            ("tags", "wsgi"),
        ],
        htmx=True,
    )
    assert captured["status"] == "200 OK"
    assert payload == "<div>Python/3/True/web,wsgi</div>"


def test_dataclass_binding_uses_defaults_and_reports_bad_values():
    @dataclass
    class Entry:
        title: str
        priority: int = 7
        published: bool = False

    app = App()

    @app.post("/entries")
    def create(request, form: Entry):
        return div(f"{form.title}/{form.priority}/{form.published}")

    captured, payload = request(
        app, "POST", "/entries", {"title": "Python"}, htmx=True
    )
    assert captured["status"] == "200 OK"
    assert payload == "<div>Python/7/False</div>"

    captured, payload = request(
        app,
        "POST",
        "/entries",
        {"title": "Python", "priority": "high"},
        htmx=True,
    )
    assert captured["status"] == "400 Bad Request"
    assert payload == "invalid form value for priority: 'high'"


def test_values_accept_first_class_form_names():
    values = Values({"search_query": ["python", "wsgi"], "page": ["3"]})
    assert values[name.search_query] == "wsgi"
    assert values.get(name.search_query) == "wsgi"
    assert values.getlist(name.search_query) == ["python", "wsgi"]
    assert values.int(name.page) == 3
