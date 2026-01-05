from fastapi import WebSocket, WebSocketDisconnect, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.auth import get_api_token_from_header
from app.ws_manager import ws_manager
from app.ws.dispatcher import dispatch
from msgpack import unpackb
import msgpack
import app.ws.handlers

async def websocket_endpoint(
    ws: WebSocket,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    # авторизация
    try:
        await get_api_token_from_header(authorization, db)
    except Exception:
        await ws.close(code=1008)
        return

    await ws_manager.connect(ws)

    # отправка конфига при подключении (как у тебя и было)
    # from app.config import config_cache
    # await ws.send_bytes(
    #     msgpack.packb({
    #         "type": "config_full",
    #         "data": config_cache
    #     }, use_bin_type=True)
    # )

    try:
        
        while True:
            message = await ws.receive()

            if message["type"] == "websocket.disconnect":
                return

            if "bytes" not in message or message["bytes"] is None:
                # можно логировать или сразу закрывать
                await ws.send_bytes(
                    msgpack.packb(
                        {
                            "type": "error",
                            "error": "Only binary msgpack messages are supported"
                        },
                        use_bin_type=True
                    )
                )
                continue

            msg = unpackb(message["bytes"], raw=False)

            if not isinstance(msg, dict):
                continue

            await dispatch(ws, msg)

    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)
