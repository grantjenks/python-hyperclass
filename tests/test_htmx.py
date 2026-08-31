from hyperclass import Page, closest, div, find, hx, id, name, outer_morph, render


class counter(div):
    pass


def test_htmx_request_attributes_accept_class_selectors():
    value = div(
        "Update",
        hx=hx.post(
            "/counter",
            target=closest(counter),
            swap=outer_morph,
        ),
    )
    assert render(value) == (
        '<div hx-post="/counter" hx-target="closest .counter" '
        'hx-swap="outerMorph">Update</div>'
    )


def test_plain_class_target_becomes_a_selector():
    assert render(div(hx=hx.get("/counter", target=counter))) == (
        '<div hx-get="/counter" hx-target=".counter"></div>'
    )


def test_class_attributes_can_declare_htmx_and_name_selectors():
    class live_search(div):
        hx = hx.get(
            "/search",
            include=name.query,
            target=id.results,
            swap=outer_morph,
        )

    assert render(live_search()) == (
        '<div class="live-search" hx-get="/search" '
        'hx-include="[name=&quot;query&quot;]" hx-target="#results" '
        'hx-swap="outerMorph"></div>'
    )


def test_htmx_attributes_compose_and_support_modifiers():
    attributes = (
        hx.post("/messages", target=id.messages, stream=True, disable=find("fieldset"))
        | hx.on.before_request("this.reset()")
        | hx.headers.inherited({"X-CSRFToken": "token"})
    )
    document = Page(div(hx=attributes)).render()
    assert 'hx-post="/messages"' in document
    assert 'hx-target="#messages"' in document
    assert 'hx-disable="find fieldset"' in document
    assert 'hx-on::before:request="this.reset()"' in document
    assert 'hx-headers:inherited="{&quot;X-CSRFToken&quot;:&quot;token&quot;}"' in document
    assert "dist/ext/hx-sse.min.js" in document


def test_htmx_sse_connect_loads_extension_without_a_fake_html_attribute():
    document = Page(div(hx=hx.sse.connect("/events"))).render()
    assert 'hx-sse:connect="/events"' in document
    assert "dist/ext/hx-sse.min.js" in document
    assert "_hyperclass" not in document
