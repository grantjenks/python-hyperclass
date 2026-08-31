from dataclasses import dataclass

from flask import Request, Response

from hyperclass import div, form, get, hx, post, render, stream
from hyperclass.flask import App
from examples.bookmarks import BookmarkRoutes


@dataclass
class Entry:
    title: str


class FlaskRoutes(App):
    seen_request = None

    @get("/")
    def index(self, request):
        return form(
            "Create",
            action=FlaskRoutes.create.url(item_id=7),
            hx=hx.post(FlaskRoutes.create, item_id=7),
        )

    @post("/items/<int:item_id>")
    def create(self, request, item_id, form: Entry):
        type(self).seen_request = request._get_current_object()
        return div(f"{item_id}:{form.title}")

    @get("/native")
    def native(self, request):
        return Response("native flask", status=201)


def test_flask_resolves_lazy_routes_at_the_mount_point():
    app = FlaskRoutes(title="Flask host")
    client = app.test_client()
    response = client.get("/", environ_overrides={"SCRIPT_NAME": "/mounted"})
    assert response.status_code == 200
    assert 'action="/mounted/items/7"' in response.text
    assert 'hx-post="/mounted/items/7"' in response.text


def test_flask_passes_native_requests_and_binds_werkzeug_forms():
    app = FlaskRoutes()
    response = app.test_client().post(
        "/items/3",
        data={"title": "Python"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert response.text == "<div>3:Python</div>"
    assert isinstance(FlaskRoutes.seen_request, Request)


def test_flask_native_responses_pass_through():
    response = FlaskRoutes().test_client().get("/native")
    assert response.status_code == 201
    assert response.text == "native flask"


def test_flask_instance_decorators_return_route_references():
    app = App()

    @app.get("/")
    def index(request):
        return div("dynamic")

    assert render(form(action=index)) == '<form action="/"></form>'
    assert app.test_client().get("/").text.endswith("<div>dynamic</div></body></html>")


def test_flask_bookmark_routes_read_native_query_keys(tmp_path):
    class Bookmarks(BookmarkRoutes, App):
        pass

    app = Bookmarks(tmp_path / "flask-query.db")
    app.store.add("https://python.org", "Python")
    response = app.test_client().get(
        "/bookmarks?q=missing&filter=all",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "No bookmarks matching &quot;missing&quot;." in response.text


def test_flask_streams_server_sent_events():
    app = App()

    @app.get("/events")
    def events(request):
        return stream([div("one"), div("two")])

    response = app.test_client().get("/events")
    assert response.content_type == "text/event-stream; charset=utf-8"
    assert response.text.startswith("data: <div>one</div>\n\n")
    assert response.text.endswith("data: <div>two</div>\n\n")
