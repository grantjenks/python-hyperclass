# Hyperclass

> **Subclass the web.**

Hyperclass is an experiment in building interactive web applications as Python
class hierarchies.

HTML elements are Python base classes. Python subclasses become CSS classes.
Styles follow inheritance. Interaction is ordinary HTTP over WSGI, with htmx in
the browser.

~~~python
from hyperclass import css, div, grid, orange, rem


class card(div):
    style = css(
        display=grid,
        gap=1 * rem,
        padding=1.25 * rem,
        border_radius=0.75 * rem,
    )


class warning_card(card):
    style = css(
        border_color=orange,
        background=orange.fade(0.08),
    )
~~~

Calling:

~~~python
warning_card("Something happened")
~~~

would produce ordinary, inspectable HTML:

~~~html
<div class="card warning-card">Something happened</div>
~~~

The Python inheritance hierarchy and the CSS cascade cooperate instead of
imitating one another.

## The model

Hyperclass treats classes and instances differently:

- An element's first built-in HTML ancestor determines its tag.
- Each semantic subclass contributes a CSS class.
- `snake_case` class names become `kebab-case`.
- Styles are inherited and emitted in method-resolution order.
- Multiple inheritance composes multiple CSS classes.
- Classes are also usable as selectors and htmx targets.
- Instances contain attributes, state, and child content.
- Typed route parameters turn URL segments into handler arguments.
- htmx 4 partials can update several object-selected regions from one response.
- `id.some_name` creates an interned Python reference for `some-name`.
- Decorated handlers are reversible route references; URLs need not be repeated.

~~~python
class compact:
    style = css(padding=0.5 * rem)


class clickable:
    style = css(cursor="pointer")


class result_card(card, compact, clickable):
    pass
~~~

A `result_card` would render as:

~~~html
<div class="card compact clickable result-card"></div>
~~~

## Components

Components are element subclasses with ordinary Python behavior:

~~~python
from hyperclass import (
    button,
    closest,
    form,
    hidden,
    hx,
    input,
    outer_morph,
    output,
)


class counter(card):
    def __init__(self, value):
        self.value = value

    def content(self):
        yield output(str(self.value))
        yield form(
            input(type=hidden, name="value", value=self.value),
            button("+1", type="submit"),
            hx=hx.post(
                "/counter",
                target=closest(counter),
                swap=outer_morph,
            ),
        )
~~~

The class `counter` simultaneously represents:

- a Python type;
- an HTML `<div>`;
- the CSS selector `.counter`;
- a reusable styled component;
- a valid htmx target.

## WSGI and htmx

Application subclasses collect decorated method routes:

~~~python
from hyperclass import App, get, post


class counter_app(App):
    @get("/")
    def index(self, request):
        return counter(0)

    @post("/counter")
    def increment(self, request):
        return counter(request.form.int("value") + 1)


app = counter_app()
if __name__ == "__main__":
    app.run()
~~~

The application is a normal WSGI callable. The development server can use
Python's standard library; production deployment can use any WSGI server.

Decorated handlers retain their routing metadata, so application code can refer
to Python rather than repeat URL strings:

~~~python
hx.patch(
    increment,
    target=closest(counter),
    swap=outer_morph,
)
~~~

Typed path parameters are supplied alongside htmx options. Class attributes
make the handler available to components without a route registry:

~~~python
hx.patch(
    bookmarks.toggle,
    bookmark_id=bookmark.id,
    target=closest(bookmark_card),
)
~~~

The same endpoint exposes `.url(...)` for ordinary links and form actions. IDs
work similarly: `id.unread_count` renders as `unread-count` in an HTML
attribute and as `#unread-count` when used as a selector.

htmx supplies browser-to-server interaction without introducing a client-side
component runtime. Hyperclass should favor native HTML and CSS for local
behavior and use htmx when the server needs to participate.

## Pages

For ordinary browser requests, returning an element wraps it in a complete page.
For htmx requests, the same route returns only the fragment to swap. Use
`Page` when you want to control the document explicitly:

~~~python
from hyperclass import Page

return Page(counter(0), title="Counter")
~~~

Pages collect the styles used by their element tree and include pinned htmx
4.0.0 from its CDN.

## Responsive CSS and states

Pseudo-states and media rules are ordinary class attributes:

~~~python
from hyperclass import css, media, rem


class primary_button(button):
    style = css(background="#6d28d9", color="white")
    hover = css(background="#5b21b6")
    focus_visible = css(outline="3px solid #c4b5fd")
    narrow = media(max_width=40 * rem, width="100%")
~~~

State names translate underscores to CSS hyphens, and named media rules can use
Python values for width, orientation, and color-scheme conditions. They follow
the same inheritance and collection rules as base styles.

## Try the examples

The repository includes the counter and a complete SQLite bookmark inbox:

~~~console
git clone https://github.com/grantjenks/python-hyperclass
cd python-hyperclass
python -m examples.bookmarks
~~~

Then open <http://127.0.0.1:8000>. The bookmark app supports adding, filtering,
marking read or unread, and deleting bookmarks. Its implementation is still only
Python and the standard library: semantic subclasses style read and unread
cards, routes such as `/bookmarks/<int:bookmark_id>` receive typed arguments,
and htmx 4 `<hx-partial>` responses update a card and the unread count together.

Use `python -m examples.counter` for the smaller introduction.

## Principles

- **Python is the authoring language.** Control flow, composition, inheritance,
  and reuse are ordinary Python.
- **The browser remains the browser.** Hyperclass emits standard HTML and CSS
  rather than recreating the DOM on the server.
- **Classes mean classes.** Python inheritance has a visible, predictable
  relationship to HTML classes and the CSS cascade.
- **HTTP is the state boundary.** There is no hydration protocol or hidden
  client component lifecycle.
- **Output should be boring.** Generated markup remains readable in View Source
  and DevTools.
- **Small is a feature.** Prefer the standard library, WSGI, and a pinned htmx
  asset over a large framework stack.

## Status

Version 0.0.2 is the first working vertical slice: HTML elements, semantic
subclasses, inherited and responsive CSS, object and ID selectors, htmx
attributes and partials, pages, request parsing, reversible typed WSGI routing,
class-based applications, and a persistent example application. The API remains
deliberately pre-alpha.
