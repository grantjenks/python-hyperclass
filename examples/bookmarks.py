"""A small, persistent bookmark inbox built entirely with Hyperclass."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from hyperclass import (
    App,
    Response,
    a,
    article,
    aside,
    button,
    closest,
    css,
    div,
    footer,
    form,
    fragment,
    h1,
    h2,
    header,
    hx,
    input,
    label,
    main,
    markup,
    outer_morph,
    p,
    partial,
    rem,
    section,
    small,
    span,
    strong,
)


@dataclass(frozen=True)
class Bookmark:
    id: int
    url: str
    title: str
    is_read: bool
    created_at: str


class BookmarkStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _bookmark(row: sqlite3.Row) -> Bookmark:
        return Bookmark(
            row["id"],
            row["url"],
            row["title"],
            bool(row["is_read"]),
            row["created_at"],
        )

    def add(self, url: str, title: str = "") -> Bookmark:
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Enter a full http:// or https:// URL.")
        url = parsed.geturl()
        title = title.strip() or parsed.hostname or url
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO bookmarks(url, title, created_at) VALUES (?, ?, ?)",
                (url, title, created_at),
            )
            bookmark_id = cursor.lastrowid
        return self.get(int(bookmark_id))

    def get(self, bookmark_id: int) -> Bookmark:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)
            ).fetchone()
        if row is None:
            raise LookupError(bookmark_id)
        return self._bookmark(row)

    def list(self, state: str = "all") -> list[Bookmark]:
        where = {
            "all": "",
            "unread": "WHERE is_read = 0",
            "read": "WHERE is_read = 1",
        }.get(state, "")
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM bookmarks {where} ORDER BY id DESC"
            ).fetchall()
        return [self._bookmark(row) for row in rows]

    def toggle(self, bookmark_id: int) -> Bookmark:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE bookmarks SET is_read = NOT is_read WHERE id = ?",
                (bookmark_id,),
            )
        if cursor.rowcount == 0:
            raise LookupError(bookmark_id)
        return self.get(bookmark_id)

    def delete(self, bookmark_id: int) -> None:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM bookmarks WHERE id = ?", (bookmark_id,)
            )
        if cursor.rowcount == 0:
            raise LookupError(bookmark_id)

    def unread_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM bookmarks WHERE is_read = 0"
            ).fetchone()
        return int(row["count"])


class bookmark_app(main):
    style = css(
        max_width=48 * rem,
        margin="3rem auto",
        padding="0 1rem",
        font_family="ui-sans-serif, system-ui, sans-serif",
        color="#172033",
    )


class app_header(header):
    style = css(margin_bottom=2 * rem)


class eyebrow(p):
    style = css(
        margin="0 0 .35rem",
        color="#6d28d9",
        font_size=".8rem",
        font_weight=700,
        letter_spacing=".12em",
        text_transform="uppercase",
    )


class bookmark_form(form):
    style = css(
        display="grid",
        grid_template_columns="2fr 1fr auto",
        gap=.75 * rem,
        padding=1 * rem,
        background="#f5f3ff",
        border="1px solid #ddd6fe",
        border_radius=.9 * rem,
        margin_bottom=1.25 * rem,
    )


class field_label(label):
    style = css(display="grid", gap=.3 * rem, font_size=.8 * rem, font_weight=650)


class text_field(input):
    style = css(
        box_sizing="border-box",
        width="100%",
        padding=".7rem .8rem",
        border="1px solid #c4b5fd",
        border_radius=.55 * rem,
        background="white",
        color="inherit",
        font="inherit",
    )


class primary_button(button):
    style = css(
        align_self="end",
        padding=".72rem 1rem",
        border=0,
        border_radius=.55 * rem,
        background="#6d28d9",
        color="white",
        font="inherit",
        font_weight=700,
        cursor="pointer",
    )


class error_message(p):
    style = css(
        grid_column="1 / -1",
        margin=0,
        color="#b91c1c",
        font_size=.9 * rem,
    )


class bookmark_toolbar(div):
    style = css(
        display="flex",
        align_items="center",
        justify_content="space-between",
        gap=1 * rem,
        margin="1rem 0",
    )


class filters(div):
    style = css(display="flex", gap=.5 * rem)


class filter_link(a):
    style = css(
        padding=".4rem .65rem",
        color="#5b21b6",
        text_decoration="none",
        border="1px solid #ddd6fe",
        border_radius=99 * rem,
        font_size=.9 * rem,
    )


class unread_badge(span):
    style = css(
        padding=".4rem .65rem",
        background="#ede9fe",
        color="#5b21b6",
        border_radius=99 * rem,
        font_size=.85 * rem,
        font_weight=700,
    )


class bookmark_list(section):
    style = css(display="grid", gap=.75 * rem)


class bookmark_card(article):
    style = css(
        display="grid",
        grid_template_columns="1fr auto",
        gap=".6rem 1rem",
        padding=1 * rem,
        border="1px solid #e2e8f0",
        border_left="4px solid #8b5cf6",
        border_radius=.75 * rem,
        background="white",
        box_shadow="0 1px 3px rgb(15 23 42 / .06)",
    )

    def __init__(self, bookmark: Bookmark):
        self.bookmark = bookmark

    def content(self):
        bookmark = self.bookmark
        yield div(
            h2(
                a(
                    bookmark.title,
                    href=bookmark.url,
                    target="_blank",
                    rel="noreferrer",
                )
            ),
            small(bookmark.url),
        )
        yield aside(
            button(
                "Mark unread" if bookmark.is_read else "Mark read",
                type="button",
                hx=hx.patch(
                    f"/bookmarks/{bookmark.id}",
                    target=closest(bookmark_card),
                    swap=outer_morph,
                ),
            ),
            button(
                "Delete",
                type="button",
                hx=hx.delete(
                    f"/bookmarks/{bookmark.id}",
                    target=closest(bookmark_card),
                    swap="delete",
                    confirm="Delete this bookmark?",
                ),
            ),
        )


class read:
    style = css(opacity=.58, border_left_color="#94a3b8")


class unread:
    style = css(border_left_color="#7c3aed")


class read_bookmark(bookmark_card, read):
    pass


class unread_bookmark(bookmark_card, unread):
    pass


class empty_state(p):
    style = css(
        padding="2rem 1rem",
        border="1px dashed #cbd5e1",
        border_radius=.75 * rem,
        color="#64748b",
        text_align="center",
    )


def bookmark_view(bookmark: Bookmark):
    kind = read_bookmark if bookmark.is_read else unread_bookmark
    return kind(bookmark)


def count_view(store: BookmarkStore):
    count = store.unread_count()
    noun = "bookmark" if count == 1 else "bookmarks"
    return unread_badge(f"{count} unread {noun}", id="unread-count")


def list_view(store: BookmarkStore, state: str = "all"):
    bookmarks = store.list(state)
    children = (
        [bookmark_view(bookmark) for bookmark in bookmarks]
        if bookmarks
        else [empty_state(f"No {state if state != 'all' else ''} bookmarks yet.")]
    )
    return bookmark_list(*children, id="bookmark-list")


def form_view(error: str = ""):
    children = [
        field_label(
            "URL",
            text_field(
                name="url",
                type="url",
                placeholder="https://example.com/article",
                required=True,
            ),
        ),
        field_label(
            "Title (optional)",
            text_field(name="title", placeholder="An excellent read"),
        ),
        primary_button("Save", type="submit"),
    ]
    if error:
        children.append(error_message(error, role="alert"))
    return bookmark_form(
        *children,
        method="post",
        action="/bookmarks",
        hx=hx.post(
            "/bookmarks", target=closest(bookmark_app), swap=outer_morph
        ),
    )


def app_view(store: BookmarkStore, error: str = ""):
    return bookmark_app(
        app_header(
            eyebrow("Hyperclass example"),
            h1("Bookmark inbox"),
            p("Save now. Read when the tab situation is less dramatic."),
        ),
        form_view(error),
        bookmark_toolbar(
            filters(
                *(
                    filter_link(
                        name.title(),
                        href=f"/bookmarks?filter={name}",
                        hx=hx.get(
                            f"/bookmarks?filter={name}",
                            target=bookmark_list,
                            swap=outer_morph,
                        ),
                    )
                    for name in ("all", "unread", "read")
                )
            ),
            count_view(store),
        ),
        list_view(store),
        footer(small("Python · SQLite · WSGI · htmx 4")),
    )


def create_app(database: str | Path) -> App:
    store = BookmarkStore(database)
    application = App(title="Hyperclass Bookmarks")

    @application.get("/")
    def index(request):
        return app_view(store)

    @application.post("/bookmarks")
    def create(request):
        try:
            store.add(request.form.get("url", ""), request.form.get("title", ""))
        except ValueError as error:
            return Response(app_view(store, str(error)), 422)
        return app_view(store)

    @application.get("/bookmarks")
    def bookmarks(request):
        state = request.query.get("filter", "all")
        return list_view(store, state if state in {"all", "unread", "read"} else "all")

    @application.patch("/bookmarks/<int:bookmark_id>")
    def toggle(request, bookmark_id):
        try:
            bookmark = store.toggle(bookmark_id)
        except LookupError:
            return Response("Bookmark not found", 404)
        return fragment(
            bookmark_view(bookmark),
            partial(count_view(store), id="unread-count", hx_swap=outer_morph),
        )

    @application.delete("/bookmarks/<int:bookmark_id>")
    def delete(request, bookmark_id):
        try:
            store.delete(bookmark_id)
        except LookupError:
            return Response("Bookmark not found", 404)
        return fragment(
            markup("<!-- bookmark deleted -->"),
            partial(count_view(store), id="unread-count", hx_swap=outer_morph),
        )

    application.store = store
    return application


app = create_app(os.environ.get("HYPERCLASS_BOOKMARKS_DB", "bookmarks.db"))


if __name__ == "__main__":
    app.run()
