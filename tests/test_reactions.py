from collections import defaultdict
import logging

import nio
import pytest

from matridge.reactions import ReactionCache


class MockMatrix:
    class session:
        log = logging.getLogger()

    @staticmethod
    async def room_messages(room, limit, start, message_filter):
        if room == "bad":
            return nio.RoomMessagesError

        return nio.RoomMessagesResponse(
            None,
            start=None,
            chunk=[
                nio.UnknownEvent(
                    type="m.reaction",
                    source=mock_source(
                        {
                            "event_id": "1",
                            "sender": "someone",
                            "content": {
                                "m.relates_to": {"event_id": "msg_id", "key": "<3"}
                            },
                        }
                    ),
                ),
                nio.UnknownEvent(
                    type="m.reaction",
                    source=mock_source(
                        {
                            "event_id": "2",
                            "sender": "someone",
                            "content": {
                                "m.relates_to": {"event_id": "msg_id", "key": "+1"}
                            },
                        }
                    ),
                ),
                nio.UnknownEvent(
                    type="m.reaction",
                    source=mock_source(
                        {
                            "event_id": "3",
                            "sender": "someone",
                            "content": {
                                "m.relates_to": {
                                    "event_id": "other_msg_id",
                                    "key": "-1",
                                }
                            },
                        }
                    ),
                ),
            ],
        )

    @staticmethod
    async def sync(sync_filter):
        return nio.SyncResponse(None, None, None, None, None, None)

    @staticmethod
    async def get_original_id(room, event_id):
        return event_id


def mock_source(data):
    x = defaultdict(str)
    x.update(data)
    return x


@pytest.mark.asyncio
async def test_no_response():
    cache = ReactionCache(MockMatrix)
    assert await cache.get("bad", "msg_id", "sender") == set()


@pytest.mark.asyncio
async def test_no_response_add_remove():
    cache = ReactionCache(MockMatrix)

    await cache.add("bad", "msg_id", "sender", "<3", "heart_event")
    assert await cache.get("bad", "msg_id", "sender") == {"<3"}

    await cache.add("bad", "msg_id", "sender", "-1", "-1_event")
    assert await cache.get("bad", "msg_id", "sender") == {"<3", "-1"}

    cache.remove("heart_event")
    assert await cache.get("bad", "msg_id", "sender") == {"-1"}


@pytest.mark.asyncio
async def test_remove_unknown_event():
    cache = ReactionCache(MockMatrix)
    cache.remove("unknown")
    assert len(cache._event_cache) == 0


@pytest.mark.asyncio
async def test_fetch():
    cache = ReactionCache(MockMatrix)
    assert await cache.get("good", "msg_id", "someone") == {"<3", "+1"}


@pytest.mark.asyncio
async def test_fetch_add_remove():
    cache = ReactionCache(MockMatrix)
    target = "good", "msg_id", "someone"
    await cache.add(*target, "prout", "4")
    assert await cache.get(*target) == {"<3", "+1", "prout"}
    cache.remove("2")
    assert await cache.get(*target) == {"<3", "prout"}
