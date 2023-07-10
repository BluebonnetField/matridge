from asyncio import Task
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

import nio
from slidge import LegacyContact, LegacyRoster
from slixmpp.exceptions import XMPPError

if TYPE_CHECKING:
    from .session import Session


class Contact(LegacyContact[str]):
    """
    We don't implement direct messages but the what's parsed here will propagate
    to MUC participants.
    """

    session: "Session"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.__download_avatar_task: Optional[Task] = None

    async def update_info(self):
        resp = await self.session.matrix.get_profile(self.legacy_id)
        if not isinstance(resp, nio.ProfileGetResponse):
            if resp.status_code == "M_FORBIDDEN":
                self.log.warning("Could not get profile: %s", resp)
                return
            raise XMPPError("internal-server-error", str(resp))

        self.name = resp.displayname

        if resp.other_info:
            self.set_vcard(note=str(resp.other_info))

        if not resp.avatar_url:
            return

        self.__download_avatar_task = self.xmpp.loop.create_task(
            self.__download_avatar(resp.avatar_url)
        )

    async def __download_avatar(self, avatar_url: str):
        resp = await self.session.matrix.try_download(avatar_url)
        if resp:
            await self.set_avatar(resp.body, resp.uuid or avatar_url)

    def update_presence(self, p: nio.PresenceEvent):
        kw = dict(status=p.status_msg)
        if last := p.last_active_ago is not None:
            kw["last_seen"] = datetime.now() - timedelta(seconds=last)
        if p.currently_active:
            self.online(**kw)
        else:
            self.away(**kw)


class Roster(LegacyRoster[str, Contact]):
    session: "Session"
