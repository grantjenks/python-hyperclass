from io import BytesIO
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from examples.chat import create_app


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


def test_chat_page_uses_indexed_ids_routes_and_sse_extension(tmp_path):
    app = create_app(tmp_path / "chat.db", model=lambda prompt: ["Hello"], token_delay=0)
    captured, payload = request(app)
    conversation = app.store.latest_or_create()

    assert captured["status"] == "200 OK"
    assert "dist/ext/hx-sse.min.js" in payload
    assert f'hx-post="/chats/{conversation.id}/messages"' in payload
    assert 'hx-disable="find .composer-fields"' in payload
    assert 'hx-on::before:request="this.reset()"' in payload


def test_chat_stream_persists_and_targets_each_message(tmp_path):
    app = create_app(
        tmp_path / "chat.db",
        model=lambda prompt: ["Hello ", prompt],
        token_delay=0,
    )
    conversation = app.store.latest_or_create()
    captured, payload = request(
        app,
        "POST",
        f"/chats/{conversation.id}/messages",
        {"message": "Python"},
        htmx=True,
    )

    assert captured["headers"]["Content-Type"] == "text/event-stream; charset=utf-8"
    assert f'hx-target="#messages" hx-swap="append"' in payload
    messages = app.store.messages(conversation.id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assistant = messages[-1]
    assert assistant.content == "Hello Python"
    assert assistant.status == "complete"
    assert f'id="message-{assistant.id}"' in payload
    assert f'hx-target="#message-{assistant.id}" hx-swap="outerMorph"' in payload


def test_chat_accepts_an_injected_model_and_regenerates(tmp_path):
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        yield "Replied"

    app = create_app(tmp_path / "chat.db", model=model, token_delay=0)
    conversation = app.store.latest_or_create()
    request(
        app,
        "POST",
        f"/chats/{conversation.id}/messages",
        {"message": "Again"},
        htmx=True,
    )
    assistant = app.store.messages(conversation.id)[-1]
    captured, payload = request(
        app,
        "POST",
        f"/messages/{assistant.id}/regenerate",
        htmx=True,
    )
    assert captured["status"] == "200 OK"
    assert "Replied" in payload
    assert prompts == ["Again", "Again"]
