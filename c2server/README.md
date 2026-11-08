# O.MG C2 Server v4

The server retains the encrypted C2 protocol used by the firmware and serves
the shared v4 WebUI through a byte-preserving administration API.

The cable backend remains authoritative for product capabilities, service
ownership, admission decisions, HIDX state, payload state, and operation
results. The server persists transport queues and polling rates; it does not
invent or override device state. The WebUI refreshes that state through the
same `SVStatus`, `SVPreflight`, and feature APIs used by a direct connection.

Install and provision from this directory:

```sh
python3 -m pip install -r requirements.txt
python3 c2server.py provision cable-one 10 1 60
python3 c2server.py
```

The provisioning rates are normal poll seconds, fast-poll deciseconds, and
contact seconds. Open the printed admin URL (port 8080 by default), select the
provisioned alias, and use the standard v4 interface. Commands execute at the
device's next check-in. Interactive operations keep a short fast-poll lease so
acknowledged payload, keylogger, HIDX, and partition transfers do not
wait a full poll between chunks.

The device-facing C2 listener binds to all interfaces by default. The admin UI
binds only to `127.0.0.1`; set `OMG_C2_ADMIN_BIND` explicitly when a trusted
management network or authenticated TLS reverse proxy needs remote access.
`OMG_C2_BIND` continues to control only the device-facing listener.
On multi-homed servers, set `OMG_C2_PUBLIC_HOST` to the hostname or address
that provisioned cables can reach; otherwise the server uses its detected
outbound address.

The same-origin API is:

- `GET /api/v4/state` — public device/session and queue state; never returns
  host private keys or client provisioning keys.
- `POST /api/v4/command` — `{ "alias": "...", "command": "<base64>" }`.
  The optional `delivery` value is `response` or `at-most-once`; reboot-class
  commands are always forced to at-most-once delivery.
- `GET /api/v4/events?alias=...&after=<id>` — byte-exact command responses,
  base64 encoded for JSON transport.
- `POST /api/v4/queue/clear`, `/api/v4/queue/delete`, `/api/v4/device`, and
  `/api/v4/log/clear` — queue, polling-rate, and log maintenance.

Background HIDX and payload status requests are coalesced while a prior copy is
waiting for the next device check-in. This prevents a slow or disconnected
device from accumulating browser-generated polling traffic. The queue display
marks an in-flight command, supports deletion of pending items, and leaves the
in-flight command under backend ownership.

`GET /api/v4/state` advertises the complete endpoint and capability contract.
The v4 WebUI refuses to connect to a partial/legacy server that lacks
byte-exact commands, binary responses, full dispatcher coverage, durable
reboot delivery, or queue/rate management.

The C2 WebUI restricts reprovisioning and stop controls because they would
destroy the active transport. Use a direct connection for these operations.
Treat the admin port and the `c2config` file as
sensitive and expose them only on a trusted management network or behind an
authenticated TLS reverse proxy.
