from typing import Union

import nio
from nio.crypto import OlmDevice, TrustState
from slidge.command import Command, CommandAccess, Form, FormField, TableResult
from slidge.command.base import FormValues
from slixmpp.exceptions import XMPPError

from .group import MUC
from .session import Session


class ListSpaces(Command):
    NAME = "Matrix spaces"
    CHAT_COMMAND = NODE = "spaces"
    HELP = "List the matrix spaces you're part of"
    ACCESS = CommandAccess.USER_LOGGED

    async def run(self, session: Session, _ifrom, *args: str) -> Form:  # type:ignore
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
                        {"label": room.display_name, "value": str(i)}
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
            description=f"Rooms of '{space.display_name}'",
            jids_are_mucs=True,
            items=[{"name": muc.name, "jid": str(muc.jid)} for muc in mucs],
        )


class ManageTrust(Command):
    NAME = "Manage trust"
    CHAT_COMMAND = NODE = "verify"
    HELP = "Manage which OLM keys you trust or not."
    ACCESS = CommandAccess.USER_LOGGED

    HUMAN_STATES = {0: "unset", 1: "verified", 2: "blacklisted", 3: "ignored"}

    def __human_device(self, d: OlmDevice, state=True):
        r = f"{d.ed25519} of {d.user_id}"
        if state:
            return r + f" ({self.HUMAN_STATES[d.trust_state.value]})"
        return r

    async def run(
        self,
        session: Session,  # type:ignore
        _ifrom,
        *args: str,
    ) -> Union[Form, str]:
        devices = list[OlmDevice](session.matrix.olm.device_store)
        device_dict = {d.id: d for d in devices}

        # this part if for chat commands only
        if args:
            if args[0] == "all":
                return await self.step2(
                    {
                        "device": list(device_dict.keys()),  # type:ignore
                        "new_state": "verified",
                    },
                    session,
                    None,
                    device_dict,
                )

            else:
                return await self.step2(
                    {"device": args[0].upper(), "new_state": "verified"},
                    session,
                    None,
                    device_dict,
                )

        return Form(
            title=self.NAME,
            instructions="Choose the session(s) which trust state you want to change",
            handler=self.step2,  # type:ignore
            handler_args=(device_dict,),
            fields=[
                FormField(
                    "device",
                    label="Device(s)",
                    type="list-multi",
                    options=[
                        {"label": self.__human_device(d), "value": d.id}
                        for d in devices
                    ],
                ),
                FormField(
                    "new_state",
                    label="What new status do you want to give the selected devices?",
                    type="list-single",
                    options=[
                        {"label": v, "value": v} for v in self.HUMAN_STATES.values()
                    ],
                ),
            ],
        )

    async def step2(
        self,
        form_values: FormValues,
        session: Session,
        _ifrom,
        devices: dict[str, OlmDevice],
    ):
        new_state = form_values["new_state"]
        matrix = session.matrix
        result = ""
        for device_name in form_values["device"]:  # type:ignore
            device = devices[device_name]
            change = False
            if new_state == "unset":
                if device.trust_state == TrustState.verified:
                    change = matrix.unverify_device(device)
                elif device.trust_state == TrustState.ignored:
                    change = matrix.unignore_device(device)
                elif device.trust_state == TrustState.blacklisted:
                    change = matrix.unblacklist_device(device)
            elif new_state == "verified":
                change = session.matrix.verify_device(device)
            elif new_state == "blacklisted":
                change = session.matrix.blacklist_device(device)
            elif new_state == "ignored":
                change = session.matrix.ignore_device(device)

            if change:
                result += (
                    f"\nThe status of {self.__human_device(device, False)} "
                    f"is now {new_state}."
                )
            else:
                result += (
                    f"\nThe status of {self.__human_device(device, False)} "
                    f"has not changed."
                )

        return result or "Nothing was changed."
