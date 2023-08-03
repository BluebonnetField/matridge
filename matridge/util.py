import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from urllib.parse import quote

import bs4
import nio
from slidge.core.mixins import MessageMixin
from slidge.util.types import LegacyAttachment, MessageReference
from slidge_style_parser import format_body

from . import config

if TYPE_CHECKING:
    from .group import MUC
    from .session import Session


class MatrixMixin(MessageMixin):
    session: "Session"
    muc: "MUC"
    log: logging.Logger

    async def __get_reply_to(self, msg: nio.RoomMessage) -> Optional[MessageReference]:
        reply_to_msg_id = get_reply_to(msg.source)
        if not reply_to_msg_id:
            return None

        reply_to = MessageReference(legacy_id=reply_to_msg_id)
        if event := await self.muc.get_message(reply_to_msg_id):
            self.log.debug("Get Message Event: %r", event)
            author = await self.muc.get_participant_by_legacy_id(event.sender)
            self.log.debug("Author: %r", author)
            reply_to.author = author
            if isinstance(event, nio.RoomMessage):
                reply_to.body = get_body(event)
        return reply_to

    async def __add_reply_to(self, msg: nio.RoomMessage, replace: str, kwargs: dict):
        if replace is None:
            kwargs["reply_to"] = await self.__get_reply_to(msg)
            return

        kwargs["correction"] = True
        original = await self.muc.get_message(replace)
        if not isinstance(original, nio.RoomMessage):
            self.log.warning(
                "Reply to something else than a message, or couldn't fetch it: %s",
                original,
            )
            return
        kwargs["reply_to"] = await self.__get_reply_to(original)

    async def __get_attachments(self, msg: nio.RoomMessage, **kwargs):
        if not isinstance(msg, nio.RoomMessageMedia):
            return []

        return [
            LegacyAttachment(
                url=await self.session.matrix.mxc_to_http(msg.url),
                legacy_file_id=quote(msg.url),
                name=get_body(msg) or None,
            )
        ]

    async def send_matrix_message(
        self,
        msg: nio.RoomMessage,
        replace=None,
        replacement_event_id=None,
        archive_only=False,
    ):
        self.log.debug("Message: %s", msg.source)

        if id_and_new := get_new_message(msg):
            replace, new = id_and_new
            return await self.send_matrix_message(
                new, replace, msg.event_id, archive_only
            )

        kwargs = dict(
            archive_only=archive_only,
            when=server_timestamp_to_datetime(msg),
            correction_event_id=replacement_event_id,
        )
        await self.__add_reply_to(msg, replace, kwargs)
        attachments = await self.__get_attachments(msg, **kwargs)

        await self.send_files(
            attachments,
            msg.event_id,
            body=None if attachments else get_body(msg),
            thread=get_rel(msg.source, "m.thread") or msg.event_id,
            **kwargs,
        )


def strip_reply_fallback(formatted_body: str) -> str:
    obj = bs4.BeautifulSoup(formatted_body, "html.parser")
    if mx_reply := obj.find("mx-reply"):
        if isinstance(mx_reply, bs4.Tag):
            mx_reply.decompose()
    return str(obj.text)


def get_reply_to(source: dict) -> Optional[str]:
    return (
        source.get("content", {})
        .get("m.relates_to", {})
        .get("m.in_reply_to", {})
        .get("event_id")
    )


def get_replace(source: dict):
    return get_rel(source, "m.replace")


def get_rel(source: dict, rel_type: str) -> Optional[str]:
    content = source.get("content")
    if not content:
        return None
    relates_to = content.get("m.relates_to")
    if not relates_to:
        return None
    if relates_to.get("rel_type") != rel_type:
        return None
    return relates_to.get("event_id")


def get_new_content(source: dict) -> Optional[nio.RoomMessage]:
    content = source.get("content")
    if not content:
        return None
    new_content = content.get("m.new_content")
    return new_content


def get_new_message(msg: nio.RoomMessage):
    replace = get_rel(msg.source, "m.replace")
    if not replace:
        return
    return replace, nio.RoomMessage.parse_event(
        {
            "content": get_new_content(msg.source),
            "origin_server_ts": msg.server_timestamp,
            "sender": msg.sender,
            "event_id": replace,
        }
    )


def get_body(msg: nio.RoomMessage):
    if (
        isinstance(msg, nio.RoomMessageFormatted)
        and msg.format == "org.matrix.custom.html"
    ):
        relates_to = msg.source.get("content", {}).get("m.relates_to", {})
        if relates_to.get("rel_type") == "m.replace" or relates_to.get("m.in_reply_to"):
            body = strip_reply_fallback(msg.formatted_body)
        else:
            body = msg.body
    else:
        body = getattr(msg, "body", "")

    if isinstance(msg, nio.RoomMessageEmote):
        body = "/me " + body

    return body


def server_timestamp_to_datetime(event: nio.Event):
    return datetime.fromtimestamp(event.server_timestamp / 1000, tz=timezone.utc)


def get_content(text: str):
    content = {"msgtype": "m.text", "body": text}
    if config.PARSE_MESSAGE_STYLING:
        formatted_body = format_body(text, MATRIX_FORMATS)
        content["formatted_body"] = formatted_body
        content["format"] = "org.matrix.custom.html"
    return content


MATRIX_FORMATS = {
    "_": ("<em>", "</em>"),
    "*": ("<strong>", "</strong>"),
    "~": ("<del>", "</del>"),
    "`": ("<code>", "</code>"),
    "```": ("<pre><code>", "</code></pre>"),
    "```language": ('<pre><code class="language-{}">', "</code></pre>"),
    ">": ("<blockquote>", "</blockquote>"),
    "||": ("<span data-mx-spoiler>", "</span>"),
}


log = logging.getLogger()
