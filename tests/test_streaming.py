from io import BytesIO

from hyperclass import App, div, event, id, partial, post, stream


def test_event_stream_escapes_text_and_renders_hyperclass_partials():
    response = stream(
        [
            "<thinking>",
            event(partial(div("Hello", id=id.message[7]), id=id.message[7]), name="done"),
        ]
    )
    assert list(response.iter_text()) == [
        "data: &lt;thinking&gt;\n\n",
        "event: done\ndata: <hx-partial id=\"message-7\"><div id=\"message-7\">Hello</div></hx-partial>\n\n",
    ]


def test_lite_serves_streaming_responses_without_content_length():
    class StreamingApp(App):
        @post("/reply")
        def reply(self, request):
            return stream([div("one"), event(div("two"), name="done")])

    statuses = []
    headers = []

    def start_response(status, values):
        statuses.append(status)
        headers.extend(values)

    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/reply",
        "QUERY_STRING": "",
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "CONTENT_LENGTH": "0",
        "wsgi.input": BytesIO(),
        "HTTP_HX_REQUEST": "true",
    }
    chunks = list(StreamingApp()(environ, start_response))
    assert statuses == ["200 OK"]
    assert ("Content-Type", "text/event-stream; charset=utf-8") in headers
    assert not any(name == "Content-Length" for name, _ in headers)
    assert chunks == [
        b"data: <div>one</div>\n\n",
        b"event: done\ndata: <div>two</div>\n\n",
    ]
