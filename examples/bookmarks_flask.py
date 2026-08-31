"""Run the bookmark components and routes on native Flask."""

import os
from pathlib import Path

from hyperclass.flask import App

from .bookmarks import BookmarkRoutes


class bookmarks(BookmarkRoutes, App):
    pass


def create_app(database: str | Path) -> App:
    return bookmarks(database)


app = create_app(os.environ.get("HYPERCLASS_BOOKMARKS_DB", "bookmarks.db"))


if __name__ == "__main__":
    app.run()
