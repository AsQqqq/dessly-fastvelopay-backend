"""
Модуль для работы с API dessly
Функции получения данных аккаунта
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user_or_api_token
from app.dependencies import get_db
from cl import logger
import aiohttp


router = APIRouter(prefix="/dessly/account", tags=["steam"])
dessly_base_url = "https://desslyhub.com/api/v1"


# ==============================
# Получение данных аккаунта (баланс)
# ==============================


@router.get("/balance")
async def get_balance_route(
    request: Request,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """
    Получение баланса аккаунта dessly
    """


    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    url = f"{dessly_base_url}/merchants/balance"

    # Получаем токен из заголовка запроса
    dessly_token = request.headers.get("Dessly-Token")
    if not dessly_token:
        raise HTTPException(status_code=400, detail="Dessly token header missing")

    headers = {
        "Content-Type": "application/json",
        "apikey": dessly_token,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response_data = await response.json()
        
        balance = response_data.get("balance")
        error_code = response_data.get("error_code")

        if error_code is not None:
            logger.warning(f"Ошибка при получении баланса dessly: {response_data}")
            raise HTTPException(status_code=400, detail="Error fetching balance from Dessly API")
        
        logger.info(f"Баланс dessly успешно получен: {balance}")
        return {"balance": balance, "error": None}
    except Exception as e:
        logger.error(f"Исключение при получении баланса dessly: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching balance")