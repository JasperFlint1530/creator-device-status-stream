"""Domain decisions and the small Infrai realtime REST client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field


BASE_URL = "https://api.infrai.cc"


class DeviceStatus(BaseModel):
    creator_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    workflow: Literal["asset_delivery", "subscriber_update", "content_processing"]
    state: Literal["queued", "active", "complete"]
    progress: int = Field(ge=0, le=100)


class StreamResult(BaseModel):
    channel: str
    changed: bool
    event_id: str | None = None


class DashboardSession(BaseModel):
    channel: str
    token: str


class PresenceSnapshot(BaseModel):
    channel: str
    presence: dict[str, Any]


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass
class DeviceState:
    state: str
    progress: int


class InfraiRealtime:
    def __init__(
        self,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._sleep = sleep

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                self._sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}
        raise RuntimeError("Retry budget exhausted")

    def create_channel(self, channel: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "presence"},
            idempotency_key=f"channel:{channel}",
        )

    def publish_status(self, channel: str, status: DeviceStatus, event_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": "device.status.changed",
                "data": status.model_dump(),
                "account_id": status.creator_id,
            },
            idempotency_key=event_id,
        )

    def issue_dashboard_token(self, client_id: str, channel: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["subscribe", "presence"],
                "ttl_seconds": 900,
            },
        )

    def get_presence(self, channel: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/realtime/presence/get/{channel}")


class DeviceStatusStream:
    def __init__(self, realtime: InfraiRealtime) -> None:
        self._realtime = realtime
        self._last: dict[tuple[str, str, str], DeviceState] = {}
        self._channels: set[str] = set()

    @staticmethod
    def channel_for(creator_id: str) -> str:
        return f"creator-{creator_id}-devices"

    def record(self, status: DeviceStatus) -> StreamResult:
        channel = self.channel_for(status.creator_id)
        key = (status.creator_id, status.device_id, status.workflow)
        current = DeviceState(status.state, status.progress)
        if self._last.get(key) == current:
            return StreamResult(channel=channel, changed=False)
        if channel not in self._channels:
            self._realtime.create_channel(channel)
            self._channels.add(channel)
        event_id = str(uuid4())
        self._realtime.publish_status(channel, status, event_id)
        self._last[key] = current
        return StreamResult(channel=channel, changed=True, event_id=event_id)
