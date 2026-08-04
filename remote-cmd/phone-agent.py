#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.request

RELAY_URL = os.environ.get("RELAY_URL", "")
TOKEN = os.environ.get("CMD_TOKEN", "")
POLL_TIMEOUT = 25
EXEC_TIMEOUT = 300


def poll():
    req = urllib.request.Request(f"{RELAY_URL}/poll?token={TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 5) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"event": "error", "detail": str(e)}


def send_result(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{RELAY_URL}/result?token={TOKEN}", data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
    except Exception:
        pass


def execute(cmd):
    try:
        proc = subprocess.run(["sh", "-c", cmd], capture_output=True, text=True, timeout=EXEC_TIMEOUT)
        output = proc.stdout
        if proc.stdout and proc.stderr:
            output += "\n"
        output += proc.stderr
        return proc.returncode, output
    except subprocess.TimeoutExpired as e:
        partial = (e.stdout or "") + (e.stderr or "")
        return 124, partial + f"\n[timed out after {EXEC_TIMEOUT}s]"
    except Exception as e:
        return 1, f"agent error: {e}"


def main():
    if not RELAY_URL or not TOKEN:
        print("set RELAY_URL and CMD_TOKEN first", file=sys.stderr)
        sys.exit(1)
    print(f"agent: polling {RELAY_URL} every {POLL_TIMEOUT}s", flush=True)
    while True:
        ev = poll()
        if ev.get("event") == "command":
            rid, cmd = ev["id"], ev["cmd"]
            print(f"\u2192 exec #{rid}: {cmd}", flush=True)
            code, output = execute(cmd)
            print(f"\u2190 #{rid} exit={code}", flush=True)
            send_result({"id": rid, "code": code, "output": output})
        elif ev.get("event") == "error":
            print(f"poll error: {ev.get('detail')}", flush=True)
            time.sleep(5)
        else:
            time.sleep(1)


if __name__ == "__main__":
    main()
