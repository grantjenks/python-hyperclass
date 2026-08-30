from hyperclass import closest, div, hx, id, name, outer_morph, render


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
