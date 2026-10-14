"""Runnable HTTP entry point for creator device dashboards."""

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from device_stream import (
    DashboardSession,
    DeviceStatus,
    DeviceStatusStream,
    InfraiError,
    InfraiRealtime,
    PresenceSnapshot,
    StreamResult,
)


class SessionRequest(BaseModel):
    creator_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)


def build_stream() -> DeviceStatusStream:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    return DeviceStatusStream(InfraiRealtime(api_key))


app = FastAPI(title="Creator Device Stream")
_stream: DeviceStatusStream | None = None


def get_stream() -> DeviceStatusStream:
    global _stream
    if _stream is None:
        _stream = build_stream()
    return _stream


StreamDependency = Annotated[DeviceStatusStream, Depends(get_stream)]


def as_http_error(error: InfraiError) -> HTTPException:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": error.code, "error": error.detail})


@app.post("/device-status", response_model=StreamResult)
def publish_device_status(status: DeviceStatus, stream: StreamDependency) -> StreamResult:
    try:
        return stream.record(status)
    except InfraiError as error:
        raise as_http_error(error) from error


@app.post("/dashboard-session", response_model=DashboardSession)
def create_dashboard_session(request: SessionRequest, stream: StreamDependency) -> DashboardSession:
    channel = stream.channel_for(request.creator_id)
    try:
        data = stream._realtime.issue_dashboard_token(request.client_id, channel)
    except InfraiError as error:
        raise as_http_error(error) from error
    return DashboardSession(channel=channel, token=str(data["token"]))


@app.get("/creators/{creator_id}/presence", response_model=PresenceSnapshot)
def creator_presence(creator_id: str, stream: StreamDependency) -> PresenceSnapshot:
    channel = stream.channel_for(creator_id)
    try:
        data = stream._realtime.get_presence(channel)
    except InfraiError as error:
        raise as_http_error(error) from error
    return PresenceSnapshot(channel=channel, presence=data)

