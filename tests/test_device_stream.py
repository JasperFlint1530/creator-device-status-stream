import httpx

from device_stream import DeviceStatus, DeviceStatusStream, InfraiRealtime


class RecordingRealtime:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.published: list[tuple[str, DeviceStatus, str]] = []

    def create_channel(self, channel: str) -> dict:
        self.created.append(channel)
        return {"channel": channel}

    def publish_status(self, channel: str, status: DeviceStatus, event_id: str) -> dict:
        self.published.append((channel, status, event_id))
        return {"published": True}


def test_repeated_device_state_is_not_published_twice() -> None:
    realtime = RecordingRealtime()
    stream = DeviceStatusStream(realtime)  # type: ignore[arg-type]
    update = DeviceStatus(
        creator_id="creator-42",
        device_id="render-node-7",
        workflow="content_processing",
        state="active",
        progress=60,
    )

    first = stream.record(update)
    repeated = stream.record(update)

    assert first.changed is True
    assert repeated.changed is False
    assert realtime.created == ["creator-creator-42-devices"]
    assert len(realtime.published) == 1


def test_create_channel_omits_optional_vendor() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/realtime/channel/create"
        assert request.content == b'{"channel":"creator-test-devices","type":"presence"}'
        return httpx.Response(200, json={"ok": True, "data": {"channel": "creator-test-devices"}})

    realtime = InfraiRealtime("test-key", transport=httpx.MockTransport(respond))
    assert realtime.create_channel("creator-test-devices") == {"channel": "creator-test-devices"}
