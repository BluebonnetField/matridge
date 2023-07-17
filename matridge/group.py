import asyncio
import typing

import nio
from slidge import LegacyBookmarks, LegacyMUC, LegacyParticipant, MucType
from slixmpp.exceptions import XMPPError

from . import config
from .util import MatrixMixin, server_timestamp_to_datetime

if typing.TYPE_CHECKING:
    from .session import Session


class Participant(MatrixMixin, LegacyParticipant):
    session: "Session"
    muc: "MUC"


class Bookmarks(LegacyBookmarks):
    session: "Session"

    async def fill(self):
        self.log.debug("Filling rooms")
        for room in self.session.matrix.rooms:
            try:
                await self.by_legacy_id(room)
            except XMPPError as e:
                self.log.debug(
                    "%s is not a group chat or trouble getting it: %r", room, e
                )


class MUC(LegacyMUC[str, str, Participant, str]):
    session: "Session"
    type = MucType.GROUP

    async def get_room(self):
        try:
            return self.session.matrix.rooms[self.legacy_id]
        except KeyError:
            raise XMPPError("item-not-found", f"No room named {self.legacy_id}")

    async def get_message(self, msg_id: str) -> typing.Optional[nio.Event]:
        resp = await self.session.matrix.room_get_event(self.legacy_id, msg_id)
        self.log.debug("Resp: %s", resp)
        if isinstance(resp, nio.RoomGetEventResponse):
            return resp.event
        return None

    async def update_info(self):
        room = await self.get_room()

        if new := room.replacement_room:
            raise XMPPError("redirect", f"{new}")
        self.log.debug("Children: %s", room.children)
        if room.children:
            raise XMPPError("bad-request", "This is not a real room but a 'space'")

        self.user_nick = room.user_name(self.session.matrix.user_id)

        # workaround for weird bug where user participant doesn't have code=110
        # in their presence
        # TODO: ^ investigate this
        part = await self.get_participant(self.user_nick)
        part.is_user = True

        self.log.debug("User nick: %s", self.user_nick)
        self.name = room.name or "unnamed"
        self.log.debug("Avatar: %s", room.room_avatar_url)
        self.n_participants = room.member_count
        self.subject = room.topic
        if not room.room_avatar_url:
            return
        resp = await self.session.matrix.download(room.room_avatar_url)
        if isinstance(resp, nio.DownloadResponse):
            self.avatar = resp.body
        else:
            self.log.debug("No avatar: %s", resp)

    async def fill_participants(self):
        room = await self.get_room()
        for i in range(config.MAX_WAIT_MEMBERS_SYNC):
            if room.members_synced:
                break
            self.log.debug("Waiting for members to be synced")
            await asyncio.sleep(1)
        else:
            self.log.debug("Do not wait for members to be synced anymore")

        for user_id, user in list(room.users.items())[: config.MAX_PARTICIPANTS_FETCH]:
            if user_id == self.session.matrix.user_id:
                self.log.debug(
                    "Skipping: %s %s", user.user_id, self.session.matrix.user_id
                )
                continue
            try:
                await self.get_participant_by_legacy_id(user.user_id)
            except XMPPError:
                continue

    async def backfill(
        self,
        oldest_message_id=None,
        oldest_message_date=None,
    ):
        for event in await self.session.matrix.fetch_history(
            self.legacy_id, config.MAX_HISTORY_FETCH
        ):
            when = server_timestamp_to_datetime(event)
            if (
                oldest_message_date and when >= oldest_message_date
            ) or oldest_message_id == event.event_id:
                continue
            if isinstance(event, nio.RoomMessage):
                participant = await self.session.matrix.get_participant(
                    await self.get_room(), event
                )
                await participant.send_matrix_message(event, archive_only=True)
                continue
            # FIXME: this breaks everything, probably because of parallel calls
            #        to sync()
            # if isinstance(event, nio.UnknownEvent) and event.type == "m.reaction":
            #     await self.session.matrix.on_reaction(
            #         await self.get_room(), event, when=when, archive_only=True
            #     )
            #     continue
            self.log.debug("Not back-filling with %s", event)
