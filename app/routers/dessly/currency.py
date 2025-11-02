"""
Модуль для работы с API dessly
Функции пополнения Steam
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from app.auth import get_current_user_or_api_token
from app.dependencies import get_db
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal, ROUND_DOWN
from cl import logger
import aiohttp


router = APIRouter(prefix="/currency", tags=["currency"])
dessly_base_url = "https://desslyhub.com/api/v1/exchange_rates/steam"


# ==============================
# Модели Pydantic
# ==============================

class currency(BaseModel):
    """
    Проверка логина Steam через dessly API
    """

    amount: Decimal
    currency: str
    dessly_token: str

# ==============================
# Проверка логина
# ==============================

@router.post("/conversion")
async def currency_conversion(
    request: Request,
    payload: currency,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """
    Конвертация валюты через dessly API
    """

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    if not payload.dessly_token:
        raise HTTPException(status_code=400, detail="Error dessly token")

    headers = {
        "content-type": "application/json",
        "apikey": payload.dessly_token
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(dessly_base_url, headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="Error fetching exchange rates from Dessly API")
            data = await resp.json()
        
    currency_key = {
        "code": {
            "KZT": 37,
            "UAH": 18,
            "RUB": 5
        }
    }

    input_currency = payload.currency
    amount = payload.amount

    if input_currency in currency_key["code"]:
        currency_id = currency_key["code"][input_currency]
        if str(currency_id) in data["exchange_rates"]:
            rate = Decimal(str(data["exchange_rates"][str(currency_id)]))
            converted = amount / rate

            # Обрезаем до двух знаков без округления
            truncated = converted.quantize(Decimal("0.00"), rounding=ROUND_DOWN)
            # Добавляем 0.01
            final_amount = truncated + Decimal("0.01")

            return {
                "original_amount": str(amount),
                "original_currency": input_currency,
                "converted_amount_usd": str(final_amount)
            }
        else:
            raise HTTPException(status_code=400, detail="Currency ID not found in rates.")
    else:
        raise HTTPException(status_code=400, detail="Unsupported currency.")