# Hyperclass

> **Subclass the web.**

Hyperclass is a small experiment in building interactive web applications as
Python class hierarchies.

HTML elements are Python base classes. Python subclasses become CSS classes.
Styles follow inheritance. Routes are methods. Decorated handlers are URLs.
Interaction is ordinary HTTP over WSGI, with htmx 4 in the browser.

~~~console
pip install hyperclass
~~~

## Sixty-second tour

~~~python
from dataclasses import dataclass

from hyperclass import (
    App, button, css, div, form, get, grid, hx, input, outer_morph,
    post, rem,
)


class card(div):
    style = css(
        display=grid,
        gap=1 * rem,
        padding=1.25 * rem,
        border="1px solid #ddd",
        border_radius=.75 * rem,
    )


class guest_form(form):
    style = css(display=grid, gap=.75 * rem)

    def content(self):
        yield input(name="name", placeholder="Your name", required=True)
        yield button("Say hello", type="submit")


@dataclass
class Guest:
    name: str


class guestbook(App):
    @get("/")
    def index(self, request):
        return card(
            "Who are you?",
            guest_form(
                hx=hx.post(
                    guestbook.create,
                    target=card,
                    swap=outer_morph,
                )
            ),
        )

    @post("/guests")
    def create(self, request, form: Guest):
        return card(f"Hello, {form.name}!")


app = guestbook(title="Guestbook")
~~~

Run it:

~~~console
python -m hyperclass myapp:app
~~~

Then open <http://127.0.0.1:8000>. There is no JavaScript build, template
language, ASGI dependency, or CSS file hidden elsewhere.

## HTML classes are Python classes

Every built-in element can be subclassed:

~~~python
from hyperclass import css, div, grid, orange, rem


class card(div):
    style = css(display=grid, gap=1 * rem, padding=1.25 * rem)


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

produces ordinary, inspectable HTML:

~~~html
<div class="card warning-card">Something happened</div>
~~~

The first built-in HTML ancestor determines the tag. Each semantic subclass
contributes a CSS class. `snake_case` becomes `kebab-case`.

Multiple inheritance composes behavior and styles:

~~~python
class compact:
    style = css(padding=.5 * rem)


class clickable:
    style = css(cursor="pointer")


class result_card(card, compact, clickable):
    pass
~~~

~~~html
<div class="card compact clickable result-card"></div>
~~~

Components use normal Python state and methods:

~~~python
from hyperclass import strong


class greeting(card):
    def __init__(self, name):
        self.name = name

    def content(self):
        yield "Hello, "
        yield strong(self.name)
~~~

Text and attribute values are escaped by default. `markup(...)` is the explicit
escape hatch for trusted HTML.

## CSS is Python too

Base styles, pseudo-states, and media rules live on the component:

~~~python
from hyperclass import button, css, media, rem


class primary_button(button):
    style = css(
        padding=".7rem 1rem",
        background="#6d28d9",
        color="white",
        border=0,
        border_radius=.5 * rem,
    )
    hover = css(background="#5b21b6")
    focus_visible = css(outline="3px solid #c4b5fd")
    narrow = media(max_width=40 * rem, width="100%")
~~~

Pages collect only the rules used by their element tree. Python inheritance and
the CSS cascade cooperate instead of imitating one another.

## Classes and IDs are selectors

Classes can be used directly anywhere a selector is expected:

~~~python
hx.get(search, target=result_card)
closest(card)
~~~

IDs are lazy, interned Python objects:

~~~python
from hyperclass import id, span

span("3 unread", id=id.unread_count)
hx.get(count, target=id.unread_count)

assert id.unread_count is id.unread_count
~~~

As an HTML attribute, `id.unread_count` renders as `unread-count`. As a
selector, it renders as `#unread-count`.

## Routes are references, not strings

Application subclasses collect decorated method routes:

~~~python
from hyperclass import App, get, patch


class bookmarks(App):
    @get("/")
    def index(self, request):
        return bookmark_list(...)

    @patch("/bookmarks/<int:bookmark_id>")
    def toggle(self, request, bookmark_id):
        return bookmark_card(...)
~~~

Decorated handlers retain their route metadata:

~~~python
bookmarks.toggle.url(bookmark_id=42)
# '/bookmarks/42'

hx.patch(
    bookmarks.toggle,
    bookmark_id=42,
    target=bookmark_card,
)
~~~

Typed path parameters are converted before the handler runs. Query strings can
be attached with `.url(query={...})` or the `query=` option on an htmx request.

## Forms bind to dataclasses

Annotate a route parameter with a dataclass and Hyperclass builds it from the
submitted form:

~~~python
@dataclass
class NewBookmark:
    url: str
    title: str = ""


class bookmarks(App):
    @post("/bookmarks")
    def create(self, request, form: NewBookmark):
        self.store.add(form.url, form.title)
        return bookmark_list(...)
~~~

Binding supports strings, integers, floats, booleans, optional values, and
lists or tuples of those values. Dataclass defaults remain defaults. Invalid or
missing required values produce a `400 Bad Request`; application validation can
return a more specific `Response`.

The underlying values remain available as `request.form`, `request.query`,
`.get(...)`, `.getlist(...)`, and `.int(...)` when explicit parsing is clearer.

## WSGI and htmx 4

A Hyperclass application is a normal WSGI callable. Use the standard-library
development server:

~~~console
python -m hyperclass package.module:app
python -m hyperclass package.module:app --host 0.0.0.0 --port 9000
~~~

Production can use any WSGI server. Returning an element from an ordinary
browser request wraps it in a complete page. Returning the same element to an
htmx request sends only the fragment to swap.

`Page(...)` controls the document explicitly. Pages include a pinned htmx 4
asset from jsDelivr. htmx 4 `<hx-partial>` responses can update several
object-selected regions from one request.

## Try the examples

Clone the repository and run the persistent SQLite bookmark inbox:

~~~console
git clone https://github.com/grantjenks/python-hyperclass
cd python-hyperclass
python -m hyperclass examples.bookmarks:app
~~~

The bookmark app adds, searches, filters, edits, marks, and deletes bookmarks.
Its implementation is Python plus SQLite, WSGI, generated CSS, and htmx. It is
also a compact integration test for the framework's ideas.

For the smallest example:

~~~console
python -m hyperclass examples.counter:app
~~~

## Principles

- **Python is the authoring language.** Control flow, composition, inheritance,
  validation, and reuse are ordinary Python.
- **The browser remains the browser.** Hyperclass emits standard HTML and CSS
  rather than recreating the DOM on the server.
- **Classes mean classes.** Python inheritance has a visible relationship to
  HTML classes and the CSS cascade.
- **HTTP is the state boundary.** There is no hydration protocol or hidden
  client component lifecycle.
- **Output should be boring.** Generated markup stays readable in View Source
  and DevTools.
- **Small is a feature.** Prefer the standard library, WSGI, and a pinned htmx
  asset over a framework stack.

## Status

Hyperclass is deliberately pre-alpha: useful enough to build small applications
and young enough for its API to change. Python 3.10 through 3.14 are tested.

Apache-2.0 licensed.
