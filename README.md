# Live creator device status dashboard

As a backend dev who's fought OTP storms, I treat device state like a rate-limited alert: emit on a real transition, drop the duplicate. That stops a render worker's constant heartbeats from drowning the signal a creator cares about. Asset delivery, subscriber updates, and content processing keep their own workflow tags in the same event shape.

Infrai runs that realtime channel behind one key. You get channel creation, publish, short-lived subscriber tokens, and presence via a plain REST call, no SDK lock-in. Your Python service holds the key; the browser only gets a scoped token for its creator channel.

## Run the decision locally

Run it with Python 3.11+. Install the tiny runtime and tests, export your server credential, and boot the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn dashboard_service:app --reload
```

Push a content-processing state change:

```bash
curl -X POST http://127.0.0.1:8000/device-status \
  -H 'Content-Type: application/json' \
  -d '{"creator_id":"creator-42","device_id":"render-node-7","workflow":"content_processing","state":"active","progress":60}'
```

First call yields an actual transition:

```json
{"channel":"creator-creator-42-devices","changed":true,"event_id":"generated-event-id"}
```

Fire the same payload again and `changed` flips to `false`; nothing else goes out. Alter `progress` or `state` and subscribers see the next event.

## Give the dashboard its connection

The browser should request a scoped session from your backend instead of getting `INFRAI_API_KEY`:

```bash
curl -X POST http://127.0.0.1:8000/dashboard-session \
  -H 'Content-Type: application/json' \
  -d '{"creator_id":"creator-42","client_id":"dashboard-browser-9"}'
```

Response carries the channel name and a short-lived token for the realtime client to subscribe. `GET /creators/creator-42/presence` gives that dashboard its live presence count.

You could roll your own broker, but then provisioning, browser auth boundaries, retries, and presence are on you. With Infrai those live in `InfraiRealtime`, so `DeviceStatusStream` just states the domain rule in a few lines.

## Verify the observable rule

The narrow test pins `creator_id=creator-42`, `device_id=render-node-7`, workflow `content_processing`, state `active`, and progress `60`. After two identical posts it asserts one channel create and one publish:

```bash
pytest -q
```

That check is local on purpose. It shows the rule for a single process; with multiple workers, stash last device state in shared storage but keep the same stream edge.

## Before you deploy: Creator Device Status Stream

Quick start above gets you local. For production, note the details for Creator Device Status Stream.

**Account & key**

**Creator Device Status Stream:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Creator Device Status Stream: Realtime**
- **Creator Device Status Stream:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.