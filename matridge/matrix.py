import json
import logging
import shutil
from asyncio import Task, create_task
from functools import wraps
from typing import TYPE_CHECKING, Awaitable, Callable, Optional, TypedDict, Union

import nio
from async_lru import alru_cache
from slidge.core import config
from slidge.util.types import LegacyAttachment
from slixmpp import JID
from slixmpp.exceptions import XMPPError

from .reactions import ReactionCache
from .util import get_replace, server_timestamp_to_datetime

if TYPE_CHECKING:
    from .group import MUC, Participant
    from .session import Session


def catch_all(coro: Callable[["Client", nio.MatrixRoom, nio.Event], Awaitable[None]]):
    @wraps(coro)
    async def wrapped(self: "Client", room: nio.MatrixRoom, event: nio.Event, *a, **kw):
        event_id = getattr(event, "event_id", None)
        if event_id in self.session.events_to_ignore:
            self.log.debug("Ignoring an event matridge has sent: %s", event_id)
            return
        try:
            return await coro(self, room, event, *a, **kw)
        except XMPPError as e:
            self.log.debug(
                "Exception raised in matrix client callback %s", coro, exc_info=e
            )
        except Exception as e:
            self.log.exception(
                "Exception raised in matrix client callback %s", coro, exc_info=e
            )

    return wrapped


class Credentials(TypedDict):
    homeserver: str
    user_id: str
    device_id: str
    access_token: str


class AuthenticationClient(nio.AsyncClient):
    def __init__(
        self, server: str, handle: str, jid: JID, log: Optional[logging.Logger] = None
    ):
        if not server.startswith("http"):
            server = "https://" + server
        self._storage = config.HOME_DIR / jid.bare
        self.store_path = store_path = config.HOME_DIR / (jid.bare + "_state")
        store_path.mkdir(exist_ok=True)
        cfg = nio.AsyncClientConfig(
            store_sync_tokens=True,
            max_limit_exceeded=0,
            max_timeouts=0,
            encryption_enabled=True,
        )
        super().__init__(server, handle, store_path=str(store_path), config=cfg)
        if log:
            self.log = log
        else:
            self.log = logging.getLogger(__name__)

    def save(self, resp: nio.LoginResponse):
        creds: Credentials = {
            "homeserver": self.homeserver,
            "user_id": resp.user_id,
            "device_id": resp.device_id,
            "access_token": resp.access_token,
        }

        with open(self._storage, "w") as f:
            json.dump(creds, f)

    def load(self):
        with open(self._storage, "r") as f:
            stored: Credentials = json.load(f)

        self.access_token = stored["access_token"]
        self.user_id = stored["user_id"]
        self.device_id = stored["device_id"]

    def destroy(self):
        try:
            self._storage.unlink()
            shutil.rmtree(self.store_path)
        except FileNotFoundError:
            self.log.error("Could not delete persistent data from disk", exc_info=True)

    async def login_token(self):
        self.load()
        await self.fix_homeserver()
        self.load_store()
        self.log.debug("Token %s", self.access_token)

    async def fix_homeserver(self):
        """
        Uses https://$HOMESERVER/.well-known/matrix/client to fix the homeserver
        URL.
        """
        response = await self.discovery_info()
        if isinstance(response, nio.DiscoveryInfoResponse):
            self.homeserver = response.homeserver_url


class Client(AuthenticationClient):
    def __init__(self, server: str, handle: str, session: "Session"):
        super().__init__(server, handle, session.user.jid, session.log)
        self.__sync_task: Optional[Task] = None
        self.session = session
        self.reactions = ReactionCache(self)

    def __add_event_handlers(self):
        self.add_event_callback(self.on_event, nio.Event)  # type:ignore
        self.add_event_callback(self.on_message, nio.RoomMessage)  # type:ignore
        self.add_event_callback(self.on_avatar, nio.RoomAvatarEvent)  # type:ignore
        self.add_event_callback(self.on_topic, nio.RoomTopicEvent)  # type:ignore
        self.add_event_callback(self.on_name, nio.RoomNameEvent)  # type:ignore
        self.add_event_callback(self.on_sticker, nio.StickerEvent)  # type:ignore
        self.add_event_callback(self.on_member, nio.RoomMemberEvent)  # type:ignore
        self.add_event_callback(self.on_redact, nio.RedactionEvent)  # type:ignore
        self.add_presence_callback(self.on_presence, nio.PresenceEvent)  # type:ignore
        self.add_ephemeral_callback(self.on_receipt, nio.ReceiptEvent)  # type:ignore
        self.add_ephemeral_callback(
            self.on_typing, nio.TypingNoticeEvent  # type:ignore
        )

    async def __get_muc(self, room: Union[nio.MatrixRoom, str]) -> "MUC":
        room_id = room.room_id if isinstance(room, nio.MatrixRoom) else room
        return await self.session.bookmarks.by_legacy_id(room_id)

    def __launch_sync(self):
        self.__sync_task = create_task(self.sync_forever())
        self.__sync_task.add_done_callback(self.__relaunch_sync)

    def __relaunch_sync(self, sync_task: Task):
        self.log.warning(
            "Sync task is done, restarting", exc_info=sync_task.exception()
        )
        self.__launch_sync()

    async def get_participant(
        self, room: nio.MatrixRoom, event: nio.Event
    ) -> "Participant":
        muc = await self.__get_muc(room)
        self.log.debug(
            "sender (%s) == me (%s)? %s",
            event.sender,
            self.session.contacts.user_legacy_id,
            event.sender == self.session.contacts.user_legacy_id,
        )
        return await muc.get_participant_by_legacy_id(event.sender)

    async def listen(self):
        # we need to sync full state or else we don't get the list of all rooms
        resp = await self.sync(full_state=True)
        self.log.debug("Sync: %s", resp)
        if isinstance(resp, nio.SyncError):
            raise PermissionError(resp)
        self.__add_event_handlers()
        self.__launch_sync()

    def stop_listen(self):
        if self.__sync_task is None:
            return
        self.__sync_task.cancel()

    async def try_download(self, url: str) -> Optional[nio.DownloadResponse]:
        resp = await self.download(url)
        if isinstance(resp, nio.DownloadResponse):
            return resp
        self.log.warning("Could not download attachment: %r", resp)
        return None

    async def fetch_history(self, room_id: str, limit: int):
        sync_resp = await self.sync()
        self.log.debug("Sync resp: %s", sync_resp)
        if isinstance(sync_resp, nio.SyncError):
            return
        resp = await self.room_messages(
            room_id,
            limit=limit,
            start=sync_resp.next_batch,
        )
        if not isinstance(resp, nio.RoomMessagesResponse):
            self.log.warning("Could not fill history.", sync_resp)
            return
        return resp.chunk

    @catch_all
    async def on_event(self, room: nio.MatrixRoom, event: nio.Event):
        self.log.debug("Event %s '%s': %r", type(event), room, event)
        if getattr(event, "type", None) == "m.reaction":
            self.log.debug("Reaction")
            await self.on_reaction(room, event)

    @catch_all
    async def on_message(self, room: nio.MatrixRoom, event: nio.RoomMessage):
        self.log.debug("Message: %s", event)

        participant = await self.get_participant(room, event)
        await participant.send_matrix_message(event)

    async def on_presence(self, presence: nio.PresenceEvent):
        if presence.user_id == self.session.contacts.user_legacy_id:
            return
        try:
            contact = await self.session.contacts.by_legacy_id(presence.user_id)
        except XMPPError as e:
            self.log.debug("Ignoring presence: %s", presence, exc_info=e)
            return
        contact.update_presence(presence)

    @catch_all
    async def on_avatar(self, room: nio.MatrixRoom, event: nio.RoomAvatarEvent):
        muc = await self.__get_muc(room)
        muc.avatar = event.avatar_url

    @catch_all
    async def on_topic(self, room: nio.MatrixRoom, event: nio.RoomTopicEvent):
        muc = await self.__get_muc(room)
        participant = await self.get_participant(room, event)
        muc.subject = event.topic
        muc.subject_setter = participant.name
        muc.subject_date = server_timestamp_to_datetime(event)

    @catch_all
    async def on_name(self, room: nio.MatrixRoom, event: nio.RoomNameEvent):
        muc = await self.__get_muc(room)
        muc.name = event.name

    @catch_all
    async def on_sticker(self, room: nio.MatrixRoom, event: nio.StickerEvent):
        participant = await self.get_participant(room, event)

        resp = await self.download(event.url)
        if isinstance(resp, nio.DownloadResponse):
            await participant.send_files(
                [LegacyAttachment(data=resp.body, caption=event.body)]
            )
        else:
            self.log.error("Failed to download sticker: %r", resp)

    @catch_all
    async def on_member(self, room: nio.MatrixRoom, event: nio.RoomMemberEvent):
        muc = await self.__get_muc(room)
        participant = await self.get_participant(room, event)
        if event.membership == "join":
            pass
        elif event.membership == "leave":
            muc.remove_participant(participant)
        elif event.membership == "ban":
            # TODO: handle bans in slidge core
            pass
        elif event.membership == "invite":
            # TODO: what's that event exactly?
            pass

    @catch_all
    async def on_typing(self, room: nio.MatrixRoom, event: nio.TypingNoticeEvent):
        muc = await self.__get_muc(room)
        for user_id in event.users:
            participant = await muc.get_participant_by_legacy_id(user_id)
            participant.composing()

    @catch_all
    async def on_receipt(self, room: nio.MatrixRoom, event: nio.ReceiptEvent):
        muc = await self.__get_muc(room)
        for receipt in event.receipts:
            if receipt.receipt_type == "m.read":
                participant = await muc.get_participant_by_legacy_id(receipt.user_id)
                participant.displayed(receipt.event_id)

    @catch_all
    async def on_reaction(self, room: nio.MatrixRoom, event: nio.Event, **kw):
        self.log.debug("Reaction2")

        source = event.source
        relates = source["content"]["m.relates_to"]
        msg_id = await self.get_original_id(room.room_id, relates["event_id"])

        sender = source["sender"]
        emoji = relates["key"]

        await self.reactions.add(room.room_id, msg_id, sender, emoji, event.event_id)
        reactions = await self.reactions.get(room.room_id, msg_id, sender)

        participant = await self.get_participant(room, event)
        participant.react(msg_id, reactions, **kw)

    @catch_all
    async def on_redact(self, room: nio.MatrixRoom, event: nio.RedactionEvent):
        self.log.debug("Redaction: %s", event)
        participant = await self.get_participant(room, event)
        if reaction_target := self.reactions.remove(event.redacts):
            msg_id = await self.get_original_id(room.room_id, reaction_target.event)
            reactions = await self.reactions.get(
                reaction_target.room, msg_id, reaction_target.sender
            )
            participant.react(msg_id, reactions)
            return

        participant.moderate(event.redacts, reason=event.reason)

    @alru_cache(maxsize=1000)
    async def get_original_id(self, room_id: str, event_id: str) -> str:
        event = await self.get_event(room_id, event_id)
        if event is None:
            return event_id
        return get_replace(event.source) or event_id

    @alru_cache(maxsize=100)
    async def get_event(self, room_id: str, event_id: str) -> Optional[nio.Event]:
        resp = await self.session.matrix.room_get_event(room_id, event_id)
        if isinstance(resp, nio.RoomGetEventError):
            return None
        return resp.event
