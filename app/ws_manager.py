from fastapi import WebSocket
from typing import Set
import asyncio
import msgpack
from cl import logger


def pack(data: dict) -> bytes:
    return msgpack.packb(data, use_bin_type=True)

class WebSocketManager:
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.connections.add(ws)
        logger.info(f"WS connected ({len(self.connections)})")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self.connections.discard(ws)
        logger.info(f"WS disconnected ({len(self.connections)})")

    async def broadcast(self, message: dict):
        data = pack(message)
        async with self._lock:
            for ws in list(self.connections):
                try:
                    await ws.send_bytes(data)
                except Exception:
                    self.connections.discard(ws)


ws_manager = WebSocketManager()