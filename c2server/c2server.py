import base64
import json
import os
import secrets
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import threading
import urllib.request
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
import monocypher as mono

provisionFile_ver = 3
C2_SERVER_VERSION = "4.1.0"
SESSION_LIFESPAN = 120
serverPort = 8000
adminPort = 8080
C2_COMMAND_LIMIT = 1400
C2_MESSAGE_LIMIT = 4096
ADMIN_BODY_LIMIT = 8192
EVENT_HISTORY_LIMIT = 4096
EVENT_HISTORY_BYTES_LIMIT = 4 * 1024 * 1024
EVENT_RESPONSE_BYTES_LIMIT = 512 * 1024
C2_QUEUE_LIMIT = 256
C2_QUEUE_BYTES_LIMIT = 256 * 1024
C2_LOG_MAX_BYTES = 5 * 1024 * 1024
C2_LOG_BACKUP_COUNT = 3
C2_CONFIG_MAX_BYTES = 2 * 1024 * 1024
C2_DEVICE_LIMIT = 128
SERVER_MAX_WORKERS = 32
SERVER_REQUEST_TIMEOUT = 15
C2_SESSION_LIMIT_PER_CLIENT = 1
C2_STATE_QUEUE_PREVIEW_LIMIT = 16
DELIVERY_RESPONSE = "response"
DELIVERY_AT_MOST_ONCE = "at-most-once"
DELIVERY_MODES = (DELIVERY_RESPONSE, DELIVERY_AT_MOST_ONCE)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_c2log_lock = threading.Lock()

V4_STATUS_COMMANDS = [
    "CI", "CV", "SVStatus", "CWRead", "CWInfo", "CNGet", "CTList",
    "CFList", "PLList", "CWStatus", "FSGet", "C2Info", "C2Status",
    "CLStatus", "CHStatus", "SFInfo\thidxfile", "LGStatus", "MP\tstatus"
]
V4_API_ENDPOINTS = [
    "GET /api/v4/state",
    "GET /api/v4/events",
    "POST /api/v4/command",
    "POST /api/v4/queue/clear",
    "POST /api/v4/queue/delete",
    "POST /api/v4/device",
    "POST /api/v4/log/clear",
]


class QueueLimitError(ValueError):
    pass


class C2StorageError(RuntimeError):
    pass


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = SERVER_MAX_WORKERS

    def __init__(self, server_address, handler_class, max_workers=SERVER_MAX_WORKERS,
                 request_timeout=SERVER_REQUEST_TIMEOUT):
        self._worker_slots = threading.BoundedSemaphore(max_workers)
        self.request_timeout = request_timeout
        super().__init__(server_address, handler_class)

    def process_request(self, request, client_address):
        if not self._worker_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._worker_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            request.settimeout(self.request_timeout)
            super().process_request_thread(request, client_address)
        finally:
            self._worker_slots.release()


def command_delivery(command, requested=None):
    """Choose durable-response or at-most-once dispatch semantics."""
    if isinstance(command, str):
        command = command.encode("utf-8")
    command = bytes(command)
    body = command
    if body.startswith(b"["):
        closing = body.find(b"]", 1, 31)
        if closing >= 0:
            body = body[closing + 1:]
    # These commands reboot before firmware can acknowledge the C2 POST. They
    # must be removed durably before delivery or they will execute again after
    # the next session starts. Validation failures can still return a response.
    if body[:2].upper() in (b"CR", b"CD"):
        return DELIVERY_AT_MOST_ONCE
    if requested is None:
        return DELIVERY_RESPONSE
    if requested not in DELIVERY_MODES:
        raise ValueError("invalid command delivery mode")
    return requested


def encode_command_entry(command, delivery=None):
    """Return a JSON-safe, byte-exact queue record."""
    if isinstance(command, str):
        command = command.encode("utf-8")
    if not isinstance(command, (bytes, bytearray)):
        raise ValueError("command must be bytes")
    command = bytes(command)
    if not command or len(command) > C2_COMMAND_LIMIT:
        raise ValueError(f"command must contain 1-{C2_COMMAND_LIMIT} bytes")
    return {
        "encoding": "base64",
        "data": base64.b64encode(command).decode("ascii"),
        "delivery": command_delivery(command, delivery),
    }


def decode_command_entry(entry):
    """Read both v4 byte records and legacy string queue entries."""
    if isinstance(entry, str):
        command = entry.encode("utf-8")
    elif isinstance(entry, dict) and entry.get("encoding") == "base64":
        try:
            command = base64.b64decode(entry.get("data", ""), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid base64 command") from exc
    else:
        raise ValueError("invalid command queue entry")
    if not command or len(command) > C2_COMMAND_LIMIT:
        raise ValueError(f"command must contain 1-{C2_COMMAND_LIMIT} bytes")
    return command


def command_entry_delivery(entry):
    command = decode_command_entry(entry)
    requested = entry.get("delivery") if isinstance(entry, dict) else None
    return command_delivery(command, requested)


def command_preview(command, limit=160):
    command = bytes(command)
    text = command.decode("utf-8", errors="replace").replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "..."


def sanitize_command_queue(entries):
    """Return valid persisted entries within the runtime count/byte limits."""
    if not isinstance(entries, list):
        return []
    queue = []
    total = 0
    for entry in entries:
        try:
            command = decode_command_entry(entry)
            delivery = command_entry_delivery(entry)
        except ValueError:
            continue
        if len(queue) >= C2_QUEUE_LIMIT or total + len(command) > C2_QUEUE_BYTES_LIMIT:
            break
        queue.append(encode_command_entry(command, delivery))
        total += len(command)
    return queue


def command_queue_bytes(entries):
    total = 0
    for entry in entries:
        try:
            total += len(decode_command_entry(entry))
        except ValueError:
            continue
    return total


def _rotate_c2log(path="c2log"):
    if not os.path.exists(path) or os.path.getsize(path) < C2_LOG_MAX_BYTES:
        return
    oldest = f"{path}.{C2_LOG_BACKUP_COUNT}"
    if os.path.exists(oldest):
        os.remove(oldest)
    for index in range(C2_LOG_BACKUP_COUNT - 1, 0, -1):
        source = f"{path}.{index}"
        if os.path.exists(source):
            os.replace(source, f"{path}.{index + 1}")
    os.replace(path, f"{path}.1")

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception as e:
        print("Error occurred while getting IP address:", e)
        return None


ip_address = get_ip_address()
if ip_address:
    print("The computer's current IP address is:", ip_address)
else:
    print("Could not determine the computer's IP address.")
hostName = os.environ.get("OMG_C2_PUBLIC_HOST", "").strip() or ip_address or "127.0.0.1"
bindHost = os.environ.get("OMG_C2_BIND", "0.0.0.0").strip() or "0.0.0.0"
adminBindHost = os.environ.get("OMG_C2_ADMIN_BIND", "127.0.0.1").strip() or "127.0.0.1"


def write_c2log(alias, direction, msg):
    try:
        with _c2log_lock:
            _rotate_c2log()
            with open("c2log", "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{alias}, {timestamp}, {direction}, {msg}\n")
    except OSError as exc:
        print(f"Unable to write C2 log: {exc}", file=sys.stderr)

class c2server(BaseHTTPRequestHandler):
    # The ESP transport keeps HTTP/1.0 connections in its connecting state
    # after the encrypted hello. Use the same explicit close-delimited HTTP/1.1
    # response contract as the hardware-in-the-loop server.
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        SimpleHTTPRequestHandler.end_headers(self)

    
    def do_GET(self):
        i = self.path.find("/C2=")
        if i < 0:
            self.send_error(404)
            return
        try:
            encoded = self.path[i + 4:]
            if not encoded or len(encoded) > C2_MESSAGE_LIMIT * 2 or len(encoded) % 2:
                raise ValueError("invalid C2 message length")
            raw_msg = bytes.fromhex(encoded)
        except ValueError:
            self.send_error(400)
            return
        try:
            resp = the_host.process_message(raw_msg, len(raw_msg))
        except C2StorageError as exc:
            self.send_error(507, str(exc))
            return
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            self.send_error(400, str(exc))
            return
        body = b"" if resp is None else resp.hex().encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=ascii")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            length = -1
        if length < 47 or length > C2_MESSAGE_LIMIT:
            self.send_error(400)
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self.send_error(400)
            return
        try:
            resp = the_host.process_message(body, length)
        except C2StorageError as exc:
            self.send_error(507, str(exc))
            return
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            self.send_error(400, str(exc))
            return
        response_body = b"" if resp is None else resp.hex().encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=ascii")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        if response_body:
            self.wfile.write(response_body)


class c2admin(SimpleHTTPRequestHandler):
    """Same-origin v4 administration API and static WebUI server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store')
        SimpleHTTPRequestHandler.end_headers(self)

    def _send_json(self, status, value):
        # Close-delimited streaming avoids holding a second full encoded copy
        # of a large event/state response in every admin worker.
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        encoder = json.JSONEncoder(separators=(",", ":"), ensure_ascii=False)
        pending = bytearray()
        for piece in encoder.iterencode(value):
            pending.extend(piece.encode("utf-8"))
            if len(pending) >= 16384:
                self.wfile.write(pending)
                pending.clear()
        if pending:
            self.wfile.write(pending)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 2 or length > ADMIN_BODY_LIMIT:
            raise ValueError("invalid request size")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("incomplete request")
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def handle_C2admin(self):
        # The v2/v3 endpoint is retained, but no longer publishes the host
        # private key or per-device public provisioning material.
        self._send_json(200, the_host.admin_state())

    def handle_C2log(self, alias=None, abridge=True):
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            with _c2log_lock:
                log_file = open("c2log", "r", encoding="utf-8", errors="replace") \
                    if os.path.exists("c2log") else None
            if log_file is None:
                return
            with log_file:
                for line in log_file:
                    if alias is not None and not line.startswith(alias + ","):
                        continue
                    if abridge and re.search(r'.*, out,\s*$', line):
                        continue
                    self.wfile.write(line.encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/api/v4/state":
            self._send_json(200, the_host.admin_state())
        elif url.path == "/api/v4/events":
            alias = query.get("alias", [""])[0]
            try:
                after = max(0, int(query.get("after", ["0"])[0]))
                limit = min(512, max(1, int(query.get("limit", ["128"])[0])))
                self._send_json(200, the_host.events_after(alias, after, limit))
            except ValueError:
                self._send_json(400, {"error": "invalid event query"})
        elif url.path == "/C2admin":
            self.handle_C2admin()
        elif url.path == "/C2log":
            alias = query.get('alias', [None])[0]
            abridge = query.get('abridge', ['false'])[0].lower() in ('1', 'true', 'yes')
            self.handle_C2log(alias, abridge)
        elif url.path == "/" or url.path == "/index.html":
            self.path = "/index.html"
            super().do_GET()
        else:
            self.send_error(404)

    def _legacy_admin_action(self, body):
        alias = body.get("alias", "")
        action = body.get("action", "")
        data = body.get("data", "")
        if action == "queueAdd":
            the_host.enqueue_command(alias, str(data).encode("utf-8"))
        elif action == "queueDelete":
            the_host.delete_queued_command(alias, int(data))
        elif action == "queueClear":
            the_host.clear_queue(alias)
        elif action in ("logClear", "logClearAll"):
            target = "" if action == "logClearAll" or alias == "clearAllLogs" else alias
            the_host.clear_log(target)
            for client_alias in ([alias] if target else [c.alias for c in the_host.clients.values()]):
                for command in V4_STATUS_COMMANDS:
                    the_host.enqueue_command(client_alias, command.encode("ascii"))
        elif action == "pollInterval":
            the_host.update_rates(alias, data)
        else:
            raise ValueError("unsupported action")

    def do_POST(self):
        url = urlparse(self.path)
        try:
            body = self._read_json()
            if url.path == "/api/v4/command":
                alias = body.get("alias", "")
                encoded = body.get("command", "")
                try:
                    command = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError) as exc:
                    raise ValueError("invalid command encoding") from exc
                queued = the_host.enqueue_command(alias, command, body.get("delivery"))
                self._send_json(202, queued)
            elif url.path == "/api/v4/queue/clear":
                self._send_json(200, the_host.clear_queue(body.get("alias", "")))
            elif url.path == "/api/v4/queue/delete":
                self._send_json(200, the_host.delete_queued_command(
                    body.get("alias", ""), int(body.get("index", -1))))
            elif url.path == "/api/v4/device":
                self._send_json(200, the_host.update_rates(body.get("alias", ""), body.get("rates", {})))
            elif url.path == "/api/v4/log/clear":
                self._send_json(200, the_host.clear_log(body.get("alias", "")))
            elif url.path == "/C2admin":
                self._legacy_admin_action(body)
                self._send_json(200, {"ok": True})
            else:
                self.send_error(404)
        except QueueLimitError as exc:
            self._send_json(429, {"error": str(exc)})
        except C2StorageError as exc:
            self._send_json(507, {"error": str(exc)})
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            self._send_json(400, {"error": str(exc)})


class Host:
    class ClientData:
        def __init__(self, client_id, alias, client_exchange_key, cmd_queue):
            self.client_id = client_id
            self.alias = alias
            self.exchange_key = client_exchange_key
            self.cmd_queue = sanitize_command_queue(cmd_queue)
            self.last_seen = 0
            self.last_response = 0
            self.fast_until = 0

    class SessionData:
        def __init__(self, session_id, session_key, client_id, device_id, expires, interface_version):
            self.session_id = session_id
            self.session_key = session_key
            self.client_id = client_id
            self.device_id = device_id
            self.expires = expires
            self.ver = interface_version
            self.msg_count = 0
            self.next_cmd = 0
            self.pending_seq = None
            self.pending_entry = None
            self.pending_delivery = DELIVERY_RESPONSE
            self.completed_seq = None

    def __init__(self, host_private_key, host_public_key, server_config=None):
        self.host_private_key = bytes.fromhex(host_private_key) if host_private_key else None
        self.public_key = bytes.fromhex(host_public_key) if host_public_key else None
        self.session_lifespan = SESSION_LIFESPAN
        self.clients = {}
        self.sessions = {}
        self.session_count = 0
        self.lock = threading.RLock()
        self.persistence_lock = threading.Lock()
        self.events = []
        self._event_bytes = 0
        self.next_event_id = 1
        self.config = server_config if server_config is not None else globals().get("config")

        for device in (self.config.devices if self.config is not None else []):
            client_id = device['client_id']
            alias = device['alias']
            client_public_key = bytes.fromhex(device['client_public_key'])
            client_exchange_key = mono.key_exchange(self.host_private_key, client_public_key)
            cmd_queue = device.get('cmd_queue', None)
            client = self.ClientData(client_id, alias, client_exchange_key, cmd_queue)
            self.clients[client_id] = client

    def _client_for_alias(self, alias):
        if not isinstance(alias, str) or not alias:
            raise ValueError("device alias required")
        for client in self.clients.values():
            if client.alias == alias:
                return client
        raise ValueError("unknown device alias")

    def _session_for_client(self, client_id):
        with self.lock:
            self._prune_sessions_locked()
            sessions = [s for s in self.sessions.values() if s.client_id == client_id]
            return max(sessions, key=lambda s: s.expires) if sessions else None

    def _prune_sessions_locked(self, now=None):
        now = int(time.time()) if now is None else now
        expired = [session_id for session_id, session in self.sessions.items()
                   if session.expires < now and
                   (session.pending_seq is None or
                    session.pending_delivery == DELIVERY_AT_MOST_ONCE)]
        for session_id in expired:
            self.sessions.pop(session_id, None)

    @staticmethod
    def _event_storage_size(event):
        return (len(event.get("data", "")) + len(event.get("alias", "")) +
                len(event.get("direction", "")) + len(event.get("time", "")) + 96)

    def _config_snapshot_locked(self, queue_overrides=None):
        queue_overrides = queue_overrides or {}
        devices = []
        for device in self.config.devices:
            saved = device.copy()
            client = self.clients.get(device.get("client_id"))
            client_id = device.get("client_id")
            if client_id in queue_overrides:
                saved["cmd_queue"] = list(queue_overrides[client_id])
            else:
                saved["cmd_queue"] = list(client.cmd_queue if client is not None
                                          else device.get("cmd_queue", []))
            devices.append(saved)
        return {
            "host_public_key": self.config.host_public_key,
            "host_private_key": self.config.host_private_key,
            "host_url": getattr(self.config, "host_url", "127.0.0.1"),
            "host_port": getattr(self.config, "host_port", serverPort),
            "admin_port": getattr(self.config, "admin_port", adminPort),
            "devices": devices,
        }

    def _save_snapshot(self, snapshot):
        self.config.save_provision_files(snapshot)

    def _append_event(self, client, direction, raw):
        raw = bytes(raw)
        event = {
            "id": self.next_event_id,
            "alias": client.alias,
            "time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "direction": direction,
            "size": len(raw),
            "data": base64.b64encode(raw).decode("ascii")
        }
        self.next_event_id += 1
        self.events.append(event)
        self._event_bytes += self._event_storage_size(event)
        while (len(self.events) > EVENT_HISTORY_LIMIT or
               self._event_bytes > EVENT_HISTORY_BYTES_LIMIT):
            removed = self.events.pop(0)
            self._event_bytes -= self._event_storage_size(removed)
        return event

    def enqueue_command(self, alias, command, delivery=None):
        entry = encode_command_entry(command, delivery)
        entry_size = len(decode_command_entry(entry))
        with self.persistence_lock:
            with self.lock:
                client = self._client_for_alias(alias)
                if len(client.cmd_queue) >= C2_QUEUE_LIMIT:
                    raise QueueLimitError("device command queue is full")
                if command_queue_bytes(client.cmd_queue) + entry_size > C2_QUEUE_BYTES_LIMIT:
                    raise QueueLimitError("device command queue byte limit exceeded")
                candidate_queue = list(client.cmd_queue)
                candidate_queue.append(entry)
                position = len(candidate_queue)
                snapshot = self._config_snapshot_locked({client.client_id: candidate_queue})
            # Persist the prospective queue before publishing it to device poll
            # handlers. A failed fsync can therefore never produce a command
            # that the API rejected but a device already executed.
            self._save_snapshot(snapshot)
            with self.lock:
                client.cmd_queue.append(entry)
                # Keep the device on its fast-poll cadence while the interactive
                # WebUI performs acknowledged multi-command operations. Without
                # this lease, each sequential transfer chunk waits a full poll.
                client.fast_until = max(client.fast_until, time.time() + 30)
            return {"queued": True, "position": position, "size": entry_size,
                    "delivery": command_entry_delivery(entry)}

    def delete_queued_command(self, alias, index):
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("valid queue index required")
        with self.persistence_lock:
            with self.lock:
                client = self._client_for_alias(alias)
                if index >= len(client.cmd_queue):
                    raise ValueError("queue index out of range")
                session = self._session_for_client(client.client_id)
                if session and session.pending_entry is not None and index == 0:
                    raise ValueError("cannot delete an in-flight command")
                candidate_queue = list(client.cmd_queue)
                candidate_queue.pop(index)
                queued = len(candidate_queue)
                snapshot = self._config_snapshot_locked({client.client_id: candidate_queue})
            self._save_snapshot(snapshot)
            with self.lock:
                client.cmd_queue = candidate_queue
            return {"deleted": True, "queued": queued}

    def clear_queue(self, alias):
        with self.persistence_lock:
            with self.lock:
                client = self._client_for_alias(alias)
                session = self._session_for_client(client.client_id)
                if session and session.pending_entry is not None and client.cmd_queue:
                    candidate_queue = client.cmd_queue[:1]
                else:
                    candidate_queue = []
                queued = len(candidate_queue)
                snapshot = self._config_snapshot_locked({client.client_id: candidate_queue})
            self._save_snapshot(snapshot)
            with self.lock:
                client.cmd_queue = candidate_queue
            return {"cleared": True, "queued": queued}

    def clear_log(self, alias=""):
        with self.lock:
            if alias:
                self._client_for_alias(alias)
                self.events = [event for event in self.events if event["alias"] != alias]
            else:
                self.events = []
            self._event_bytes = sum(self._event_storage_size(event) for event in self.events)
            event_cursor = self.next_event_id - 1
        paths = ["c2log"] + [f"c2log.{index}" for index in range(1, C2_LOG_BACKUP_COUNT + 1)]
        temporary = None
        try:
            with _c2log_lock:
                for path in paths:
                    if path != "c2log" and not os.path.exists(path):
                        continue
                    temporary = f"{path}.tmp"
                    with open(temporary, "w", encoding="utf-8") as output:
                        if alias and os.path.exists(path):
                            with open(path, "r", encoding="utf-8", errors="replace") as source:
                                for line in source:
                                    if not line.startswith(alias + ","):
                                        output.write(line)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(temporary, path)
                    temporary = None
        except OSError as exc:
            if temporary:
                try:
                    os.remove(temporary)
                except OSError:
                    pass
            raise C2StorageError(f"unable to clear C2 log: {exc}") from exc
        return {"cleared": True, "event_cursor": event_cursor}

    def update_rates(self, alias, rates):
        if not isinstance(rates, dict):
            raise ValueError("rates object required")
        with self.persistence_lock:
            with self.lock:
                self._client_for_alias(alias)
                device = next((item for item in self.config.devices if item.get("alias") == alias), None)
                if device is None:
                    raise ValueError("unknown device alias")
                original = {key: device.get(key) for key in
                            ("poll_seconds", "fast_seconds", "contact_seconds")}
                updated = dict(original)
                for key in original:
                    if key in rates:
                        value = rates[key]
                        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 86400:
                            raise ValueError("rates must be whole numbers between 1 and 86400")
                        updated[key] = value
                device.update(updated)
                snapshot = self._config_snapshot_locked()
            try:
                self._save_snapshot(snapshot)
            except C2StorageError:
                with self.lock:
                    device.update(original)
                raise
            return {"updated": True, "rates": updated}

    def events_after(self, alias, after, limit):
        with self.lock:
            if alias:
                self._client_for_alias(alias)
            events = []
            response_bytes = 64
            for event in self.events:
                if event["id"] <= after or (alias and event["alias"] != alias):
                    continue
                event_bytes = self._event_storage_size(event)
                if events and response_bytes + event_bytes > EVENT_RESPONSE_BYTES_LIMIT:
                    break
                events.append(event)
                response_bytes += event_bytes
                if len(events) >= limit:
                    break
            cursor = events[-1]["id"] if events else self.next_event_id - 1
            return {"events": events, "cursor": cursor,
                    "latest": self.next_event_id - 1}

    def admin_state(self):
        with self.lock:
            now = int(time.time())
            devices = []
            for device in self.config.devices:
                client = self.clients.get(device.get("client_id"))
                if client is None:
                    continue
                session = self._session_for_client(client.client_id)
                queue = []
                for index, entry in enumerate(client.cmd_queue[:C2_STATE_QUEUE_PREVIEW_LIMIT]):
                    try:
                        command = decode_command_entry(entry)
                        queue.append({"index": index, "size": len(command),
                                      "delivery": command_entry_delivery(entry),
                                      "in_flight": bool(session and index == 0 and
                                                        session.pending_entry is entry),
                                      "preview": command_preview(command)})
                    except ValueError:
                        queue.append({"index": index, "size": 0, "preview": "[invalid entry]"})
                devices.append({
                    "alias": client.alias,
                    "client_id": client.client_id,
                    "protocol": session.ver if session else None,
                    "session_id": session.session_id if session else None,
                    "online": bool(session and session.expires >= now),
                    "session_expires_in": max(0, session.expires - now) if session else 0,
                    "last_seen": client.last_seen or None,
                    "last_response": client.last_response or None,
                    "poll_seconds": int(device.get("poll_seconds", SESSION_LIFESPAN)),
                    "fast_seconds": int(device.get("fast_seconds", 1)),
                    "contact_seconds": int(device.get("contact_seconds", SESSION_LIFESPAN)),
                    "queue_count": len(client.cmd_queue),
                    "queue_truncated": len(client.cmd_queue) > len(queue),
                    "interactive": client.fast_until > time.time(),
                    "cmd_queue": queue
                })
            return {
                "api_version": 4,
                "server_version": C2_SERVER_VERSION,
                "c2_protocol": provisionFile_ver,
                "command_limit": C2_COMMAND_LIMIT,
                "backend_contract": {
                    "authority": "device",
                    "api_generation": 4,
                    "c2_wire_version": provisionFile_ver,
                    "command_limit": C2_COMMAND_LIMIT,
                    "service_status": "SVStatus",
                    "service_preflight": "SVPreflight",
                    "hidx_status": "CHStatus",
                },
                "delivery_modes": list(DELIVERY_MODES),
                "capabilities": {
                    "byte_exact_commands": True,
                    "binary_responses": True,
                    "full_v4_dispatch": True,
                    "at_most_once_reboot": True,
                    "queue_management": True,
                    "poll_rate_management": True,
                    "authoritative_backend_state": True,
                    "coalesced_background_polling": True,
                    "queue_item_deletion": True,
                    "server_log_clear": True,
                },
                "api_endpoints": list(V4_API_ENDPOINTS),
                "safety_restrictions": ["c2_provisioning_mutation"],
                "event_cursor": self.next_event_id - 1,
                "devices": devices
            }

    def provision(self, alias, poll_seconds, fast_seconds, contact_seconds):
        with self.persistence_lock:
            with self.lock:
                if len(self.config.devices) >= C2_DEVICE_LIMIT:
                    raise ValueError(f"device limit of {C2_DEVICE_LIMIT} reached")
                for device in self.config.devices:
                    if device['alias'] == alias:
                        print(f"Warning: Existing Device Alias {alias} already exists. Provisioning did not continue.")
                        return

                self.session_count += 1
                client_id = secrets.randbelow(0x100000000)
                while client_id in self.clients:
                    client_id = secrets.randbelow(0x100000000)
                client_secret_key = gen_random(32)
                client_public_key = mono.compute_key_exchange_public_key(client_secret_key)
                client_exchange_key = mono.key_exchange(self.host_private_key, client_public_key)
                client = self.ClientData(client_id, alias, client_exchange_key, None)
                self.clients[client_id] = client

                provision_data = {
                    'alias': alias,
                    'client_id': client_id,
                    'client_public_key': client_public_key.hex(),
                    'poll_seconds': poll_seconds,
                    'fast_seconds': fast_seconds,
                    'contact_seconds': contact_seconds
                }

                self.config.devices.append(provision_data)
                snapshot = self._config_snapshot_locked()
            try:
                self._save_snapshot(snapshot)
            except C2StorageError:
                with self.lock:
                    self.clients.pop(client_id, None)
                    self.config.devices.remove(provision_data)
                raise

        log("Provisioned  [{}]   alias: {}".format(client_id, alias))

        print(f"---------- Provision-file: {alias} ----------")
        device_config = f"host_pk = {self.public_key.hex()},host_url = {self.config.host_url},host_port = {self.config.host_port},host_path = \"\",client_id = {client_id},client_sk = {client_secret_key.hex()},poll_rate = {poll_seconds},fast_rate = {fast_seconds},contact_rate = {contact_seconds}"
        print(device_config)
        print('\n\nCopy the Provision-file into Settings -> Net -> C2 Config on a C2-capable O.MG device, then apply it.')
    def make_err_msg(self, err_code, err_text, msg_id=0):
        print("***** Sending Error ", err_code, err_text)
        wrapper = MsgWrapper(109, err_code)
        wrapper.id = msg_id
        return wrapper.secure_msg()

    def handle_hello(self, hello_msg, client):
        print("<<<<< Hello Msg >>>>>")
        client_id = client.client_id
        device_id = hello_msg.plain_msg[4:10]
        ver = 1
        if hello_msg.msg_size > 10:
            ver = int.from_bytes(hello_msg.plain_msg[10:11], 'little')
    
        with self.lock:
            self._prune_sessions_locked()
            # Provisioning credentials identify one physical client. Replace
            # every older session for that client so two reconnecting transports
            # can never receive the same queue head concurrently.
            old_sessions = [key for key, session in self.sessions.items()
                            if session.client_id == client_id]
            for old_session in old_sessions:
                del self.sessions[old_session]

            session_key = gen_random(32)
            session_id = secrets.randbelow(0xffffffff) + 1
            while session_id in self.sessions:
                session_id = secrets.randbelow(0xffffffff) + 1
            expires = int(time.time()) + self.session_lifespan + 5
            self.sessions[session_id] = self.SessionData(
                session_id, session_key, client_id, device_id, expires, ver)
            client_sessions = sorted(
                (session for session in self.sessions.values()
                 if session.client_id == client_id),
                key=lambda session: session.expires,
                reverse=True)
            for stale in client_sessions[C2_SESSION_LIMIT_PER_CLIENT:]:
                self.sessions.pop(stale.session_id, None)
            client.last_seen = int(time.time())
        print(f"Session id: {session_id}, ver: {ver}")
    
        # Fetch the per-device values from the c2config device entry with the matching client_id
        matching_device = next((device for device in self.config.devices if device["client_id"] == client.client_id), None)
        if matching_device is not None:
            poll_seconds = matching_device.get("poll_seconds", self.session_lifespan)
            fast_seconds = matching_device.get("fast_seconds", self.session_lifespan)
            contact_seconds = matching_device.get("contact_seconds", poll_seconds)
        else:
            poll_seconds = fast_seconds = contact_seconds = self.session_lifespan
        
        
        plain_resp = HelloResponse(session_id, session_key, self.session_lifespan, poll_seconds, fast_seconds, contact_seconds)
        resp = MsgWrapper(101, plain_resp.text, len(plain_resp.text))
        # Firmware requires every response envelope to echo the request id:
        # client id during hello, then session id for later messages.
        resp.id = getattr(hello_msg, 'id', client_id)
        resp.encrypt(client.exchange_key)
        wrapped_msg = resp.secure_msg()
        print("   secure msg: ", wrapped_msg.hex())
        return wrapped_msg

    def handle_poll(self, poll_msg, session):
        seq_no = int.from_bytes(poll_msg.plain_msg[4:8], 'little')
        script_status = int.from_bytes(poll_msg.plain_msg[8:9], 'little')
        print(f"<<<<< Poll Msg #{seq_no} - SS: {script_status}>>>>>")

        with self.persistence_lock:
            queue_changed = False
            candidate_queue = None
            snapshot = None
            delivery = DELIVERY_RESPONSE
            with self.lock:
                client = self.clients[session.client_id]
                client.last_seen = int(time.time())
                entry = client.cmd_queue[0] if client.cmd_queue else None
                try:
                    if entry is None:
                        cmd = b""
                    else:
                        cmd = decode_command_entry(entry)
                        delivery = command_entry_delivery(entry)
                except ValueError:
                    # Persist removal before publishing it, just like every
                    # other command-queue mutation.
                    candidate_queue = list(client.cmd_queue)
                    candidate_queue.pop(0)
                    snapshot = self._config_snapshot_locked({client.client_id: candidate_queue})
                    queue_changed = True
                    cmd = b""
                    entry = None

            if queue_changed:
                try:
                    self._save_snapshot(snapshot)
                except C2StorageError as exc:
                    print(f"Unable to persist sanitized command queue: {exc}", file=sys.stderr)
                else:
                    with self.lock:
                        client.cmd_queue = candidate_queue

            with self.lock:
                if cmd.startswith(b"CE") and not cmd.startswith(b"CEStatus"):
                    if session.ver > 1 and script_status != 0:
                        cmd = b""
                        entry = None

                if cmd and delivery == DELIVERY_AT_MOST_ONCE:
                    candidate_queue = list(client.cmd_queue[1:])
                    snapshot = self._config_snapshot_locked({client.client_id: candidate_queue})

            if cmd and delivery == DELIVERY_AT_MOST_ONCE:
                # Reboot-class commands cannot acknowledge success. Commit the
                # removal before placing the command on the wire so a reconnect
                # can never replay a destructive operation.
                self._save_snapshot(snapshot)
                with self.lock:
                    if not client.cmd_queue or client.cmd_queue[0] is not entry:
                        raise ValueError("C2 queue changed before at-most-once delivery")
                    client.cmd_queue = candidate_queue

            with self.lock:
                queued_after_current = (len(client.cmd_queue) > 1
                                        if delivery == DELIVERY_RESPONSE
                                        else len(client.cmd_queue) > 0)
                is_more = 1 if ((cmd and queued_after_current) or
                               client.fast_until > time.time()) else 0
                session.pending_seq = seq_no if cmd else None
                session.pending_entry = (entry if cmd and delivery == DELIVERY_RESPONSE
                                         else None)
                session.pending_delivery = delivery if cmd else DELIVERY_RESPONSE

        if len(cmd):
            print(f">>>>> Running command {command_preview(cmd)}")
        else:
            print(">>>>> Idle  (No command sent)")

        msg = CommandMsg(seq_no, cmd, is_more)
        resp = MsgWrapper(102, msg.text, len(msg.text))
        resp.id = getattr(poll_msg, 'id', session.session_id)
        resp.encrypt(session.session_key)
        wrapped_msg = resp.secure_msg()

        if cmd:
            with self.lock:
                self._append_event(client, "command", cmd)
            write_c2log(client.alias, "out", command_preview(cmd, 1000))

        return wrapped_msg

    def handle_response(self, command_response, session):
        seq_no = int.from_bytes(command_response.plain_msg[0:4], 'little')
        resp_size = int.from_bytes(command_response.plain_msg[4:6], 'little')
        cmd_offset = 7
        if len(command_response.plain_msg) < cmd_offset or resp_size != len(command_response.plain_msg[cmd_offset:]):
            raise ValueError("Malformed C2 command response")
        raw_response = bytes(command_response.plain_msg[7:])
        response = command_preview(raw_response, 1000)
        
        print(f"<<<<< Output for #{seq_no} >>>>>   size: {resp_size} ({len(command_response.plain_msg[7:])})")
        print(response)
        
        log_alias = None
        with self.persistence_lock:
            with self.lock:
                client = self.clients[session.client_id]
                if session.pending_seq is None:
                    if session.completed_seq == seq_no:
                        return None
                    raise ValueError("Unexpected C2 command response sequence")
                if seq_no != session.pending_seq:
                    raise ValueError("Unexpected C2 command response sequence")
                if session.pending_delivery == DELIVERY_AT_MOST_ONCE:
                    client.last_response = client.last_seen = int(time.time())
                    self._append_event(client, "response", raw_response)
                    session.pending_seq = None
                    session.pending_entry = None
                    session.pending_delivery = DELIVERY_RESPONSE
                    session.completed_seq = seq_no
                    log_alias = client.alias
                else:
                    # An in-flight response owns the queue head. Keep its session
                    # key available across temporary network/storage outages.
                    session.expires = int(time.time()) + self.session_lifespan + 5
                    if (not client.cmd_queue or session.pending_entry is None or
                            client.cmd_queue[0] is not session.pending_entry):
                        raise ValueError("C2 queue changed before command response")
                    candidate_queue = client.cmd_queue[1:]
                    snapshot = self._config_snapshot_locked({client.client_id: candidate_queue})
            if log_alias is None:
                # The HTTP acknowledgement is sent only after the queue removal is
                # durable. Firmware retries this same response if saving fails.
                self._save_snapshot(snapshot)
                with self.lock:
                    if (session.pending_seq != seq_no or not client.cmd_queue or
                            client.cmd_queue[0] is not session.pending_entry):
                        raise ValueError("C2 queue changed before command response commit")
                    client.cmd_queue = candidate_queue
                    client.last_response = client.last_seen = int(time.time())
                    self._append_event(client, "response", raw_response)
                    session.pending_seq = None
                    session.pending_entry = None
                    session.pending_delivery = DELIVERY_RESPONSE
                    session.completed_seq = seq_no
                    log_alias = client.alias
        write_c2log(log_alias, "in ", response)

    def handle_error(self, err_msg, session):
        client = self.clients.get(session.client_id)
        message = "Device error code: {}".format(err_msg.err_code)
        log(message)
        if client is not None:
            with self.lock:
                self._append_event(client, "error", message.encode("utf-8"))

    def process_message(self, raw_msg, raw_len):
        request_id = int.from_bytes(raw_msg[1:5], 'little') if raw_len >= 5 else 0
        if raw_len != len(raw_msg) or raw_len < 47 or raw_len > C2_MESSAGE_LIMIT:
            return self.make_err_msg(101, "Bad message length", request_id)

        msg_type = raw_msg[0]
        declared_size = int.from_bytes(raw_msg[45:47], 'little')
        if msg_type not in (9, 109) and raw_len != 47 + declared_size:
            return self.make_err_msg(101, "Bad message length", request_id)
        if msg_type in (9, 109) and raw_len != 47:
            return self.make_err_msg(101, "Bad error message length", request_id)

        msg = MsgWrapper(raw_msg)

        if msg.msg_type == 1:
            if msg.id not in self.clients:
                return self.make_err_msg(102, "Unknown client-id", msg.id)
            client = self.clients[msg.id]
            key = client.exchange_key
        else:
            with self.lock:
                session = self.sessions.get(msg.id)
                if (session is not None and session.expires < int(time.time()) and
                        not (msg_type == 3 and session.pending_seq is not None and
                             session.pending_delivery == DELIVERY_RESPONSE)):
                    self.sessions.pop(msg.id, None)
                    self._prune_sessions_locked()
                    return self.make_err_msg(104, "Session has expired", msg.id)
                self._prune_sessions_locked()
            if session is None:
                return self.make_err_msg(103, "Unknown session-id", msg.id)
            key = session.session_key

        if not msg.decrypt(key):
            return self.make_err_msg(105, "Invalid encryption", msg.id)

        if msg.msg_type == 1:
            return self.handle_hello(msg, client)
        if msg.msg_type == 2:
            return self.handle_poll(msg, session)
        elif msg.msg_type == 3:
            return self.handle_response(msg, session)
        elif msg.msg_type == 9:
            return self.handle_error(msg, session)

        return self.make_err_msg(106, "Unknown message-type", msg.id)


class HelloResponse:
    def __init__(self, session_id, session_key, expiry, poll_seconds, fast_seconds, contact_seconds):
        self.text = bytearray()
        self.text.extend(session_id.to_bytes(4, 'little'))
        self.text.extend(expiry.to_bytes(4, 'little'))
        self.text.extend(session_key)
        self.text.extend(poll_seconds.to_bytes(4, 'little'))
        self.text.extend(fast_seconds.to_bytes(4, 'little'))
        self.text.extend(contact_seconds.to_bytes(4, 'little'))

class CommandMsg:
    def __init__(self, seq, command, is_more):
        cmd_len = len(command)
        self.text = bytearray()
        self.text.extend(seq.to_bytes(4, 'little'))
        self.text.extend(cmd_len.to_bytes(2, 'little'))
        self.text.extend(is_more.to_bytes(1, 'little'))
        self.text.extend(command)
        print("   is_more: ", is_more)


class MsgWrapper:
    def __init__(self, *args):
        if len(args) == 1:
            msg = args[0]
            self.msg_type = msg[0]
            self.id = int.from_bytes(msg[1:5], 'little')
            self.nonce = msg[5:29]
            self.mac = msg[29:45]
            if self.msg_type != 9:
                self.msg_size = int.from_bytes(msg[45:47], 'little')
                self.err_code = 0
            else:
                self.err_code = int.from_bytes(msg[45:47], 'little')
                self.msg_size = 0
            self.encoded = msg[47:47 + self.msg_size]
            self.plain_msg = None
        else:
            self.msg_type = args[0]
            self.id = 0
            self.nonce = None
            self.mac = None
            self.encoded = None
            if len(args) == 2:
                self.err_code = args[1]
                self.msg_size = 0
            else:
                self.plain_msg = args[1]
                self.msg_size = args[2]
                self.err_code = 0

    def encrypt(self, key):
        if self.msg_type == 109:
            return

        self.nonce = gen_random(24)
        self.mac, self.encoded = mono.lock(key, self.nonce, self.plain_msg)

    def decrypt(self, key):
        if self.msg_type == 9:
            return True

        self.plain_msg = mono.unlock(key, self.nonce, self.mac, self.encoded)
        if self.plain_msg is None:
            print("   Decrypt failed")
            return False
        return True

    def secure_msg(self):
        msg = bytearray()
        msg.extend(self.msg_type.to_bytes(1, 'little'))
        msg.extend(self.id.to_bytes(4, 'little'))
        if self.msg_type == 9 or self.msg_type == 109:
            msg.extend(bytearray(40))
            msg.extend(self.err_code.to_bytes(2, 'little'))
        else:
            msg.extend(self.nonce)
            msg.extend(self.mac)
            msg.extend(self.msg_size.to_bytes(2, 'little'))
            msg.extend(self.encoded)
        return msg


def log(err_text):
    print("<LOG> ", err_text)


def gen_random(size):
    return secrets.token_bytes(size)


class c2config:
    def __init__(self, host_public_key, host_private_key, host_url, host_port, admin_port):
        self._save_lock = threading.Lock()
        self.host_public_key = host_public_key
        self.host_private_key = host_private_key
        self.host_url = host_url or "127.0.0.1"
        self.host_port = host_port
        self.admin_port = admin_port
        self.devices = []

        if os.path.exists("c2config"):
            try:
                self.load_provision_files()
                return
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                backup_base = f"c2config.invalid-{int(time.time())}"
                backup = backup_base
                suffix = 1
                while os.path.exists(backup):
                    backup = f"{backup_base}.{suffix}"
                    suffix += 1
                try:
                    os.replace("c2config", backup)
                except OSError as backup_exc:
                    raise C2StorageError(
                        f"invalid c2config ({exc}); unable to preserve it: {backup_exc}") from backup_exc
                print(f"Invalid c2config preserved as {backup}: {exc}", file=sys.stderr)
        else:
            print("No c2config file exists.")
            print('You must provision an O.MG Elite Device before you can use.\n\nEach device provision requires 4 arguments: (alias, poll_seconds, fast_seconds, contact_seconds).\n')
        self._initialize_new_config()

    def _initialize_new_config(self):
        self.devices = []
        self.host_private_key = gen_random(32).hex()
        self.host_public_key = mono.compute_key_exchange_public_key(
            bytes.fromhex(self.host_private_key)).hex()
        self.save_provision_files()

    @staticmethod
    def _hex_key(value, name):
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{name} must be a 32-byte hexadecimal key")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be hexadecimal") from exc
        return value

    @classmethod
    def _validate_config_data(cls, data):
        if not isinstance(data, dict):
            raise ValueError("c2config must contain a JSON object")
        private_key = cls._hex_key(data["host_private_key"], "host_private_key")
        public_key = cls._hex_key(data["host_public_key"], "host_public_key")
        host_url = data["host_url"]
        if not isinstance(host_url, str) or not host_url or len(host_url) > 255:
            raise ValueError("host_url must be a non-empty hostname or address")
        ports = []
        for name in ("host_port", "admin_port"):
            value = data[name]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 65535:
                raise ValueError(f"{name} must be a port between 1 and 65535")
            ports.append(value)
        raw_devices = data["devices"]
        if not isinstance(raw_devices, list) or len(raw_devices) > C2_DEVICE_LIMIT:
            raise ValueError(f"devices must be a list of at most {C2_DEVICE_LIMIT} entries")
        aliases = set()
        client_ids = set()
        devices = []
        for raw_device in raw_devices:
            if not isinstance(raw_device, dict):
                raise ValueError("each device must be a JSON object")
            alias = raw_device.get("alias")
            client_id = raw_device.get("client_id")
            if not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", alias):
                raise ValueError("device alias is invalid")
            if (isinstance(client_id, bool) or not isinstance(client_id, int) or
                    client_id < 0 or client_id > 0xffffffff):
                raise ValueError("device client_id is invalid")
            if alias in aliases or client_id in client_ids:
                raise ValueError("device aliases and client IDs must be unique")
            cls._hex_key(raw_device.get("client_public_key"), "client_public_key")
            device = raw_device.copy()
            for rate_name in ("poll_seconds", "fast_seconds", "contact_seconds"):
                rate = device.get(rate_name, SESSION_LIFESPAN)
                if isinstance(rate, bool) or not isinstance(rate, int) or rate < 1 or rate > 86400:
                    raise ValueError(f"device {rate_name} is invalid")
                device[rate_name] = rate
            device["cmd_queue"] = sanitize_command_queue(raw_device.get("cmd_queue", []))
            devices.append(device)
            aliases.add(alias)
            client_ids.add(client_id)
        return public_key, private_key, host_url, ports[0], ports[1], devices

    def save_provision_files(self, config_data=None):
        if config_data is None:
            devices_with_cmd_queue = []
            host = globals().get("the_host")
            for device in self.devices:
                saved = device.copy()
                client = host.clients.get(device['client_id']) if host is not None else None
                saved['cmd_queue'] = list(client.cmd_queue if client is not None
                                         else device.get('cmd_queue', []))
                devices_with_cmd_queue.append(saved)
            config_data = {
                'host_public_key': self.host_public_key,
                'host_private_key': self.host_private_key,
                'host_url': self.host_url,
                'host_port': self.host_port,
                'admin_port': self.admin_port,
                'devices': devices_with_cmd_queue
            }

        temporary = "c2config.tmp"
        with self._save_lock:
            try:
                with open(temporary, 'w', encoding="utf-8") as f:
                    json.dump(config_data, f, indent=4)
                    if f.tell() > C2_CONFIG_MAX_BYTES:
                        raise C2StorageError("c2config exceeds the size limit")
                    f.flush()
                    os.fsync(f.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, "c2config")
            except C2StorageError:
                try:
                    os.remove(temporary)
                except OSError:
                    pass
                raise
            except (OSError, TypeError, ValueError) as exc:
                try:
                    os.remove(temporary)
                except OSError:
                    pass
                raise C2StorageError(f"unable to save c2config: {exc}") from exc

    def load_provision_files(self):
        size = os.path.getsize("c2config")
        if size == 0 or size > C2_CONFIG_MAX_BYTES:
            raise ValueError("c2config is empty or exceeds the size limit")
        with open("c2config", 'r', encoding="utf-8") as f:
            values = self._validate_config_data(json.load(f))
        (self.host_public_key, self.host_private_key, self.host_url,
         self.host_port, self.admin_port, self.devices) = values

def validate_arguments(argv):
            if (len(argv) - 2) % 4 != 0:
                return False, "\nERROR: Incorrect number of arguments.\nEach device provision requires 4 arguments: (alias, poll_seconds, fast_seconds, contact_seconds).\n"
            try:
                for i in range(2, len(argv), 4):
                    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", argv[i]):
                        return False, "ERROR: Alias must contain 1-64 letters, numbers, dots, underscores, or hyphens.\n"
                    rates = [int(argv[i + 1]), int(argv[i + 2]), int(argv[i + 3])]
                    if any(value < 1 or value > 86400 for value in rates):
                        return False, "ERROR: Polling rates must be between 1 and 86400.\n"
            except ValueError:
                return False, "ERROR: Expected integer values for poll_seconds, fast_seconds, and contact_seconds.\n"
            return True, ""


webServer = None
secondaryServer = None

if __name__ == "__main__":
    config = c2config(None, None, hostName, serverPort, adminPort)
    the_host = Host(config.host_private_key, config.host_public_key, config)

    if len(sys.argv) > 1 and sys.argv[1].lower() == 'provision':
        valid, error_msg = validate_arguments(sys.argv)
        if not valid:
            print(error_msg)
            print("Example usage: python3 ./c2server.py provision cableOne 60 1 300\nExample usage: python3 ./c2server.py provision cableOne 60 1 300 cableTwo 120 1 600")
        else:
            index = 2
            while index < len(sys.argv):
                try:
                    alias = sys.argv[index]
                    poll_seconds = int(sys.argv[index + 1])
                    fast_seconds = int(sys.argv[index + 2])
                    contact_seconds = int(sys.argv[index + 3])
                    the_host.provision(alias, poll_seconds, fast_seconds, contact_seconds)
                    index += 4
                except (IndexError, ValueError):
                    print("Invalid arguments for provisioning. Expected sets of (alias, poll_seconds, fast_seconds, contact_seconds).")
    else:
        try:
            secondaryServer = BoundedThreadingHTTPServer((adminBindHost, config.admin_port), c2admin)
            secondaryThread = threading.Thread(target=secondaryServer.serve_forever)
            secondaryThread.daemon = True
            secondaryThread.start()
            print("AdminUI server started http://%s:%s (bound to %s)" %
                  (hostName if adminBindHost not in ("127.0.0.1", "::1") else adminBindHost,
                   config.admin_port, adminBindHost))
        except OSError as e:
            print("Failed to start the AdminUI server.")
            print(e);
            if 'Address already in use' in str(e):
                print(f"Port {config.admin_port} is already in use. Please choose a different port in your c2config.")
            elif 'Can\'t assign requested address' in str(e):
                print(f"Cannot assign requested address: {adminBindHost}. Please check OMG_C2_ADMIN_BIND.")
            sys.exit(1)

        try:
            webServer = BoundedThreadingHTTPServer((bindHost, config.host_port), c2server)
            print("C2 server started http://%s:%s (bound to %s)" %
                  (hostName, config.host_port, bindHost))
            with webServer:
                webServer.serve_forever()
        except KeyboardInterrupt:
            print("Server stopped.")
        except OSError as e:
            print(e);
            print("Failed to start the C2 server.")
            if 'Address already in use' in str(e):
                print(f"Port {config.host_port} is already in use. Please choose a different port in your c2config.")
            elif 'Can\'t assign requested address' in str(e):
                print(f"Cannot assign requested address: {bindHost}. Please check OMG_C2_BIND.")
            sys.exit(1)
        finally:
            if webServer is not None:
                webServer.server_close()
                print("Server stopped.")
            if secondaryServer is not None:
                secondaryServer.shutdown()
                secondaryServer.server_close()
