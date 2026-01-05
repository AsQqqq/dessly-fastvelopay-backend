from app.ws.dispatcher import register_handler
from cl import logger
import aiohttp
import msgpack
from decimal import Decimal, ROUND_DOWN

dessly_rates_url = "https://desslyhub.com/api/v1/exchange_rates/steam"

currency_key = {
    "KZT": 37,
    "UAH": 18,
    "RUB": 5,
    "USD": 5,
}


@register_handler("dessly/conversion")
async def handle_dessly_conversion(ws, msg):
    """
    Конвертация валюты через Dessly (WebSocket)
    """

    # -------- 1. Валидация входных данных --------
    try:
        dessly_token = msg.get("dessly_token")
        amount = Decimal(str(msg.get("amount")))
        currency = msg.get("currency")
        convert_to_rub = bool(msg.get("convert_to_rub", False))
    except Exception:
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/conversion",
                    "error": "Invalid input data"
                },
                use_bin_type=True
            )
        )
        return

    if not dessly_token:
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/conversion",
                    "error": "Dessly token missing"
                },
                use_bin_type=True
            )
        )
        return

    if currency not in currency_key:
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/conversion",
                    "error": "Unsupported currency"
                },
                use_bin_type=True
            )
        )
        return

    # -------- 2. Запрос курсов --------
    headers = {
        "Content-Type": "application/json",
        "apikey": dessly_token,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(dessly_rates_url, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError("Dessly API error")

                data = await resp.json()

    except Exception as e:
        logger.error(f"Dessly exchange rates error: {e}")
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/conversion",
                    "error": "Error fetching exchange rates"
                },
                use_bin_type=True
            )
        )
        return

    logger.warning(f"Dessly rates: {data}")

    # -------- 3. Конвертация --------
    currency_id = currency_key[currency]

    if str(currency_id) not in data.get("exchange_rates", {}):
        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/conversion",
                    "error": "Currency rate missing"
                },
                use_bin_type=True
            )
        )
        return

    rate = Decimal(str(data["exchange_rates"][str(currency_id)]))
    converted = amount / rate

    truncated = converted.quantize(Decimal("0.00"), rounding=ROUND_DOWN)
    final_amount = truncated + Decimal("0.01")

    # -------- 4. Конвертация в RUB (если нужно) --------
    if convert_to_rub:
        rub_id = currency_key["RUB"]

        if str(rub_id) not in data["exchange_rates"]:
            await ws.send_bytes(
                msgpack.packb(
                    {
                        "type": "dessly/conversion",
                        "error": "RUB rate missing"
                    },
                    use_bin_type=True
                )
            )
            return

        rub_rate = Decimal(str(data["exchange_rates"][str(rub_id)]))
        rub_amount = amount * rub_rate

        await ws.send_bytes(
            msgpack.packb(
                {
                    "type": "dessly/conversion",
                    "original_amount_usd": str(amount),
                    "converted_amount_rub": str(
                        rub_amount.quantize(Decimal("0.00"), rounding=ROUND_DOWN)
                    ),
                    "error": None
                },
                use_bin_type=True
            )
        )
        return

    # -------- 5. Ответ --------
    await ws.send_bytes(
        msgpack.packb(
            {
                "type": "dessly/conversion",
                "original_amount": str(amount),
                "original_currency": currency,
                "converted_amount_usd": str(final_amount),
                "error": None
            },
            use_bin_type=True
        )
    )
