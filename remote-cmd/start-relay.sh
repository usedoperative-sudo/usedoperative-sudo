#!/bin/bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CS="${CODESPACE_NAME:-}"
TOKEN="$(python3 -c "import json;print(json.load(open('$HERE/config.json'))['token'])")"

if curl -s --max-time 3 "http://127.0.0.1:8787/status?token=$TOKEN" > /dev/null 2>&1; then
    echo "relay already running"
else
    setsid bash -c "exec python3 -u '$HERE/relay.py'" > /tmp/relay.log 2>&1 < /dev/null &
    disown 2>/dev/null
    sleep 2
    echo "relay started"
fi

if [ -n "$CS" ]; then
    if gh codespace ports -c "$CS" 2>/dev/null | grep -q 8787; then
        echo "port 8787 already forwarded"
    else
        setsid bash -c "exec gh codespace ports forward -c '$CS' 8787:8791" > /tmp/forward.log 2>&1 < /dev/null &
        disown 2>/dev/null
        sleep 6
        echo "port 8787 forwarded"
    fi
    gh codespace ports visibility -c "$CS" 8787:public > /dev/null 2>&1
    echo "public URL: https://${CS}-8787.app.github.dev"
fi

echo "token: $TOKEN"
echo "status: $(curl -s --max-time 5 "http://127.0.0.1:8787/status?token=$TOKEN")"
