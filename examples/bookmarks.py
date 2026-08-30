"""A small, persistent bookmark inbox built entirely with Hyperclass."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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
    delete_route,
    div,
    footer,
    form,
    get,
    h1,
    h2,
    header,
    hx,
    id,
    input,
    label,
    main,
    media,
    name,
    outer_morph,
    p,
    patch,
    post,
    put,
    rem,
    section,
    small,
    span,
)


@dataclass(frozen=True)
class Bookmark:
    id: int
    url: str
    title: str
    is_read: bool
    created_at: str


@dataclass(frozen=True)
class NewBookmark:
    url: str
    title: str = ""


@dataclass(frozen=True)
class EditedBookmark:
    url: str
    title: str = ""


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

    @staticmethod
    def _clean(url: str, title: str = "") -> tuple[str, str]:
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Enter a full http:// or https:// URL.")
        url = parsed.geturl()
        title = title.strip() or parsed.hostname or url
        return url, title

    def add(self, url: str, title: str = "") -> Bookmark:
        url, title = self._clean(url, title)
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO bookmarks(url, title, created_at) VALUES (?, ?, ?)",
                (url, title, created_at),
            )
            bookmark_id = cursor.lastrowid
        return self.get(int(bookmark_id))

    def update(self, bookmark_id: int, url: str, title: str = "") -> Bookmark:
        url, title = self._clean(url, title)
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE bookmarks SET url = ?, title = ? WHERE id = ?",
                (url, title, bookmark_id),
            )
        if cursor.rowcount == 0:
            raise LookupError(bookmark_id)
        return self.get(bookmark_id)

    def get(self, bookmark_id: int) -> Bookmark:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)
            ).fetchone()
        if row is None:
            raise LookupError(bookmark_id)
        return self._bookmark(row)

    def list(self, state: str = "all", query: str = "") -> list[Bookmark]:
        clauses: list[str] = []
        parameters: list[str] = []
        if state == "unread":
            clauses.append("is_read = 0")
        elif state == "read":
            clauses.append("is_read = 1")
        if query := query.strip():
            clauses.append("(title LIKE ? OR url LIKE ?)")
            parameters.extend((f"%{query}%", f"%{query}%"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM bookmarks {where} ORDER BY id DESC", parameters
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


class url_field(text_field):
    type = "url"
    name = name.url
    required = True


class title_field(text_field):
    name = name.title


class primary_button(button):
    type = "submit"
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


class search_form(form):
    style = css(flex="1 1 14rem", max_width=22 * rem)


class search_field(text_field):
    type = "search"
    name = name.q
    placeholder = "Search bookmarks"
    aria_label = "Search bookmarks"


class filter_field(input):
    type = "hidden"
    name = name.filter


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


class bookmark_results(section):
    pass


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

    def __init__(self, bookmark: Bookmark, state: str = "all", query: str = ""):
        self.bookmark = bookmark
        self.state = state
        self.query = query

    def content(self):
        bookmark = self.bookmark
        context = {}
        if self.state != "all":
            context["filter"] = self.state
        if self.query:
            context["q"] = self.query
        yield bookmark_copy(
            bookmark_title(
                bookmark_link(
                    bookmark.title,
                    href=bookmark.url,
                )
            ),
            bookmark_url(bookmark.url),
        )
        yield card_actions(
            action_button(
                "Mark unread" if bookmark.is_read else "Mark read",
                hx=hx.patch(
                    bookmarks.toggle,
                    bookmark_id=bookmark.id,
                    query=context,
                    target=id.bookmark_results,
                    swap=outer_morph,
                ),
            ),
            action_button(
                "Edit",
                hx=hx.get(
                    bookmarks.edit,
                    bookmark_id=bookmark.id,
                    target=closest(bookmark_card),
                    swap=outer_morph,
                ),
            ),
            delete_button(
                "Delete",
                hx=hx.delete(
                    bookmarks.delete,
                    bookmark_id=bookmark.id,
                    query=context,
                    target=id.bookmark_results,
                    swap=outer_morph,
                    confirm="Delete this bookmark?",
                ),
            ),
        )


class bookmark_copy(div):
    style = css(min_width=0)


class bookmark_title(h2):
    style = css(margin="0 0 .25rem", font_size=1.05 * rem, line_height=1.3)


class bookmark_link(a):
    target = "_blank"
    rel = "noreferrer"
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
    type = "button"
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


class bookmark_editor(form):
    style = bookmark_card.style
    narrow = bookmark_card.narrow


class editor_fields(div):
    style = css(display="grid", gap=.6 * rem)


def bookmark_view(bookmark: Bookmark, state: str = "all", query: str = ""):
    kind = read_bookmark if bookmark.is_read else unread_bookmark
    return kind(bookmark, state, query)


def count_view(store: BookmarkStore):
    count = store.unread_count()
    noun = "bookmark" if count == 1 else "bookmarks"
    return unread_badge(f"{count} unread {noun}", id=id.unread_count)


def list_view(
    store: BookmarkStore, state: str = "all", query: str = ""
):
    bookmarks = store.list(state, query)
    children = (
        [bookmark_view(bookmark, state, query) for bookmark in bookmarks]
        if bookmarks
        else [
            empty_state(
                f'No bookmarks matching "{query}".'
                if query
                else (
                    f"No {state} bookmarks yet."
                    if state != "all"
                    else "No bookmarks yet."
                )
            )
        ]
    )
    return bookmark_list(*children, id=id.bookmark_list)


def results_view(store: BookmarkStore, state: str = "all", query: str = ""):
    query_values = {"filter": state}
    if query:
        query_values["q"] = query
    return bookmark_results(
        bookmark_toolbar(
            search_form(
                search_field(
                    value=query,
                    hx=hx.get(
                        bookmarks.listing,
                        include=name.filter,
                        target=id.bookmark_results,
                        swap=outer_morph,
                        trigger="input changed delay:250ms, search",
                    ),
                ),
                filter_field(value=state),
            ),
            filters(
                *(
                    filter_link(
                        state_name.title(),
                        href=bookmarks.listing.url(
                            query={**query_values, "filter": state_name}
                        ),
                        hx=hx.get(
                            bookmarks.listing,
                            query={**query_values, "filter": state_name},
                            target=id.bookmark_results,
                            swap=outer_morph,
                        ),
                    )
                    for state_name in ("all", "unread", "read")
                )
            ),
            count_view(store),
        ),
        list_view(store, state, query),
        id=id.bookmark_results,
    )


def edit_view(bookmark: Bookmark, error: str = ""):
    children = [
        editor_fields(
            field_label(
                "URL",
                url_field(value=bookmark.url),
            ),
            field_label(
                "Title",
                title_field(value=bookmark.title),
            ),
        ),
        card_actions(
            primary_button("Save"),
            action_button(
                "Cancel",
                hx=hx.get(
                    bookmarks.show,
                    bookmark_id=bookmark.id,
                    target=closest(bookmark_editor),
                    swap=outer_morph,
                ),
            ),
        ),
    ]
    if error:
        children.append(error_message(error, role="alert"))
    return bookmark_editor(
        *children,
        method="post",
        action=bookmarks.update.url(bookmark_id=bookmark.id),
        hx=hx.put(
            bookmarks.update,
            bookmark_id=bookmark.id,
            target=closest(bookmark_editor),
            swap=outer_morph,
        ),
    )


def form_view(error: str = ""):
    children = [
        field_label(
            "URL",
            url_field(
                placeholder="https://example.com/article",
            ),
        ),
        field_label(
            "Title (optional)",
            title_field(placeholder="An excellent read"),
        ),
        primary_button("Save"),
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
        results_view(store),
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
    def create(self, request, form: NewBookmark):
        try:
            self.store.add(form.url, form.title)
        except ValueError as error:
            return Response(app_view(self.store, str(error)), 422)
        return app_view(self.store)

    @get("/bookmarks")
    def listing(self, request):
        state = request.query.get(name.filter, "all")
        return results_view(
            self.store,
            state if state in {"all", "unread", "read"} else "all",
            request.query.get(name.q, ""),
        )

    @get("/bookmarks/<int:bookmark_id>")
    def show(self, request, bookmark_id):
        try:
            return bookmark_view(self.store.get(bookmark_id))
        except LookupError:
            return Response("Bookmark not found", 404)

    @get("/bookmarks/<int:bookmark_id>/edit")
    def edit(self, request, bookmark_id):
        try:
            return edit_view(self.store.get(bookmark_id))
        except LookupError:
            return Response("Bookmark not found", 404)

    @put("/bookmarks/<int:bookmark_id>")
    def update(self, request, bookmark_id, form: EditedBookmark):
        try:
            return bookmark_view(
                self.store.update(bookmark_id, form.url, form.title)
            )
        except ValueError as error:
            try:
                bookmark = self.store.get(bookmark_id)
            except LookupError:
                return Response("Bookmark not found", 404)
            return Response(edit_view(bookmark, str(error)), 422)
        except LookupError:
            return Response("Bookmark not found", 404)

    @patch("/bookmarks/<int:bookmark_id>")
    def toggle(self, request, bookmark_id):
        try:
            self.store.toggle(bookmark_id)
        except LookupError:
            return Response("Bookmark not found", 404)
        state = request.query.get(name.filter, "all")
        return results_view(
            self.store,
            state if state in {"all", "unread", "read"} else "all",
            request.query.get(name.q, ""),
        )

    @delete_route("/bookmarks/<int:bookmark_id>")
    def delete(self, request, bookmark_id):
        try:
            self.store.delete(bookmark_id)
        except LookupError:
            return Response("Bookmark not found", 404)
        state = request.query.get(name.filter, "all")
        return results_view(
            self.store,
            state if state in {"all", "unread", "read"} else "all",
            request.query.get(name.q, ""),
        )


def create_app(database: str | Path) -> App:
    return bookmarks(database)


app = create_app(os.environ.get("HYPERCLASS_BOOKMARKS_DB", "bookmarks.db"))


if __name__ == "__main__":
    app.run()
