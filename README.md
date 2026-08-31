# Hyperclass

> **Subclass the web.**

Hyperclass is a small experiment in building interactive web applications as
Python class hierarchies.

HTML elements are Python base classes. Python subclasses become CSS classes.
Styles follow inheritance. Routes are methods. Decorated handlers are URLs.
Interaction is ordinary HTTP, with htmx 4 in the browser. Run it with the tiny
built-in WSGI host, or put the same components and routes inside Flask or
Django.

~~~console
pip install hyperclass
# or: pip install "hyperclass[flask]"
# or: pip install "hyperclass[django]"
~~~

## Sixty-second tour

~~~python
from dataclasses import dataclass

from hyperclass import (
    App, button, css, div, form, get, grid, hx, input, outer_morph,
    name, post, rem,
)


class card(div):
    style = css(
        display=grid,
        gap=1 * rem,
        padding=1.25 * rem,
        border="1px solid #ddd",
        border_radius=.75 * rem,
    )


class guest_name(input):
    name = name.name
    placeholder = "Your name"
    required = True


class guest_form(form):
    style = css(display=grid, gap=.75 * rem)

    def content(self):
        yield guest_name()
        yield button("Say hello", type="submit")


@dataclass
class Guest:
    name: str


class GuestbookRoutes:
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


class guestbook(GuestbookRoutes, App):
    pass


app = guestbook(title="Guestbook")
~~~

Run it:

~~~console
python -m hyperclass myapp:app
~~~

Then open <http://127.0.0.1:8000>. There is no JavaScript build, template
language, ASGI dependency, or CSS file hidden elsewhere.

`App` is the zero-dependency host and remains the shortest way to start. The
HTML, CSS, htmx, selector, route, and form-binding APIs are shared by every
host.

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

## HTML attributes inherit too

Non-private class values become default HTML attributes:

~~~python
from hyperclass import a, input, name


class external_link(a):
    target = "_blank"
    rel = "noreferrer"


class url_field(input):
    type = "url"
    name = name.url
    required = True
    autocomplete = "url"
~~~

The defaults follow the same base-to-derived order as styles. Subclasses and
multiple-inheritance mixins can override them. Attributes passed to an instance
win last:

~~~python
external_link("Same tab", href="/", target="_self", rel=None)
~~~

`None` and `False` suppress an inherited attribute. Underscores in Python names
become hyphens, so `aria_label` renders as `aria-label`. Boolean `True` renders
as a valueless HTML attribute. An `hx = hx.get(...)` class default expands into
the corresponding htmx attributes.

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

Pages collect only the rules used by their element tree. Rules use the concrete
semantic class chain as their selector, so Python inheritance and the CSS
cascade cooperate even when new component styles arrive later.

## Classes, IDs, and names are selectors

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

Form names work the same way while preserving Python underscores:

~~~python
from hyperclass import name

input(name=name.search_query)
request.form[name.search_query]
hx.get(search, include=name.search_query, target=id.results)
~~~

As an attribute, `name.search_query` renders as `search_query`. As a selector,
it renders as `[name="search_query"]`. Repeated access returns the same object.

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

Decorated handlers retain their route metadata. Their URLs are lazy values:

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
The URL is resolved only while rendering, so a Flask mount prefix or Django URL
namespace is included automatically. Components never need to know where their
application was mounted.

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
return `(body, status)`.

The lightweight host also exposes `request.form` and `request.query`. Flask and
Django handlers receive their native request objects, so use `request.form` and
`request.args` in Flask or `request.POST` and `request.GET` in Django. Their
Werkzeug `MultiDict` and Django `QueryDict` values feed the same dataclass
binder without a request wrapper.

## Three hosts, one component model

### Lightweight

Top-level `App` is a deliberately small, dependency-free WSGI application. Use
the standard-library development server:

~~~console
python -m hyperclass package.module:app
python -m hyperclass package.module:app --host 0.0.0.0 --port 9000
~~~

Production can use any WSGI server. Returning an element from an ordinary
browser request wraps it in a complete page. Returning the same element to an
htmx request sends only the fragment to swap.

The explicit import is `from hyperclass.lite import App`; top-level
`from hyperclass import App` is its convenient and backward-compatible alias.

### Flask

Install `hyperclass[flask]`, then subclass the native Flask host:

~~~python
from hyperclass.flask import App


class guestbook(GuestbookRoutes, App):
    pass


app = guestbook(title="Guestbook")
~~~

`hyperclass.flask.App` is a real `flask.Flask` subclass. Route handlers receive
Flask's request object, native Flask responses pass through unchanged, and
Flask extensions, middleware, test clients, and WSGI deployment continue to
work normally. Hyperclass route references use `url_for()` when rendered.

### Django

Install `hyperclass[django]`, create the route application, and include it in a
normal Django URLconf:

~~~python
from django.urls import include, path
from hyperclass.django import App


class guestbook(GuestbookRoutes, App):
    pass


guestbook_app = guestbook(title="Guestbook", namespace="guestbook")

urlpatterns = [
    path("guestbook/", include(guestbook_app.urls)),
]
~~~

Handlers receive native `HttpRequest` objects and may return native
`HttpResponse` objects. Routes sharing a path are dispatched by HTTP method,
and route references use Django `reverse()`, including the mount and namespace.
Full Hyperclass pages inherit an htmx `X-CSRFToken` header and request a Django
CSRF cookie, so unsafe htmx requests work with `CsrfViewMiddleware` enabled.

### htmx 4

`Page(...)` controls the document explicitly. Pages include a pinned htmx 4
asset from jsDelivr. htmx 4 `<hx-partial>` responses can update several
object-selected regions from one request.

When an htmx response introduces a component that was not present on the first
page, Hyperclass includes its CSS in a partial targeting the page's stable
`hyperclass-styles` stylesheet. The new fragment is styled immediately, without
a reload or a global CSS build.

## Try the examples

Clone the repository and run the persistent SQLite bookmark inbox:

~~~console
git clone https://github.com/grantjenks/python-hyperclass
cd python-hyperclass
python -m hyperclass examples.bookmarks:app
# Flask: flask --app examples.bookmarks_flask run
~~~

The bookmark app adds, searches, filters, edits, marks, and deletes bookmarks.
Its route mixin and component tree are shared by Lite, Flask, and Django. The
same browser contract adds, toggles, edits, searches, and deletes a bookmark on
all three hosts.

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
- **Choose your host.** Start with the standard library, or use Flask/Django
  where their ecosystem and infrastructure are already the right answer.

## Development

Run the Python test matrix locally with:

~~~console
uvx nox -s tests
~~~

The browser contract starts each of the Lite, Flask, and Django bookmark hosts
on an ephemeral port and exercises add, toggle, edit, search, and delete
through htmx in Chromium:

~~~console
uvx nox -s browser
~~~

Playwright is used only by that development session and is not a Hyperclass
runtime dependency.

## Status

Hyperclass is deliberately pre-alpha: useful enough to build small applications
and young enough for its API to change. Python 3.10 through 3.14 are tested.

Apache-2.0 licensed.
