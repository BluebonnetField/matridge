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

        if mxc := resp.avatar_url:
            self.avatar = await self.session.matrix.mxc_to_http(mxc)
        else:
            self.avatar = None

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

    async def jid_username_to_legacy_id(self, jid_username: str):
        u = await super().jid_username_to_legacy_id(jid_username)
        if not u.startswith("@"):
            raise XMPPError(
                "bad-request",
                f"'{jid_username}' is not a valid matrix username. "
                "Matrix usernames starts with @",
            )
        return u
