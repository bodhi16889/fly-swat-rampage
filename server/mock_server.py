#!/usr/bin/env python3
"""Local mock of the Fly Swat Rampage leaderboard API (stdlib only).

Used by verify_smoke.py and for manual frontend work:
    python3 server/mock_server.py --port 8790
Then open index.html?lb=on&lb_url=http://127.0.0.1:8790&lb_token=test-alice

It accepts test tokens only (`test-<id>` and the SDK's `gpx-local-mock-token`).
Never deploy this file; production uses worker.js + D1 with real JWT checks.
"""
import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

LEVEL_MAX = 100
STORE = {}
LOCK = threading.Lock()


def goal_type(n):
    chapter = (n - 1) // 20 + 1
    stage = (n - 1) % 20 + 1
    is_boss = stage % 10 == 0
    is_defend = (not is_boss) and chapter == 3 and stage % 3 != 0
    is_kills = (not is_boss) and (not is_defend) and (
        chapter in (2, 4) or stage % 2 == 0
    )
    return "boss" if is_boss else "defend" if is_defend else "kills" if is_kills else "score"


def level_time(n):
    chapter = (n - 1) // 20 + 1
    stage = (n - 1) % 20 + 1
    is_boss = stage % 10 == 0
    is_defend = (not is_boss) and chapter == 3 and stage % 3 != 0
    is_kills = (not is_boss) and (not is_defend) and (
        chapter in (2, 4) or stage % 2 == 0
    )
    if is_boss:
        return 80
    if is_defend:
        return round(45 + min(15, n * 0.12))
    if is_kills:
        return round(45 + min(20, n * 0.15))
    return round(40 + min(20, n * 0.15))


def clean_name(raw):
    s = re.sub(r"<[^>]*>", "", str(raw or ""))
    s = re.sub(r"[\x00-\x1f<>]", "", s)
    s = re.sub(r"\s+", " ", s).strip()[:16]
    return s or "Player"


def validate(body):
    level = int(body.get("level", 0))
    if not 1 <= level <= LEVEL_MAX:
        raise ValueError("bad-level")
    kind = goal_type(level)
    value = int(round(float(body.get("value", 0))))
    time_ms = int(round(float(body.get("timeMs", 0))))
    misses = int(round(float(body.get("misses", 0))))
    revived = 1 if body.get("revived") else 0
    if value < 0 or time_ms < 0 or misses < 0 or misses > 999:
        raise ValueError("bad-range")
    if time_ms > level_time(level) * 1000 + 3000:
        raise ValueError("time-too-long")
    if kind == "score":
        if value > max(2000, (300 + level * 40) * 20):
            raise ValueError("score-too-high")
    elif kind == "defend":
        if value > 100 or time_ms < 2000:
            raise ValueError("bad-defend")
    else:
        if value != time_ms or time_ms < 3000:
            raise ValueError("bad-time")
    return level, kind, value, time_ms, misses, revived


def better(new, old, kind):
    if old is None:
        return True
    if kind in ("score", "defend"):
        return (new["value"], -new["time_ms"]) > (old["value"], -old["time_ms"])
    return (new["time_ms"], new["misses"]) < (old["time_ms"], old["misses"])


def rank_of(level, revived, kind, entry):
    rows = [r for r in STORE.values() if r["level"] == level and r["revived"] == revived]
    if kind in ("score", "defend"):
        ahead = [r for r in rows if r["value"] > entry["value"] or (
            r["value"] == entry["value"] and r["time_ms"] < entry["time_ms"])]
    else:
        ahead = [r for r in rows if r["time_ms"] < entry["time_ms"] or (
            r["time_ms"] == entry["time_ms"] and r["misses"] < entry["misses"])]
    return len(ahead) + 1


def player(headers):
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if token == "gpx-local-mock-token":
        return {"sub": "mock", "username": "MockPlayer"}
    if token.startswith("test-") and len(token) > 5:
        uid = token[5:]
        return {"sub": uid, "username": uid}
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "FlySwatLbMock/1.0"

    def log_message(self, format, *args):
        pass

    def _send(self, data, status=200):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length).decode() or "{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/v1/health":
            return self._send({"ok": True, "mock": True})
        if url.path != "/v1/leaderboard":
            return self._send({"error": "not-found"}, 404)
        q = parse_qs(url.query)
        try:
            level = int(q.get("level", ["0"])[0])
        except ValueError:
            return self._send({"error": "bad-level"}, 400)
        if not 1 <= level <= LEVEL_MAX:
            return self._send({"error": "bad-level"}, 400)
        revived = 1 if q.get("revived", ["0"])[0] == "1" else 0
        try:
            limit = min(100, max(1, int(q.get("limit", ["50"])[0])))
        except ValueError:
            limit = 50
        kind = goal_type(level)
        with LOCK:
            rows = [r for r in STORE.values() if r["level"] == level and r["revived"] == revived]
            rows.sort(key=(lambda r: (-r["value"], r["time_ms"]))
                      if kind in ("score", "defend")
                      else (lambda r: (r["time_ms"], r["misses"])))
            who = player(self.headers)
            out = [{
                "name": r["name"], "value": r["value"], "timeMs": r["time_ms"],
                "misses": r["misses"], "revived": r["revived"],
                "you": bool(who and r["player_id"] == who["sub"]),
            } for r in rows[:limit]]
            me = None
            if who:
                mine = next((r for r in rows if r["player_id"] == who["sub"]), None)
                if mine:
                    me = {"rank": rank_of(level, revived, kind, mine),
                          "value": mine["value"], "timeMs": mine["time_ms"],
                          "misses": mine["misses"], "revived": mine["revived"]}
        return self._send({"level": level, "revived": revived, "rows": out, "me": me})

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/v1/reset":
            with LOCK:
                STORE.clear()
            return self._send({"ok": True})
        if url.path != "/v1/scores":
            return self._send({"error": "not-found"}, 404)
        who = player(self.headers)
        if not who:
            return self._send({"error": "login-required"}, 401)
        try:
            body = self._body()
            level, kind, value, time_ms, misses, revived = validate(body)
        except (ValueError, TypeError) as e:
            return self._send({"error": str(e) or "bad-request"}, 400)
        entry = {
            "level": level, "player_id": who["sub"], "name": clean_name(body.get("name") or who["username"]),
            "value": value, "time_ms": time_ms, "misses": misses, "revived": revived,
        }
        key = (level, who["sub"], revived)
        with LOCK:
            old = STORE.get(key)
            if better(entry, old, kind):
                STORE[key] = entry
                stored = entry
            else:
                stored = old
            rank = rank_of(level, revived, kind, stored)
        return self._send({"ok": True, "level": level, "revived": revived,
                           "rank": rank, "name": entry["name"]})

    def do_DELETE(self):
        if urlparse(self.path).path != "/v1/me":
            return self._send({"error": "not-found"}, 404)
        who = player(self.headers)
        if not who:
            return self._send({"error": "login-required"}, 401)
        with LOCK:
            for k in [k for k, v in STORE.items() if v["player_id"] == who["sub"]]:
                STORE.pop(k, None)
        return self._send({"ok": True})


def start(port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"mock leaderboard on http://127.0.0.1:{args.port}")
    srv.serve_forever()
