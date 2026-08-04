#!/usr/bin/env python3
import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
PORT = int(os.environ.get("CMD_RELAY_PORT", "8787"))
POLL_TIMEOUT = 25


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    cfg = {"token": os.urandom(16).hex()}
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    return cfg


CONFIG = load_config()

_state = {"pending": [], "results": {}, "last_poll": 0.0}
_cond = threading.Condition()


class Handler(BaseHTTPRequestHandler):
    def _query(self, key, default=None):
        return parse_qs(urlparse(self.path).query).get(key, [default])[0]

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bad_token(self):
        self._send_json({"error": "bad token"}, 401)

    def do_GET(self):
        if self._query("token") != CONFIG["token"]:
            return self._bad_token()
        path = urlparse(self.path).path
        if path == "/poll":
            with _cond:
                _state["last_poll"] = time.time()
                deadline = time.time() + POLL_TIMEOUT
                while not _state["pending"]:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return self._send_json({"event": "timeout"})
                    _cond.wait(remaining)
                cmd = _state["pending"].pop(0)
            return self._send_json({"event": "command", "id": cmd["id"], "cmd": cmd["cmd"]})
        if path == "/result":
            rid = self._query("id")
            with _cond:
                res = _state["results"].get(rid)
            if res is None:
                return self._send_json({"pending": True})
            return self._send_json(res)
        if path == "/status":
            with _cond:
                age = time.time() - _state["last_poll"]
                npend = len(_state["pending"])
            self._send_json({"online": age < 60, "last_poll_age": round(age, 1), "pending": npend})
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self._query("token") != CONFIG["token"]:
            return self._bad_token()
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        if path == "/send":
            rid = uuid.uuid4().hex[:12]
            with _cond:
                _state["pending"].append({"id": rid, "cmd": data.get("cmd", "")})
                _cond.notify_all()
            return self._send_json({"id": rid})
        if path == "/result":
            rid = data.get("id", "")
            with _cond:
                _state["results"][rid] = data
                _cond.notify_all()
            return self._send_json({"ok": True})
        self._send_json({"error": "not found"}, 404)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    _state["last_poll"] = time.time()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"relay listening on 0.0.0.0:{PORT}")
    print(f"token: {CONFIG['token']}")
    server.serve_forever()
