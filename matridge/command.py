import nio
from slidge.core.command import Command, CommandAccess, Form, FormField, TableResult
from slidge.core.command.base import FormValues
from slixmpp.exceptions import XMPPError

from .group import MUC
from .session import Session


class ListSpaces(Command):
    NAME = "Matrix spaces"
    CHAT_COMMAND = NODE = "spaces"
    HELP = "List the matrix spaces you're part of"
    ACCESS = CommandAccess.USER_LOGGED

    async def run(self, session: Session, _ifrom, *args: str):  # type:ignore
        spaces = list[nio.MatrixRoom]()
        for room in session.matrix.rooms.values():
            if room.children:
                spaces.append(room)
        spaces = sorted(spaces, key=lambda r: r.name)
        return Form(
            title=self.NAME,
            instructions="Choose a space to list its children rooms. "
            "NB: as of now, you can also see rooms that you are a member of.",
            handler=self.finish,  # type:ignore
            handler_args=(spaces,),
            fields=[
                FormField(
                    "space",
                    label="Matrix space",
                    type="list-single",
                    options=[
                        {"label": room.name or "unnamed", "value": str(i)}
                        for i, room in enumerate(spaces)
                    ],
                )
            ],
        )

    @staticmethod
    async def finish(
        form_values: FormValues,
        session: Session,
        _ifrom,
        rooms: list[nio.MatrixRoom],
    ):
        space = rooms[int(form_values["space"])]  # type:ignore
        mucs = list[MUC]()
        for room_id in space.children:
            try:
                mucs.append(await session.bookmarks.by_legacy_id(room_id))
            except XMPPError:
                continue

        mucs = sorted(mucs, key=lambda muc: muc.name)
        return TableResult(
            fields=[FormField("name"), FormField("jid", type="jid-single")],
            description=f"Rooms of '{space.name or 'unnamed'}'",
            jids_are_mucs=True,
            items=[{"name": muc.name, "jid": muc.jid} for muc in mucs],  # type:ignore
        )
