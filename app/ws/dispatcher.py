from typing import Dict, Callable
import msgpack

handlers: Dict[str, Callable] = {}

def register_handler(msg_type: str):
    def decorator(func: Callable):
        handlers[msg_type] = func
        return func
    return decorator

async def dispatch(ws, msg: dict):
    msg_type = msg.get("type")
    handler = handlers.get(msg_type)

    if not handler:
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "error",
                    "message": f"Unknown WS type: {msg_type}"
                },
                use_bin_type=True
            )
        )
        return

    await handler(ws, msg)
