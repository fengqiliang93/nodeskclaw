import json

from app.services.channel_adapters.feishu_ws_client import _FeishuMessageBatcher


class FakeTimer:
    created: list["FakeTimer"] = []

    def __init__(self, interval, callback, args=None, kwargs=None):
        self.interval = interval
        self.callback = callback
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.daemon = False
        self.cancelled = False
        FakeTimer.created.append(self)

    def start(self):
        return None

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.callback(*self.args, **self.kwargs)


def test_message_batcher_merges_multiple_text_messages_within_window():
    FakeTimer.created = []
    handled: list[tuple[str, str, str]] = []
    batcher = _FeishuMessageBatcher(
        lambda chat_id, sender_open_id, content: handled.append((chat_id, sender_open_id, content)),
        window_seconds=1.5,
        timer_factory=FakeTimer,
    )

    batcher.add("chat-1", "user-1", {"message_type": "text", "content": json.dumps({"text": "第一条"})})
    batcher.add("chat-1", "user-1", {"message_type": "text", "content": json.dumps({"text": "第二条"})})

    assert len(FakeTimer.created) == 2
    assert FakeTimer.created[0].cancelled is True

    FakeTimer.created[1].fire()

    assert handled == [("chat-1", "user-1", "第一条\n第二条")]


def test_message_batcher_merges_mixed_message_types_in_order():
    FakeTimer.created = []
    handled: list[tuple[str, str, str]] = []
    batcher = _FeishuMessageBatcher(
        lambda chat_id, sender_open_id, content: handled.append((chat_id, sender_open_id, content)),
        timer_factory=FakeTimer,
    )

    batcher.add("chat-2", "user-2", {"message_type": "image", "content": "{}"})
    batcher.add("chat-2", "user-2", {"message_type": "text", "content": json.dumps({"text": "补一句"})})
    batcher.add("chat-2", "user-2", {"message_type": "file", "content": "{}"})

    FakeTimer.created[-1].fire()

    assert handled == [("chat-2", "user-2", "[image message]\n补一句\n[file message]")]


def test_message_batcher_separates_different_conversations():
    FakeTimer.created = []
    handled: list[tuple[str, str, str]] = []
    batcher = _FeishuMessageBatcher(
        lambda chat_id, sender_open_id, content: handled.append((chat_id, sender_open_id, content)),
        timer_factory=FakeTimer,
    )

    batcher.add("chat-a", "user-1", {"message_type": "text", "content": json.dumps({"text": "A"})})
    batcher.add("chat-b", "user-1", {"message_type": "text", "content": json.dumps({"text": "B"})})

    FakeTimer.created[0].fire()
    FakeTimer.created[1].fire()

    assert handled == [
        ("chat-a", "user-1", "A"),
        ("chat-b", "user-1", "B"),
    ]


def test_message_batcher_flush_all_emits_pending_messages_once():
    FakeTimer.created = []
    handled: list[tuple[str, str, str]] = []
    batcher = _FeishuMessageBatcher(
        lambda chat_id, sender_open_id, content: handled.append((chat_id, sender_open_id, content)),
        timer_factory=FakeTimer,
    )

    batcher.add("chat-3", "user-3", {"message_type": "text", "content": json.dumps({"text": "结束前消息"})})
    batcher.flush_all()

    assert handled == [("chat-3", "user-3", "结束前消息")]
    assert FakeTimer.created[-1].cancelled is True
