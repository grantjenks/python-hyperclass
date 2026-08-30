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
    get,
    h1,
    h2,
    header,
    hx,
    id,
    input,
    label,
    main,
    markup,
    media,
    outer_morph,
    p,
    partial,
    patch,
    post,
    rem,
    section,
    small,
    span,
)
from hyperclass import delete_route


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
    narrow = media(
        max_width=40 * rem,
        margin="1.25rem auto",
        padding="0 .75rem",
    )


class app_header(header):
    style = css(margin_bottom=2 * rem)
    narrow = media(max_width=40 * rem, margin_bottom=1.25 * rem)


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
        grid_template_columns="minmax(0, 2fr) minmax(0, 1fr) auto",
        gap=.75 * rem,
        padding=1 * rem,
        background="#f5f3ff",
        border="1px solid #ddd6fe",
        border_radius=.9 * rem,
        margin_bottom=1.25 * rem,
    )
    narrow = media(max_width=40 * rem, grid_template_columns="1fr")


class field_label(label):
    style = css(
        display="grid",
        gap=.3 * rem,
        min_width=0,
        font_size=.8 * rem,
        font_weight=650,
    )


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
        font_size=1 * rem,
    )
    focus = css(outline="2px solid #8b5cf6", outline_offset="1px")


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
        min_height=2.75 * rem,
    )
    hover = css(background="#5b21b6")
    focus_visible = css(outline="3px solid #c4b5fd", outline_offset="2px")
    narrow = media(max_width=40 * rem, width="100%")


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
    narrow = media(
        max_width=40 * rem,
        display="grid",
        justify_content="stretch",
    )


class filters(div):
    style = css(display="flex", gap=.5 * rem, flex_wrap="wrap")


class filter_link(a):
    style = css(
        padding=".4rem .65rem",
        color="#5b21b6",
        text_decoration="none",
        border="1px solid #ddd6fe",
        border_radius=99 * rem,
        font_size=.9 * rem,
    )
    hover = css(background="#f5f3ff", border_color="#8b5cf6")
    focus_visible = css(outline="2px solid #8b5cf6", outline_offset="2px")


class unread_badge(span):
    style = css(
        padding=".4rem .65rem",
        background="#ede9fe",
        color="#5b21b6",
        border_radius=99 * rem,
        font_size=.85 * rem,
        font_weight=700,
    )
    narrow = media(max_width=40 * rem, justify_self="start")


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
    narrow = media(max_width=40 * rem, grid_template_columns="minmax(0, 1fr)")

    def __init__(self, bookmark: Bookmark):
        self.bookmark = bookmark

    def content(self):
        bookmark = self.bookmark
        yield bookmark_copy(
            bookmark_title(
                bookmark_link(
                    bookmark.title,
                    href=bookmark.url,
                    target="_blank",
                    rel="noreferrer",
                )
            ),
            bookmark_url(bookmark.url),
        )
        yield card_actions(
            action_button(
                "Mark unread" if bookmark.is_read else "Mark read",
                type="button",
                hx=hx.patch(
                    bookmarks.toggle,
                    bookmark_id=bookmark.id,
                    target=closest(bookmark_card),
                    swap=outer_morph,
                ),
            ),
            delete_button(
                "Delete",
                type="button",
                hx=hx.delete(
                    bookmarks.delete,
                    bookmark_id=bookmark.id,
                    target=closest(bookmark_card),
                    swap="delete",
                    confirm="Delete this bookmark?",
                ),
            ),
        )


class bookmark_copy(div):
    style = css(min_width=0)


class bookmark_title(h2):
    style = css(margin="0 0 .25rem", font_size=1.05 * rem, line_height=1.3)


class bookmark_link(a):
    style = css(color="#2e1065", text_decoration="none")
    hover = css(text_decoration="underline")
    focus_visible = css(outline="2px solid #8b5cf6", outline_offset="2px")


class bookmark_url(small):
    style = css(color="#64748b", overflow_wrap="anywhere")


class card_actions(aside):
    style = css(
        display="flex",
        align_items="start",
        gap=.5 * rem,
        flex_wrap="wrap",
    )


class action_button(button):
    style = css(
        min_height=2.5 * rem,
        padding=".5rem .7rem",
        border="1px solid #cbd5e1",
        border_radius=.5 * rem,
        background="white",
        color="#334155",
        font="inherit",
        font_size=.85 * rem,
        cursor="pointer",
    )
    hover = css(background="#f8fafc", border_color="#94a3b8")
    focus_visible = css(outline="2px solid #8b5cf6", outline_offset="2px")


class delete_button(action_button):
    style = css(color="#b91c1c")


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
    return unread_badge(f"{count} unread {noun}", id=id.unread_count)


def list_view(
    store: BookmarkStore, state: str = "all"
):
    bookmarks = store.list(state)
    children = (
        [bookmark_view(bookmark) for bookmark in bookmarks]
        if bookmarks
        else [empty_state(f"No {state if state != 'all' else ''} bookmarks yet.")]
    )
    return bookmark_list(*children, id=id.bookmark_list)


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
        action=bookmarks.create,
        hx=hx.post(
            bookmarks.create, target=closest(bookmark_app), swap=outer_morph
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
                        href=bookmarks.listing.url(query={"filter": name}),
                        hx=hx.get(
                            bookmarks.listing,
                            query={"filter": name},
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


class bookmarks(App):
    def __init__(self, database: str | Path):
        self.store = BookmarkStore(database)
        super().__init__(title="Hyperclass Bookmarks")

    @get("/")
    def index(self, request):
        return app_view(self.store)

    @post("/bookmarks")
    def create(self, request):
        try:
            self.store.add(
                request.form.get("url", ""), request.form.get("title", "")
            )
        except ValueError as error:
            return Response(app_view(self.store, str(error)), 422)
        return app_view(self.store)

    @get("/bookmarks")
    def listing(self, request):
        state = request.query.get("filter", "all")
        return list_view(
            self.store,
            state if state in {"all", "unread", "read"} else "all",
        )

    @patch("/bookmarks/<int:bookmark_id>")
    def toggle(self, request, bookmark_id):
        try:
            bookmark = self.store.toggle(bookmark_id)
        except LookupError:
            return Response("Bookmark not found", 404)
        return fragment(
            bookmark_view(bookmark),
            partial(
                count_view(self.store), id=id.unread_count, hx_swap=outer_morph
            ),
        )

    @delete_route("/bookmarks/<int:bookmark_id>")
    def delete(self, request, bookmark_id):
        try:
            self.store.delete(bookmark_id)
        except LookupError:
            return Response("Bookmark not found", 404)
        return fragment(
            markup("<!-- bookmark deleted -->"),
            partial(
                count_view(self.store), id=id.unread_count, hx_swap=outer_morph
            ),
        )


def create_app(database: str | Path) -> App:
    return bookmarks(database)


app = create_app(os.environ.get("HYPERCLASS_BOOKMARKS_DB", "bookmarks.db"))


if __name__ == "__main__":
    app.run()
