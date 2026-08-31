"""Mount the streaming chat as a native Django URL application."""

import os

from django.urls import include, path

from hyperclass.django import App

from .chat import ChatRoutes


class chat(ChatRoutes, App):
    pass


app = chat(os.environ.get("HYPERCLASS_CHAT_DB", "chat.db"), namespace="chat")
urlpatterns = [path("", include(app.urls))]
