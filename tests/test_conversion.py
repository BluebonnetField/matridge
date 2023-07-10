import nio

from matridge.util import strip_reply_fallback, get_body


def test_reply_to():
    reply = {
        "content": {
            "body": "> dddd\n\n * for update a list of users i modified the updategroupparticipants functions",
            "format": "org.matrix.custom.html",
            "formatted_body": '<mx-reply><blockquote><a href="https://matrix.to/#/!XXXX.net&amp;via=matrix.org&amp;via=aria-net.org">In reply to</a> <a href="https://matrix.to/#/@XX">@SDASDA:matrix.org</a><br>'
            "aasdasdasd"
            "</blockquote></mx-reply> * for update a list of users i modified the updategroupparticipants functions",
            "m.new_content": {
                "body": "for update a list of users i modified the updategroupparticipants functions",
                "format": "org.matrix.custom.html",
                "formatted_body": "for update a list of users i modified the updategroupparticipants functions",
                "msgtype": "m.text",
            },
            "m.relates_to": {
                "event_id": "asdasda",
                "rel_type": "m.replace",
            },
            "msgtype": "m.text",
        },
        "origin_server_ts": 1688997470785,
        "sender": "@asdasd:matrix.org",
        "type": "m.room.message",
        "unsigned": {"age": 75665575},
        "event_id": "asdasd",
        "room_id": "!whatsmeow-v9:maunium.net",
    }
    event = nio.Event.parse_event(reply)
    assert (
        get_body(event)
        == " * for update a list of users i modified the updategroupparticipants functions"
    )
    reply = {
        "content": {
            "body": "> <@nicocool:matrix.org> asdfasdf\n\nsadfsadf",
            "format": "org.matrix.custom.html",
            "formatted_body": '<mx-reply><blockquote><a href="https://matrix.to/#/!fFWFUtcegfROhIEMbt:matrix.org/$gdL7K5fh98eQTAl_EUdFkvH2xskV0UCO5i-vUeVY3Zk?via=matrix.org">In reply to</a> <a href="https://matrix.to/#/@nicocool:matrix.org">@nicocool:matrix.org</a><br>asdfasdf</blockquote></mx-reply>sadfsadf',
            "m.relates_to": {
                "m.in_reply_to": {
                    "event_id": "$gdL7K5fh98eQTAl_EUdFkvH2xskV0UCO5i-vUeVY3Zk"
                }
            },
            "msgtype": "m.text",
        },
        "origin_server_ts": 1689102822908,
        "sender": "@nicovraimentcool:matrix.org",
        "type": "m.room.message",
        "unsigned": {"age": 710},
        "event_id": "$RAOwtjYb487xbVc9zmVJN_rLVLeSKLoxmGyucp9BsL4",
    }
    event = nio.Event.parse_event(reply)
    assert get_body(event) == "sadfsadf"


def test_strip_reply_fallback():
    assert (
        strip_reply_fallback(  # language=html
            "<mx-reply>"
            '<blockquote><a href="https://matrix.to/XXX">In reply to</a> <a href="https://matrix.to/#/@nicovraimentcool:matrix.org">@nicovraimentcool:matrix.org</a><br>fdg</blockquote>'
            "</mx-reply>"
            "dfggg"
        )
        == "dfggg"
    )


def test_notice():
    notice = {
        "content": {
            "body": "**[mautrix/facebook]** sdfsafasdfsadf starred the repo",
            "com.beeper.linkpreviews": [],
            "format": "org.matrix.custom.html",
            "formatted_body": '<strong>[<a data-mautrix-exclude-plaintext href="https://github.com/mautrix/facebook">mautrix/facebook</a>]</strong> <a data-mautrix-exclude-plaintext href="https://github.com/sdfsafasdfsadf">sdf</a> starred the repo',
            "msgtype": "m.notice",
            "xyz.maubot.github.webhook": {
                "delivery_ids": ["asdfasdf-1d28-11ee-9be9-fec185c673cf"],
                "event_type": "star",
            },
        },
        "origin_server_ts": 1688776979579,
        "room_id": "!facebook-v10:maunium.net",
        "sender": "@github:maunium.net",
        "type": "m.room.message",
        "unsigned": {},
        "event_id": "sdfasdf",
        "user_id": "@github:maunium.net",
    }
    event = nio.Event.parse_event(notice)
    assert get_body(event) == "**[mautrix/facebook]** sdfsafasdfsadf starred the repo"
    notice = {
        "content": {
            "body": "**[tulir/whatsmeow]** tulir pushed [1 commit](https://github.com/tulir/whatsmeow/compare/6e8b189f1308...93091c7024da) to main:\n● `93091c70` Fix decrypting message secret reactions",
            "com.beeper.linkpreviews": [],
            "format": "org.matrix.custom.html",
            "formatted_body": '<strong>[<a data-mautrix-exclude-plaintext href="https://github.com/tulir/whatsmeow">tulir/whatsmeow</a>]</strong> <a data-mautrix-exclude-plaintext href="https://github.com/tulir">tulir</a>      pushed\n        <a href="https://github.com/tulir/whatsmeow/compare/6e8b189f1308...93091c7024da">1 commit</a>\n    to\n main:<ul>         <li>\n            <code><a data-mautrix-exclude-plaintext href="https://github.com/tulir/whatsmeow/commit/93091c7024dac73790fafe4036f6771352d40ca0">93091c70</a></code>\n            Fix decrypting message secret reactions\n        </li>\n </ul>',
            "msgtype": "m.notice",
            "xyz.maubot.github.webhook": {
                "delivery_ids": ["7e0044f0-1f0b-11ee-9cbd-cba6b984b843"],
                "event_type": "push",
            },
        },
        "origin_server_ts": 1688984472208,
        "room_id": "!whatsmeow-v9:maunium.net",
        "sender": "@github:maunium.net",
        "type": "m.room.message",
        "unsigned": {},
        "event_id": "$-ff",
        "user_id": "@github:maunium.net",
    }
    event = nio.Event.parse_event(notice)
    assert (
        get_body(event)
        == "**[tulir/whatsmeow]** tulir pushed [1 commit](https://github.com/tulir/whatsmeow/compare/6e8b189f1308...93091c7024da) to main:\n● `93091c70` Fix decrypting message secret reactions"
    )
