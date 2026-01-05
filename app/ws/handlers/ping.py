from app.ws.dispatcher import register_handler
import msgpack

@register_handler("ping")
async def handle_ping(ws, msg):
    await ws.send_bytes(
        msgpack.packb({"type": "pong"}, use_bin_type=True)
    )
