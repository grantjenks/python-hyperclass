"""Run the streaming chat on native Flask."""

import os

from hyperclass.flask import App

from .chat import ChatRoutes


class chat(ChatRoutes, App):
    pass


app = chat(os.environ.get("HYPERCLASS_CHAT_DB", "chat.db"))


if __name__ == "__main__":
    app.run()
