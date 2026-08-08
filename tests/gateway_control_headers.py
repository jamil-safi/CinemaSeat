"""Exercise every mock-gateway /charge control header.

The callback receiver binds to the host. Docker Desktop containers reach it
through host.docker.internal, which lets the test count duplicate callbacks and
compare callback timing with the /charge response.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


GATEWAY_URL = "http://localhost:9000/charge"
CALLBACK_HOST = "host.docker.internal"
CALLBACK_PORT = 45123
CALLBACK_WAIT_SECONDS = 20


callbacks: list[dict] = []
callbacks_lock = threading.Lock()


class CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw.decode(errors="replace")}
        with callbacks_lock:
            callbacks.append({"received_at": time.monotonic(), "payload": payload})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"accepted"}')

    def log_message(self, _format: str, *args: object) -> None:
        return


@dataclass(frozen=True)
class Case:
    name: str
    header: str
    value: str


CASES = [
    Case("deterministic", "X-Mock-Mode", "deterministic"),
    Case("fail", "X-Mock-Force", "fail"),
    Case("duplicate", "X-Mock-Force", "duplicate"),
    Case("timeout", "X-Mock-Force", "timeout"),
    Case("race", "X-Mock-Force", "race"),
    Case("success", "X-Mock-Force", "success"),
]


def callbacks_for(booking_ref: str) -> list[dict]:
    with callbacks_lock:
        return [
            item
            for item in callbacks
            if item["payload"].get("booking_ref") == booking_ref
        ]


def run_case(case: Case) -> dict:
    booking_ref = f"control-{case.name}-{uuid4().hex[:10]}"
    started_at = time.monotonic()
    body = json.dumps(
        {
            "amount": 450,
            "currency": "BDT",
            "booking_ref": booking_ref,
            "callback_url": f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/callback",
        }
    ).encode()
    request = Request(
        GATEWAY_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", case.header: case.value},
    )

    response_status: int | str
    response_body = ""
    response_at: float | None = None
    try:
        with urlopen(request, timeout=4) as response:
            response_status = response.status
            response_body = response.read().decode()
            response_at = time.monotonic()
    except HTTPError as error:
        response_status = error.code
        response_body = error.read().decode(errors="replace")
        response_at = time.monotonic()
    except (TimeoutError, socket.timeout):
        response_status = "TIMEOUT"
    except URLError as error:
        response_status = f"ERROR: {error.reason}"

    return {
        "case": case.name,
        "header": f"{case.header}: {case.value}",
        "booking_ref": booking_ref,
        "started_at": started_at,
        "response_at": response_at or time.monotonic(),
        "charge_status": response_status,
        "charge_ms": round(((response_at or time.monotonic()) - started_at) * 1000),
        "response": response_body,
    }


def add_callback_results(result: dict) -> dict:
    received = callbacks_for(result["booking_ref"])
    statuses = [item["payload"].get("status") for item in received]
    event_ids = [item["payload"].get("event_id") for item in received]
    first_callback_at = received[0]["received_at"] if received else None
    callback_before_response = bool(
        first_callback_at and first_callback_at < result["response_at"]
    )
    callback_ms = (
        round((first_callback_at - result["started_at"]) * 1000)
        if first_callback_at
        else None
    )

    passed = {
        "deterministic": len(received) == 1 and statuses == ["SUCCEEDED"] and callback_ms >= 1900,
        "fail": len(received) == 1 and statuses == ["FAILED"],
        "duplicate": len(received) >= 2 and len(set(event_ids)) == 1,
        "timeout": result["charge_status"] == "TIMEOUT",
        "race": len(received) == 1 and statuses == ["SUCCEEDED"] and callback_before_response,
        "success": len(received) == 1 and statuses == ["SUCCEEDED"],
    }[result["case"]]

    return {
        "case": result["case"],
        "header": result["header"],
        "passed": passed,
        "charge_status": result["charge_status"],
        "charge_ms": result["charge_ms"],
        "first_callback_ms": callback_ms,
        "callback_count": len(received),
        "callback_statuses": statuses,
        "event_ids": event_ids,
        "callback_before_response": callback_before_response,
        "response": result["response"],
    }


def main() -> None:
    requested_cases = set(sys.argv[1:])
    selected_cases = [
        case for case in CASES if not requested_cases or case.name in requested_cases
    ]
    if not selected_cases:
        raise SystemExit(f"Unknown case(s): {', '.join(sorted(requested_cases))}")

    server = ThreadingHTTPServer(("0.0.0.0", CALLBACK_PORT), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with ThreadPoolExecutor(max_workers=len(selected_cases)) as executor:
            pending_results = list(executor.map(run_case, selected_cases))
        deadline = time.monotonic() + CALLBACK_WAIT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(0.05)
        results = [add_callback_results(result) for result in pending_results]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    print(json.dumps(results, indent=2))
    if not all(result["passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
