"""Optional authenticated WebSocket status events; phone RPC remains existing HTTP."""

from __future__ import annotations

import json
import logging
import threading

from symport.phone.bridge_security import host_allowed, key_allowed


def start_events(agent, key, port):
    try:
        from websockets.sync.server import serve
    except ImportError:
        return None
    clients = threading.BoundedSemaphore(4)

    def session(socket):
        if not clients.acquire(blocking=False):
            socket.close(1013, "Bridge busy")
            return
        try:
            try:
                initial = json.loads(socket.recv(timeout=3))
                if not isinstance(initial, dict) or not key_allowed(
                    str(initial.get("token", "")), key
                ):
                    socket.close(1008, "Authorization required")
                    return
            except (ValueError, TimeoutError, TypeError):
                socket.close(1008, "Authorization required")
                return
            while not agent.stop.is_set():
                socket.send(
                    json.dumps(
                        {
                            "schema": "symport.bridge.events/1",
                            "type": "status",
                            "status": agent.status,
                        }
                    )
                )
                if agent.stop.wait(2):
                    break
        except Exception:
            pass  # Never log frames, authorization or private data.
        finally:
            clients.release()

    def handshake(connection, request):
        from http import HTTPStatus

        if (
            request.path != "/api/bridge/events"
            or len(request.headers.get_all("Host")) != 1
            or not host_allowed(request.headers["Host"], port)
        ):
            return connection.respond(HTTPStatus.FORBIDDEN, "Host or path not allowed")

    logger = logging.getLogger("symport.bridge.websocket")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    server = serve(
        session,
        "127.0.0.1",
        port,
        origins=[None, *agent.server.origins],
        max_size=16384,
        open_timeout=5,
        close_timeout=2,
        logger=logger,
        process_request=handshake,
    )
    threading.Thread(target=server.serve_forever, daemon=True, name="bridge-events").start()
    return server
