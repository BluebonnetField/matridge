from slidge.util.test import SlidgeTest

import matridge


class TestMatridge(SlidgeTest):
    def test_base(self):
        self.recv("<presence />")
        reply = self.next_sent()
        assert reply["type"] == "error"
