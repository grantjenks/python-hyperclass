"""Mount the bookmark components and routes as a native Django URL app."""

import os
from pathlib import Path

from django.urls import include, path

from hyperclass.django import App

from .bookmarks import BookmarkRoutes


class bookmarks(BookmarkRoutes, App):
    pass


def create_app(database: str | Path) -> App:
    return bookmarks(database, namespace="bookmarks")


app = create_app(os.environ.get("HYPERCLASS_BOOKMARKS_DB", "bookmarks.db"))
urlpatterns = [path("", include(app.urls))]
