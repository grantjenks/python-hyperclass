from hyperclass import (
    App,
    button,
    closest,
    css,
    div,
    form,
    grid,
    hidden,
    hx,
    input,
    orange,
    outer_morph,
    output,
    rem,
)


class card(div):
    style = css(
        display=grid,
        gap=0.75 * rem,
        padding=1.25 * rem,
        border="1px solid #ddd",
        border_radius=0.75 * rem,
        max_width=16 * rem,
        margin="4rem auto",
        font_family="system-ui, sans-serif",
    )


class counter(card):
    style = css(border_color=orange)

    def __init__(self, value):
        self.value = value

    def content(self):
        yield output(str(self.value), aria_live="polite")
        yield form(
            input(type=hidden, name="value", value=self.value),
            button("+1", type="submit"),
            hx=hx.post(
                "/counter",
                target=closest(counter),
                swap=outer_morph,
            ),
        )


app = App(title="Hyperclass Counter")


@app.get("/")
def index(request):
    return counter(0)


@app.post("/counter")
def increment(request):
    return counter(request.form.int("value") + 1)


if __name__ == "__main__":
    app.run()
