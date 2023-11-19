from collections import defaultdict, namedtuple
from typing import TYPE_CHECKING, Literal, Optional, overload

import nio

if TYPE_CHECKING:
    from matridge.matrix import Client

ReactionTarget = namedtuple("ReactionTarget", ["room", "event", "sender"])
Reaction = namedtuple("Reaction", ["event", "emoji"])


class ReactionCache:
    """
    To avoid fetching history on each matrix reaction event, we store the
    "reaction state" per sender per message.

    This is because matrix reaction events are atomic, unlike XMPP reactions
    which contain the full state in each event.
    """

    # TODO: periodically purge cache for messages older than XX days *and/or*
    #       implement proper non-RAM persistent storage

    def __init__(self, client: "Client"):
        self.matrix = client
        self.log = client.session.log

        # key = room, msg, sender
        self._reaction_cache = defaultdict[ReactionTarget, list[Reaction]](list)

        # key = event
        # on redaction events, we only get the
        self._event_cache = dict[str, ReactionTarget]()

    async def _fetch_if_needed(self, target: ReactionTarget):
        if target not in self._reaction_cache:
            await self._fetch(target.room, target.sender)
        # nothing was added for this target, meaning it's empty
        # initialize an empty list to avoid checking for the same message later
        if target not in self._reaction_cache:
            self._reaction_cache[target] = []

    async def _fetch(self, room: str, sender: Optional[str] = None, limit=100):
        self.log.debug("Getting reactions...")

        filt = {"senders": [sender], "types": ["m.reaction"]}

        sync_resp = await self.matrix.sync(sync_filter=filt)
        self.log.debug("Sync")
        if isinstance(sync_resp, nio.SyncError):
            return

        resp = await self.matrix.room_messages(
            room,
            limit=limit,
            start=sync_resp.next_batch,
            message_filter=filt,
        )
        if not isinstance(resp, nio.RoomMessagesResponse):
            return

        for event in resp.chunk:
            if not isinstance(event, nio.ReactionEvent):
                continue
            reacts_to = event.reacts_to
            if not reacts_to:
                continue
            emoji = event.key
            if emoji:
                target = ReactionTarget(
                    room=room,
                    sender=event.sender,
                    event=await self.matrix.get_original_id(room, reacts_to),
                )
                self._reaction_cache[target].append(
                    Reaction(event=event.event_id, emoji=emoji)
                )
                self._event_cache[event.event_id] = target
            else:
                self.log.debug("Weird reaction? %s", event)

    async def add(
        self, room: str, msg: str, sender: str, emoji: str, reaction_event: str
    ) -> None:
        target = ReactionTarget(room=room, event=msg, sender=sender)
        await self._fetch_if_needed(target)
        reaction = Reaction(event=reaction_event, emoji=emoji)
        self._reaction_cache[target].append(reaction)
        self._event_cache[reaction_event] = target
        self.log.debug("Added: %s - %s", target, reaction)

    @overload
    async def get(
        self, room: str, msg: str, sender: str, with_event_ids: Literal[False]
    ) -> set[str]:
        ...

    @overload
    async def get(self, room: str, msg: str, sender: str) -> set[str]:
        ...

    @overload
    async def get(
        self, room: str, msg: str, sender: str, with_event_ids: Literal[True]
    ) -> dict[str, str]:
        ...

    async def get(self, room, msg, sender, with_event_ids=False):
        target = ReactionTarget(room=room, event=msg, sender=sender)
        await self._fetch_if_needed(target)
        if with_event_ids:
            return {r.emoji: r.event for r in self._reaction_cache[target]}
        else:
            return set(r.emoji for r in self._reaction_cache[target])

    def remove(self, event_id: str) -> Optional[ReactionTarget]:
        self.log.debug("Needle: %s; Haystack: %s", event_id, self._event_cache)
        target = self._event_cache.pop(event_id, None)
        if target is None:
            return None

        cache = self._reaction_cache[target]
        cache[:] = [r for r in cache if r.event != event_id]
        return target


__all__ = ("ReactionCache",)
