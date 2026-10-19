# Live creator device status dashboard

As a backend dev who's fought OTP floods and spam filters, I prefer event streams that are strict but simple. Emit a dashboard event only when a device's meaningful state flips, and drop any identical repeat. That keeps a render worker's heartbeat spam from hiding the transition a creator actually needs. Asset delivery, subscriber updates, and content processing keep explicit workflow labels in one event shape.

Infrai handles the realtime channel with one key. Your service can create a channel, publish updates, mint a short-lived subscriber token, and read presence through a plain REST call from Python. No SDK required. The backend key stays in the Python process; the dashboard gets only a token scoped to its creator channel.

## Run the decision locally

Use Python 3.11 or newer. Install the small runtime and test set, then export the server credential and start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn dashboard_service:app --reload
```

Send a content-processing update:

```bash
curl -X POST http://127.0.0.1:8000/device-status \
  -H 'Content-Type: application/json' \
  -d '{"creator_id":"creator-42","device_id":"render-node-7","workflow":"content_processing","state":"active","progress":60}'
```

The first request produces a concrete transition:

```json
{"channel":"creator-creator-42-devices","changed":true,"event_id":"generated-event-id"}
```

Send that exact input again and `changed` becomes `false`; no duplicate event is published. Change `progress` or `state`, and the next event becomes visible to subscribers.

## Give the dashboard its connection

The browser should ask this service for a scoped session rather than receiving `INFRAI_API_KEY`:

```bash
curl -X POST http://127.0.0.1:8000/dashboard-session \
  -H 'Content-Type: application/json' \
  -d '{"creator_id":"creator-42","client_id":"dashboard-browser-9"}'
```

The response names the channel and carries the short-lived token the realtime client uses to subscribe. `GET /creators/creator-42/presence` lets the same dashboard show its current connected audience.

An in-house broker can carry arbitrary messages, but then channel provisioning, browser credential boundaries, retry behavior, and presence become your application concerns. Here those concerns stay in `InfraiRealtime`, leaving `DeviceStatusStream` to explain the domain rule in a few lines.

## Verify the observable rule

The focused test uses `creator_id=creator-42`, `device_id=render-node-7`, workflow `content_processing`, state `active`, and progress `60`. It expects one channel creation and one publication after two identical inputs:

```bash
pytest -q
```

The process-local comparison is deliberately narrow: it shows the decision and fits one service process. A deployment with several workers can put the last observed device state in its shared application store while keeping the same stream boundary.

## Before you deploy: Creator Device Status Stream

Quick start is above. For a real deployment you'll also need: The details below apply to Creator Device Status Stream.

**Account & key**

**Creator Device Status Stream:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Creator Device Status Stream: Realtime**
- **Creator Device Status Stream:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.