from app.ws.dispatcher import register_handler
from cl import logger
import aiohttp
import msgpack

dessly_base_url = "https://desslyhub.com/api/v1"


@register_handler("dessly/balance")
async def handle_dessly_balance(ws, msg):
    """
    Получение баланса Dessly через WebSocket
    """

    # 1. Проверка токена
    dessly_token = msg.get("dessly_token")
    if not dessly_token:
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "error",
                    "error": "Dessly token missing"
                },
                use_bin_type=True
            )
        )
        return

    headers = {
        "Content-Type": "application/json",
        "apikey": dessly_token,
    }

    url = f"{dessly_base_url}/merchants/balance"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response_data = await response.json()

        error_code = response_data.get("error_code")
        balance = response_data.get("balance")

        if error_code is not None:
            logger.warning(f"Dessly balance error: {response_data}")
            await ws.send_bytes(
                msgpack.packb(
                    {
                        "type": "dessly/balance",
                        "error": "Error fetching balance from Dessly API"
                    },
                    use_bin_type=True
                )
            )
            return

        logger.info(f"Dessly balance received: {balance}")

        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/balance",
                    "balance": balance,
                    "error": None
                },
                use_bin_type=True
            )
        )

    except Exception as e:
        logger.error(f"Dessly balance exception: {str(e)}")
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/balance",
                    "error": "Internal server error"
                },
                use_bin_type=True
            )
        )
