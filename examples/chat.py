"""A persistent, streaming AI chat built with Hyperclass and no JavaScript."""

from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from hyperclass import (
    App,
    a,
    append,
    article,
    aside,
    button,
    css,
    div,
    fieldset,
    find,
    footer,
    form,
    fragment,
    get,
    h1,
    header,
    hx,
    id,
    label,
    main,
    media,
    name,
    outer_morph,
    p,
    partial,
    post,
    rem,
    section,
    small,
    span,
    stream,
    textarea,
)


@dataclass(frozen=True)
class Conversation:
    id: int
    title: str
    created_at: str


@dataclass(frozen=True)
class Message:
    id: int
    conversation_id: int
    role: str
    content: str
    status: str
    generation: int


@dataclass(frozen=True)
class Prompt:
    message: str


class ChatStore:
    """A deliberately small SQLite store suitable for the reference app."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    generation INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(messages)")
            }
            if "generation" not in columns:
                connection.execute(
                    "ALTER TABLE messages ADD COLUMN generation INTEGER NOT NULL DEFAULT 0"
                )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def create_conversation(self, title: str = "New conversation") -> Conversation:
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO conversations(title, created_at) VALUES (?, ?)",
                (title, created_at),
            )
        return self.conversation(int(cursor.lastrowid))

    def conversation(self, conversation_id: int) -> Conversation:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        if row is None:
            raise LookupError(conversation_id)
        return Conversation(row["id"], row["title"], row["created_at"])

    def conversations(self) -> list[Conversation]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM conversations ORDER BY id DESC"
            ).fetchall()
        return [Conversation(row["id"], row["title"], row["created_at"]) for row in rows]

    def latest_or_create(self) -> Conversation:
        conversations = self.conversations()
        return conversations[0] if conversations else self.create_conversation()

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        status: str = "complete",
        generation: int = 0,
    ) -> Message:
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO messages(
                       conversation_id, role, content, status, generation
                   ) VALUES (?, ?, ?, ?, ?)""",
                (conversation_id, role, content, status, generation),
            )
            if role == "user":
                connection.execute(
                    """UPDATE conversations SET title = ?
                       WHERE id = ? AND title = 'New conversation'""",
                    (content[:44], conversation_id),
                )
        return self.message(int(cursor.lastrowid))

    def message(self, message_id: int) -> Message:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM messages WHERE id = ?", (message_id,)
            ).fetchone()
        if row is None:
            raise LookupError(message_id)
        return Message(
            row["id"],
            row["conversation_id"],
            row["role"],
            row["content"],
            row["status"],
            row["generation"],
        )

    def messages(self, conversation_id: int) -> list[Message]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return [
            Message(
                row["id"],
                row["conversation_id"],
                row["role"],
                row["content"],
                row["status"],
                row["generation"],
            )
            for row in rows
        ]

    def update_message(self, message_id: int, content: str, status: str) -> Message:
        with self.connect() as connection:
            connection.execute(
                "UPDATE messages SET content = ?, status = ? WHERE id = ?",
                (content, status, message_id),
            )
        return self.message(message_id)

    def update_generation(
        self,
        message_id: int,
        generation: int,
        content: str,
        status: str,
    ) -> Message | None:
        """Update only while this iterator still owns the generation."""

        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE messages SET content = ?, status = ?
                   WHERE id = ? AND generation = ? AND status = 'streaming'""",
                (content, status, message_id, generation),
            )
        return self.message(message_id) if cursor.rowcount else None

    def restart(self, message_id: int) -> Message:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE messages
                   SET content = '', status = 'streaming', generation = generation + 1
                   WHERE id = ? AND role = 'assistant'""",
                (message_id,),
            )
        if cursor.rowcount == 0:
            raise LookupError(message_id)
        return self.message(message_id)

    def stop(self, message_id: int) -> Message:
        message = self.message(message_id)
        if message.status == "streaming":
            return self.update_message(message_id, message.content, "stopped")
        return message

    def preceding_prompt(self, message_id: int) -> str:
        message = self.message(message_id)
        with self.connect() as connection:
            row = connection.execute(
                """SELECT content FROM messages
                   WHERE conversation_id = ? AND role = 'user' AND id < ?
                   ORDER BY id DESC LIMIT 1""",
                (message.conversation_id, message_id),
            ).fetchone()
        if row is None:
            raise LookupError(message_id)
        return str(row["content"])


def demo_model(prompt: str) -> Iterable[str]:
    """A deterministic local model substitute; inject a real provider in production."""

    response = (
        f"You asked: {prompt}\n\n"
        "This answer is streaming from a plain Python iterator. The browser receives "
        "HTML fragments over one normal POST response, while SQLite keeps the transcript.\n\n"
        "A real model adapter has the same tiny contract:\n\n"
        "def model(prompt):\n"
        "    yield from provider.stream(prompt)\n\n"
        "That keeps model choice, authentication, tools, and retrieval in application code."
    )
    words = response.split(" ")
    for index, word in enumerate(words):
        yield word if index == len(words) - 1 else word + " "


class chat_shell(main):
    style = css(
        display="grid",
        grid_template_columns="17rem minmax(0, 1fr)",
        min_height="100dvh",
        background="#f8fafc",
        color="#172033",
        font_family="ui-sans-serif, system-ui, sans-serif",
    )
    narrow = media(max_width=48 * rem, grid_template_columns="1fr")


class chat_sidebar(aside):
    style = css(
        display="flex",
        flex_direction="column",
        gap=1 * rem,
        padding=1 * rem,
        background="#111827",
        color="#f8fafc",
        min_width=0,
    )
    narrow = media(max_width=48 * rem, padding=".75rem", min_height="auto")


class brand(h1):
    style = css(margin=0, font_size=1.05 * rem, letter_spacing="-.02em")


class new_chat(a):
    style = css(
        display="block",
        padding=".7rem .8rem",
        border="1px solid #4b5563",
        border_radius=.7 * rem,
        color="white",
        text_decoration="none",
        text_align="center",
        font_weight=700,
    )
    hover = css(background="#1f2937")


class conversation_list(div):
    style = css(display="grid", gap=.35 * rem, overflow="auto")
    narrow = media(max_width=48 * rem, display="flex")


class conversation_link(a):
    style = css(
        display="block",
        padding=".65rem .7rem",
        border_radius=.55 * rem,
        color="#d1d5db",
        text_decoration="none",
        overflow="hidden",
        text_overflow="ellipsis",
        white_space="nowrap",
    )
    hover = css(background="#1f2937", color="white")


class current_conversation(conversation_link):
    style = css(background="#374151", color="white")


class chat_panel(section):
    style = css(
        display="grid",
        grid_template_rows="auto minmax(0, 1fr) auto",
        height="100dvh",
        min_width=0,
    )
    narrow = media(max_width=48 * rem, height="calc(100dvh - 9.5rem)")


class chat_header(header):
    style = css(
        padding="1rem 1.25rem",
        background="rgb(255 255 255 / .9)",
        border_bottom="1px solid #e5e7eb",
        backdrop_filter="blur(12px)",
    )


class chat_title(h1):
    style = css(margin=0, font_size=1.05 * rem)


class model_label(small):
    style = css(color="#64748b")


class transcript(section):
    style = css(
        overflow_y="auto",
        padding="1.5rem max(1rem, calc((100% - 48rem) / 2)) 8rem",
        scroll_behavior="smooth",
    )


class empty_chat(div):
    style = css(max_width=36 * rem, margin="16vh auto 0", text_align="center", color="#64748b")


class message(article):
    style = css(
        display="grid",
        grid_template_columns="2.25rem minmax(0, 1fr)",
        gap=.8 * rem,
        max_width=48 * rem,
        margin="0 auto 1.35rem",
    )

    def __init__(self, value: Message, **attributes):
        super().__init__(**attributes)
        self.value = value

    def content(self):
        value = self.value
        yield avatar("You" if value.role == "user" else "AI", aria_hidden="true")
        yield message_body(
            message_meta(
                span("You" if value.role == "user" else "Hyperclass Assistant"),
                status_badge(value.status, id=id.message_status[value.id]),
            ),
            message_copy(
                value.content or "Thinking…", id=id.message_copy[value.id]
            ),
            message_actions(*message_controls(value)) if value.role == "assistant" else None,
        )


class user_message(message):
    pass


class assistant_message(message):
    pass


class avatar(div):
    style = css(
        display="grid",
        place_items="center",
        width=2.25 * rem,
        height=2.25 * rem,
        border_radius=.65 * rem,
        background="#e0e7ff",
        color="#4338ca",
        font_size=.7 * rem,
        font_weight=800,
    )


class message_body(div):
    style = css(min_width=0)


class message_meta(div):
    style = css(display="flex", align_items="center", gap=.55 * rem, font_size=.82 * rem, font_weight=750)


class status_badge(small):
    style = css(padding=".15rem .4rem", border_radius=99 * rem, background="#eef2ff", color="#4f46e5")


class message_copy(p):
    style = css(margin=".35rem 0 0", line_height=1.65, white_space="pre-wrap", overflow_wrap="anywhere")


class message_actions(div):
    style = css(display="flex", gap=.45 * rem, margin_top=.65 * rem)


class subtle_button(button):
    type = "button"
    style = css(
        padding=".35rem .55rem",
        border="1px solid #d1d5db",
        border_radius=.45 * rem,
        background="white",
        color="#475569",
        font="inherit",
        font_size=.78 * rem,
        cursor="pointer",
    )
    hover = css(background="#f1f5f9")


class action_label(span):
    pass


class composer_footer(footer):
    style = css(
        padding="1rem max(1rem, calc((100% - 48rem) / 2))",
        background="linear-gradient(transparent, #f8fafc 25%)",
    )


class composer(form):
    style = css(
        display="grid",
        grid_template_columns="minmax(0, 1fr) auto",
        gap=.65 * rem,
        padding=.65 * rem,
        border="1px solid #cbd5e1",
        border_radius=1 * rem,
        background="white",
        box_shadow="0 12px 35px rgb(15 23 42 / .12)",
    )


class composer_fields(fieldset):
    style = css(display="contents", border=0, padding=0, margin=0, min_width=0)


class prompt_field(textarea):
    name = name.message
    required = True
    rows = 1
    placeholder = "Message Hyperclass…"
    aria_label = "Message"
    style = css(
        resize="none",
        min_height=2.75 * rem,
        max_height=10 * rem,
        padding=".7rem .75rem",
        border=0,
        outline=0,
        color="inherit",
        font="inherit",
        line_height=1.4,
    )


class send_button(button):
    type = "submit"
    style = css(
        align_self="end",
        width=2.75 * rem,
        height=2.75 * rem,
        border=0,
        border_radius=.75 * rem,
        background="#4f46e5",
        color="white",
        font_size=1.15 * rem,
        cursor="pointer",
    )
    hover = css(background="#4338ca")
    disabled = css(opacity=.55, cursor="wait")


class helper_text(small):
    style = css(display="block", margin_top=.55 * rem, text_align="center", color="#64748b")


class stream_sink(div):
    hidden = True


def message_controls(value: Message):
    return (
        subtle_button(
            action_label(
                "Stop generating" if value.status == "streaming" else "Regenerate response",
                id=id.message_action[value.id],
            ),
            hx=(
                hx.post(
                    ChatRoutes.generation,
                    message_id=value.id,
                    target=id.stream_sink,
                    swap="none",
                    stream=True,
                )
                | hx.config("sse.releaseOn:first")
            ),
        ),
    )


def message_update(value: Message):
    """Update a message without replacing the button that owns its stream."""

    return fragment(
        partial(
            message_copy(
                value.content or "Thinking…", id=id.message_copy[value.id]
            ),
            hx_target=id.message_copy[value.id].selector,
            hx_swap=outer_morph,
        ),
        partial(
            status_badge(value.status, id=id.message_status[value.id]),
            hx_target=id.message_status[value.id].selector,
            hx_swap=outer_morph,
        ),
        partial(
            action_label(
                "Stop generating" if value.status == "streaming" else "Regenerate response",
                id=id.message_action[value.id],
            ),
            hx_target=id.message_action[value.id].selector,
            hx_swap=outer_morph,
        ),
    )


def message_view(value: Message):
    kind = user_message if value.role == "user" else assistant_message
    return kind(value, id=id.message[value.id])


def conversation_nav(store: ChatStore, selected: Conversation):
    return chat_sidebar(
        brand("Hyperclass Chat"),
        new_chat("＋ New chat", href=ChatRoutes.new),
        conversation_list(
            *(
                (current_conversation if item.id == selected.id else conversation_link)(
                    item.title,
                    href=ChatRoutes.show.url(chat_id=item.id),
                )
                for item in store.conversations()
            )
        ),
    )


def composer_view(conversation_id: int):
    attributes = (
        hx.post(
            ChatRoutes.send,
            chat_id=conversation_id,
            target=id.stream_sink,
            swap="none",
            disable=find(composer_fields),
            stream=True,
        )
        | hx.on.before_request("this.reset()")
    )
    return composer_footer(
        composer(
            composer_fields(
                label("Message", for_=str(name.message), hidden=True),
                prompt_field(id=str(name.message), autofocus=True),
                send_button("↑", aria_label="Send message"),
            ),
            method="post",
            action=ChatRoutes.send.url(chat_id=conversation_id),
            hx=attributes,
        ),
        helper_text("Demo responses are generated locally · no API key required"),
    )


def app_view(store: ChatStore, conversation: Conversation):
    messages = store.messages(conversation.id)
    return chat_shell(
        conversation_nav(store, conversation),
        chat_panel(
            chat_header(chat_title(conversation.title), model_label("Local demo model · SSE")),
            transcript(
                *(
                    [message_view(value) for value in messages]
                    if messages
                    else [
                        empty_chat(
                            h1("What can we build?"),
                            p("This chat persists, streams, stops, and regenerates with Python objects all the way down."),
                        )
                    ]
                ),
                id=id.messages,
                aria_live="polite",
            ),
            composer_view(conversation.id),
            stream_sink(id=id.stream_sink),
        ),
    )


class ChatRoutes:
    def __init__(
        self,
        database: str | Path,
        *,
        model: Callable[[str], Iterable[str]] | None = None,
        token_delay: float = 0.025,
        **host_options,
    ):
        self.store = ChatStore(database)
        self.model = model or demo_model
        self.token_delay = token_delay
        super().__init__(title="Hyperclass Chat", **host_options)

    @get("/")
    def index(self, request):
        conversation = self.store.latest_or_create()
        return app_view(self.store, conversation)

    @get("/new")
    def new(self, request):
        return app_view(self.store, self.store.create_conversation())

    @get("/chats/<int:chat_id>")
    def show(self, request, chat_id):
        try:
            return app_view(self.store, self.store.conversation(chat_id))
        except LookupError:
            return "Conversation not found", 404

    @post("/chats/<int:chat_id>/messages")
    def send(self, request, chat_id, form: Prompt):
        prompt = form.message.strip()
        if not prompt:
            return "A message is required", 422
        try:
            self.store.conversation(chat_id)
        except LookupError:
            return "Conversation not found", 404
        user = self.store.add_message(chat_id, "user", prompt)
        assistant = self.store.add_message(
            chat_id, "assistant", "", "streaming", generation=1
        )
        return stream(self._events(prompt, assistant, initial=(user, assistant)))

    @post("/messages/<int:message_id>/stop")
    def stop(self, request, message_id):
        try:
            return message_view(self.store.stop(message_id))
        except LookupError:
            return "Message not found", 404

    @post("/messages/<int:message_id>/regenerate")
    def regenerate(self, request, message_id):
        try:
            prompt = self.store.preceding_prompt(message_id)
            message = self.store.restart(message_id)
        except LookupError:
            return "Message not found", 404
        return stream(self._events(prompt, message, in_place=True))

    @post("/messages/<int:message_id>/generation")
    def generation(self, request, message_id):
        try:
            message = self.store.message(message_id)
            if message.status == "streaming":
                stopped = self.store.stop(message_id)
                return partial(
                    message_view(stopped),
                    hx_target=id.message[message_id].selector,
                    hx_swap=outer_morph,
                )
            prompt = self.store.preceding_prompt(message_id)
            restarted = self.store.restart(message_id)
        except LookupError:
            return "Message not found", 404
        return stream(self._events(prompt, restarted, in_place=True))

    def _events(
        self,
        prompt: str,
        assistant: Message,
        *,
        initial: tuple[Message, Message] | None = None,
        in_place: bool = False,
    ) -> Iterator:
        if initial:
            yield partial(
                *(message_view(value) for value in initial),
                hx_target=id.messages.selector,
                hx_swap=append,
            )
        content = ""
        generation = assistant.generation
        try:
            for chunk in self.model(prompt):
                current = self.store.message(assistant.id)
                if (
                    current.status != "streaming"
                    or current.generation != generation
                ):
                    return
                content += str(chunk)
                current = self.store.update_generation(
                    assistant.id, generation, content, "streaming"
                )
                if current is None:
                    return
                yield message_update(current) if in_place else partial(
                    message_view(current),
                    hx_target=id.message[assistant.id].selector,
                    hx_swap=outer_morph,
                )
                if self.token_delay:
                    time.sleep(self.token_delay)
            current = self.store.update_generation(
                assistant.id, generation, content, "complete"
            )
            if current is None:
                return
            yield message_update(current) if in_place else partial(
                message_view(current),
                hx_target=id.message[assistant.id].selector,
                hx_swap=outer_morph,
            )
        except GeneratorExit:
            self.store.stop(assistant.id)
            raise
        except Exception as error:
            current = self.store.update_generation(
                assistant.id,
                generation,
                f"{content}\n\nGeneration failed: {error}",
                "error",
            )
            if current is None:
                return
            yield message_update(current) if in_place else partial(
                message_view(current),
                hx_target=id.message[assistant.id].selector,
                hx_swap=outer_morph,
            )


class chat(ChatRoutes, App):
    pass


def create_app(
    database: str | Path,
    *,
    model: Callable[[str], Iterable[str]] | None = None,
    token_delay: float = 0.025,
) -> App:
    return chat(database, model=model, token_delay=token_delay)


app = create_app(os.environ.get("HYPERCLASS_CHAT_DB", "chat.db"))


if __name__ == "__main__":
    app.run()
