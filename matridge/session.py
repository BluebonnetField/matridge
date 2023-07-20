import io
from typing import Any, Optional, Union

import aiohttp
import nio
from slidge import BaseSession, SearchResult
from slidge.util.types import LegacyMessageType, LegacyThreadType, RecipientType
from slixmpp.exceptions import XMPPError

from .contact import Contact, Roster
from .group import MUC, Bookmarks, Participant
from .matrix import Client

Sender = Union[Contact, Participant]
Recipient = Union[MUC, Contact]


def no_dm(func):
    async def wrapped_no_dm(self, chat: Recipient, *a, **kw):
        if isinstance(chat, Contact):
            # TODO: list rooms with this contact
            # TODO: create 1:1 room if no room
            raise XMPPError("bad-request", "Matridge does not implement 1:1 chats")
        return await func(self, chat, *a, **kw)

    return wrapped_no_dm


class Session(BaseSession[str, Recipient]):
    bookmarks: Bookmarks
    contacts: Roster
    matrix: Client

    MESSAGE_IDS_ARE_THREAD_IDS = True

    def __init__(self, *a):
        super().__init__(*a)
        self.events_to_ignore = set[str]()

    async def login(self):
        f = self.user.registration_form
        self.matrix = Client(f["homeserver"], f["username"], self)  # type:ignore
        await self.matrix.login_token()
        await self.matrix.listen()
        self.contacts.user_legacy_id = self.matrix.user_id
        return f"Logged in as {self.matrix.user}"

    async def logout(self):
        self.matrix.stop_listen()

    @staticmethod
    def __relates_to(
        content: dict[str, Any], reply_to_msg_id: Optional[str], thread: Optional[str]
    ):
        relates_to = dict[str, Any]()
        if reply_to_msg_id:
            relates_to["m.in_reply_to"] = {"event_id": reply_to_msg_id}
        if thread:
            relates_to["rel_type"] = "m.thread"
            relates_to["event_id"] = thread
        if relates_to:
            content["m.relates_to"] = relates_to

    async def __handle_response(self, response: nio.Response):
        self.log.debug("Send response: %s", response)
        if isinstance(response, nio.RoomSendError):
            raise XMPPError("internal-server-error", str(response))
        assert isinstance(response, nio.RoomSendResponse)
        i = response.event_id
        self.events_to_ignore.add(i)
        return i

    async def __room_send(
        self, chat: MUC, content: dict, message_type="m.room.message"
    ):
        await self.matrix.room_typing(chat.legacy_id, False)
        response = await self.matrix.room_send(
            chat.legacy_id,
            message_type=message_type,
            content=content,
        )
        return await self.__handle_response(response)

    @no_dm
    async def send_text(
        self,
        chat: MUC,
        text: str,
        *,
        reply_to_msg_id: Optional[str] = None,
        reply_to_fallback_text: Optional[str] = None,
        reply_to: Optional[Sender] = None,
        thread: Optional[str] = None,
    ) -> Optional[LegacyMessageType]:
        content = {"msgtype": "m.text", "body": text}
        self.__relates_to(content, reply_to_msg_id, thread)
        return await self.__room_send(chat, content)

    @no_dm
    async def send_file(
        self,
        chat: MUC,
        url: str,
        *,
        http_response: aiohttp.ClientResponse,
        reply_to_msg_id: Optional[str] = None,
        reply_to_fallback_text: Optional[str] = None,
        reply_to: Optional[Sender] = None,
        thread: Optional[str] = None,
    ) -> Optional[LegacyMessageType]:
        filename = url.split("/")[-1]
        content_type = http_response.content_type
        resp, _ = await self.matrix.upload(
            io.BytesIO(await http_response.read()), content_type, filename
        )
        self.log.debug("Upload response: %s %r", type(resp), resp)
        if not isinstance(resp, nio.UploadResponse):
            raise XMPPError("internal-server-error", str(resp))
        content = {
            "msgtype": "m.image" if content_type.startswith("image") else "m.file",
            "body": filename,
            "url": resp.content_uri,
        }
        self.__relates_to(content, reply_to_msg_id, thread)
        return await self.__room_send(chat, content)

    async def active(self, c: RecipientType, thread: Optional[LegacyThreadType] = None):
        pass

    async def inactive(
        self, c: RecipientType, thread: Optional[LegacyThreadType] = None
    ):
        pass

    @no_dm
    async def composing(self, c: MUC, thread: Optional[LegacyThreadType] = None):
        await self.matrix.room_typing(c.legacy_id)

    @no_dm
    async def paused(self, c: MUC, thread: Optional[LegacyThreadType] = None):
        await self.matrix.room_typing(c.legacy_id, False)

    @no_dm
    async def displayed(
        self,
        c: RecipientType,
        legacy_msg_id: LegacyMessageType,
        thread: Optional[LegacyThreadType] = None,
    ):
        resp = await self.matrix.update_receipt_marker(c.legacy_id, legacy_msg_id)
        self.log.debug("Displayed response: %s", resp)

    @no_dm
    async def correct(
        self,
        c: MUC,
        text: str,
        legacy_msg_id: str,
        thread: Optional[str] = None,
    ) -> Optional[str]:
        content = {
            "msgtype": "m.text",
            "body": "* " + text,
            "m.new_content": {"body": text, "msgtype": "m.text"},
            "m.relates_to": {"rel_type": "m.replace", "event_id": legacy_msg_id},
        }
        self.__relates_to(content, None, thread)
        return await self.__room_send(c, content)

    @no_dm
    async def search(self, form_values: dict[str, str]) -> Optional[SearchResult]:
        pass

    @no_dm
    async def react(
        self,
        c: MUC,
        legacy_msg_id: str,
        emojis: list[str],
        thread: Optional[LegacyThreadType] = None,
    ):
        new_emojis = set(emojis)
        old_emojis = await self.matrix.reactions.get(
            c.legacy_id, legacy_msg_id, self.matrix.user_id, with_event_ids=True
        )
        for old_emoji, event in old_emojis.items():
            if old_emoji in new_emojis:
                new_emojis.remove(old_emoji)
            else:
                await self.retract(c, event)
                self.matrix.reactions.remove(event)
        for emoji in new_emojis:
            content = {
                "m.relates_to": {
                    "rel_type": "m.annotation",
                    "event_id": legacy_msg_id,
                    "key": emoji,
                },
            }

            i = await self.__room_send(c, content, "m.reaction")
            await self.matrix.reactions.add(
                c.legacy_id, legacy_msg_id, self.matrix.user_id, emoji, i
            )

    @no_dm
    async def retract(
        self,
        c: RecipientType,
        legacy_msg_id: str,
        thread: Optional[str] = None,
    ):
        # TODO
        resp = await self.matrix.room_redact(c.legacy_id, legacy_msg_id)
        self.log.debug("Redact response: %s", resp)
        if isinstance(resp, nio.RoomRedactError):
            raise XMPPError("internal-server-error", str(resp))
        assert isinstance(resp, nio.RoomRedactResponse)
        self.events_to_ignore.add(resp.event_id)
