"""Measure how long a chat WebSocket survives, and which layer hangs up.

Read-only. Opens a socket, holds it, and reports the exact lifetime plus the
close code and reason. Point it at one layer at a time to bisect the path:

    --target direct   ws://127.0.0.1:8000/ws/chat        uvicorn alone
    --target origin   wss://<host>/api/ws/chat via IP    + nginx (skips Cloudflare)
    --target public   wss://<host>/api/ws/chat           + Cloudflare (full path)

The client deliberately sends no pings of its own (``ping_interval=None``) so it
behaves like a browser: it answers the server's pings and never initiates. A
client-side keepalive would mask exactly the failure being hunted.

Run from the backend/ directory:
    .venv/bin/python scripts/ws_lifetime_probe.py --target direct --user-id 5
    .venv/bin/python scripts/ws_lifetime_probe.py --target public --host spinshare.cc --user-id 5
"""

import argparse
import asyncio
import logging
import socket
import ssl
import sys
import time

sys.path.insert(0, ".")

from app.utils.security import create_chat_ticket  # noqa: E402

import websockets  # noqa: E402
from websockets.asyncio.client import connect  # noqa: E402


def _log(start: float, message: str) -> None:
    """Print wall-clock time, seconds since open, and the event."""
    now = time.time()
    print(
        f"{time.strftime('%H:%M:%S', time.localtime(now))}  t+{now - start:6.1f}s  {message}",
        flush=True,
    )


def _build_target(args, ticket: str) -> tuple[str, dict]:
    """Return the URI and the connect() kwargs for the requested layer."""
    query = f"?ticket={ticket}"

    if args.target == "direct":
        return f"ws://127.0.0.1:{args.port}/ws/chat{query}", {}

    uri = f"wss://{args.host}/api/ws/chat{query}"

    # Skip certificate verification: the origin test connects by IP, and this is
    # a diagnostic against the operator's own server either way.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if args.target == "public":
        return uri, {"ssl": ctx}

    # origin: keep the real Host header (it comes from the URI) but force the
    # TCP connection to the origin IP, so Cloudflare is not in the path.
    sock = socket.create_connection((args.origin_ip, 443))
    return uri, {"ssl": ctx, "sock": sock, "server_hostname": args.host}


async def probe(args) -> None:
    ticket = create_chat_ticket(args.user_id)
    uri, kwargs = _build_target(args, ticket)

    printable = uri.split("?")[0]
    print(f"\n=== {args.target}: {printable} (holding {args.seconds}s) ===", flush=True)

    start = time.time()
    try:
        async with connect(uri, ping_interval=None, max_queue=None, **kwargs) as ws:
            _log(start, "connection open")
            deadline = start + args.seconds
            while time.time() < deadline:
                try:
                    frame = await asyncio.wait_for(ws.recv(), timeout=deadline - time.time())
                except TimeoutError:
                    break
                _log(start, f"frame: {str(frame)[:120]}")
    except websockets.exceptions.ConnectionClosed as exc:
        _log(start, f"CLOSED by peer — code={exc.code} reason={exc.reason!r}")
        print(f"\n>>> lifetime: {time.time() - start:.1f}s, close code {exc.code}", flush=True)
        return
    except Exception as exc:
        _log(start, f"ERROR — {type(exc).__name__}: {exc}")
        return

    print(f"\n>>> survived the full {args.seconds}s without closing", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["direct", "origin", "public"], default="direct")
    parser.add_argument(
        "--user-id", type=int, required=True, help="A real user id (the ticket subject)"
    )
    parser.add_argument(
        "--host", default="spinshare.cc", help="Public hostname (origin/public targets)"
    )
    parser.add_argument("--origin-ip", default="127.0.0.1", help="Origin IP for the origin target")
    parser.add_argument("--port", type=int, default=8000, help="uvicorn port for the direct target")
    parser.add_argument("--seconds", type=int, default=300, help="How long to hold the socket")
    parser.add_argument("--debug", action="store_true", help="Log ping/pong frames")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(message)s")

    asyncio.run(probe(args))


if __name__ == "__main__":
    main()
