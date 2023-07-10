import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import bs4
import nio
from slidge.core.mixins import MessageMixin
from slidge.util.types import LegacyAttachment, MessageReference

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
            if hasattr(event, "body"):
                reply_to.body = get_body(event.body)
        return reply_to

    async def send_matrix_message(
        self,
        msg: nio.RoomMessage,
        correction=False,
        archive_only=False,
    ):
        self.log.debug("Message: %s", msg.source)

        if new := get_new_message(msg):
            return await self.send_matrix_message(new, True, archive_only)

        kwargs = dict(
            archive_only=archive_only,
            reply_to=await self.__get_reply_to(msg),
            correction=correction,
            when=server_timestamp_to_datetime(msg),
        )

        if isinstance(msg, nio.RoomMessageMedia):
            resp = await self.session.matrix.try_download(msg.url)
            if not resp:
                self.send_text(
                    "/me tried to send a file matridge couldn't download. :(",
                    msg.event_id,
                    **kwargs,
                )
                return
            attachments = [
                LegacyAttachment(data=resp.body, legacy_file_id=resp.uuid or msg.url)
            ]
        else:
            attachments = []

        await self.send_files(attachments, msg.event_id, get_body(msg), **kwargs)


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


def get_replace(source: dict) -> Optional[str]:
    content = source.get("content")
    if not content:
        return None
    relates_to = content.get("m.relates_to")
    if not relates_to:
        return None
    rel_type = relates_to.get("rel_type")
    if rel_type != "m.replace":
        return None
    return relates_to.get("event_id")


def get_new_content(source: dict) -> Optional[nio.RoomMessage]:
    content = source.get("content")
    if not content:
        return None
    new_content = content.get("m.new_content")
    return new_content


def get_new_message(msg: nio.RoomMessage):
    replace = get_replace(msg.source)
    if not replace:
        return
    return nio.RoomMessage.parse_event(
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


log = logging.getLogger()
