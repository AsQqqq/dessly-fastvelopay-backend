import websockets
import asyncio
import msgpack

headers = {
    "Authorization": "Bearer c4cbf2ccef4c3de2dfecd9440b0aae46012c0f5c70f9236efa0c5c2ea0dba2fd"
}

def pack(data: dict) -> bytes:
    return msgpack.packb(data, use_bin_type=True)

def unpack(data: bytes) -> dict:
    return msgpack.unpackb(data, raw=False)

async def run():
    async with websockets.connect(
        "ws://192.168.0.205:8080/ws",
        additional_headers=headers,
        proxy=None,
        ssl=None,
    ) as ws:

        await ws.send(pack({
            "type": "ping",
            "source": "startup"
        }))

        async def delayed_request():
            await asyncio.sleep(5)
            await ws.send(pack({
                "type": "dessly/balance",
                "dessly_token": "56b850b346564faa9b4cc2fe684da9bc"
            }))

        # запускаем отложенный запрос параллельно
        asyncio.create_task(delayed_request())

        # Постоянно слушаем сервер
        while True:
            data = unpack(await ws.recv())
            print("FROM SERVER:", data)

asyncio.run(run())