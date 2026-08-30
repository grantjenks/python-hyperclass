from hyperclass import (
    Page,
    css,
    div,
    fragment,
    grid,
    id,
    media,
    orange,
    outer_morph,
    partial,
    rem,
    render,
    selector,
    span,
)


class card(div):
    style = css(display=grid, gap=1 * rem, padding=1.25 * rem)


class warning_card(card):
    style = css(border_color=orange, background=orange.fade(0.08))


def test_semantic_subclasses_render_as_html_classes():
    assert render(warning_card("Careful")) == (
        '<div class="card warning-card">Careful</div>'
    )


def test_multiple_inheritance_composes_classes_in_declaration_order():
    class compact:
        style = css(padding=0.5 * rem)

    class clickable:
        style = css(cursor="pointer")

    class result_card(card, compact, clickable):
        pass

    assert render(result_card()) == (
        '<div class="card compact clickable result-card"></div>'
    )


def test_content_and_attributes_are_escaped():
    assert render(div("<unsafe>", title='a "quote"')) == (
        '<div title="a &quot;quote&quot;">&lt;unsafe&gt;</div>'
    )


def test_class_and_instance_are_selectors():
    instance = warning_card(id="notice")
    assert selector(warning_card) == ".warning-card"
    assert warning_card.selector == ".warning-card"
    assert selector(instance) == "#notice"
    assert instance.selector == "#notice"


def test_page_collects_styles_and_pins_htmx_4():
    document = Page(warning_card("Careful"), title="Demo").render()
    assert document.startswith("<!doctype html>")
    assert "<title>Demo</title>" in document
    assert ".card{display:grid;gap:1rem;padding:1.25rem}" in document
    assert (
        ".warning-card{border-color:orange;background:rgb(255 165 0 / 0.08)}"
        in document
    )
    assert "https://cdn.jsdelivr.net/npm/htmx.org@4.0.0" in document


def test_fragment_and_htmx_partial_render_sibling_updates():
    value = fragment(
        div("primary"),
        partial(span("3", id="count"), id="count", hx_swap=outer_morph),
    )
    assert render(value) == (
        '<div>primary</div><hx-partial id="count" hx-swap="outerMorph">'
        '<span id="count">3</span></hx-partial>'
    )


def test_ids_are_lazy_interned_python_references():
    assert id.unread_count is id.unread_count
    assert str(id.unread_count) == "unread-count"
    assert id.unread_count.selector == "#unread-count"
    assert selector(id.unread_count) == "#unread-count"
    assert render(span("3", id=id.unread_count)) == (
        '<span id="unread-count">3</span>'
    )


def test_page_collects_state_and_media_styles_from_classes():
    class interactive_card(card):
        hover = css(background="lavender")
        focus_visible = css(outline="2px solid purple")
        narrow = media(max_width=40 * rem, grid_template_columns="1fr")

    document = Page(interactive_card()).render()
    assert ".interactive-card:hover{background:lavender}" in document
    assert (
        ".interactive-card:focus-visible{outline:2px solid purple}" in document
    )
    assert (
        "@media (max-width:40rem){.interactive-card{grid-template-columns:1fr}}"
        in document
    )
