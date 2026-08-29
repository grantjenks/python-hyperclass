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

Routes return elements directly:

~~~python
from hyperclass import App

app = App()


@app.get("/")
def index(request):
    return counter(0)


@app.post("/counter")
def increment(request):
    return counter(request.form.int("value") + 1)


if __name__ == "__main__":
    app.run()
~~~

The application is a normal WSGI callable. The development server can use
Python's standard library; production deployment can use any WSGI server.

htmx supplies browser-to-server interaction without introducing a client-side
component runtime. Hyperclass should favor native HTML and CSS for local
behavior and use htmx when the server needs to participate.

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

Hyperclass is currently a design exploration. The examples above describe the
intended direction, not a released API.
