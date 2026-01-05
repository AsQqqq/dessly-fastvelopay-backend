"""
Модуль для работы с API dessly
Функции пополнения Steam
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from app.auth import get_current_user_or_api_token
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from cl import logger
import aiohttp


router = APIRouter(prefix="/dessly/steam", tags=["steam"])
dessly_base_url_topup = "https://desslyhub.com/api/v1/service/steamtopup"
dessly_base_url_gift = "https://desslyhub.com/api/v1/service/steamgift"


# ==============================
# Модели Pydantic
# ==============================

class check_login(BaseModel):
    """
    Проверка логина Steam через dessly API
    """

    username: str
    dessly_token: str
    amount: float

class topup_steam(BaseModel):
    """
    Пополнение Steam через dessly API
    """

    username: str
    dessly_token: str
    amount: float
    reference: Optional[str] = None

class get_all_games(BaseModel):
    """
    Получение списка игр
    """

    dessly_token: str

class get_data_game(BaseModel):
    """
    Получение данных игры
    """

    dessly_token: str
    app_id: str

class steam_gift(BaseModel):
    """
    Отправка гифта
    """

    username: str
    dessly_token: str
    amount: float
    reference: Optional[str] = None


# ==============================
# Проверка логина
# ==============================

@router.post("/check_login")
async def check_login_route(
    request: Request,
    payload: check_login,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Проверяет валидность логина и dessly_token для Steam
    """

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    url = f"{dessly_base_url_topup}/check_login"
    headers = {
        "Content-Type": "application/json",
        "apikey": payload.dessly_token,
    }
    payload = {
        "username": payload.username,
        "amount": payload.amount,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()

        error_code = response_data.get("error_code")
        can_refill = response_data.get("can_refill")
        
        if can_refill == True or error_code == 0:
            logger.info(f"Проверка логина Steam успешно выполнена: {response_data}")
            return {"status": True, "error": None}

        elif error_code == -100:
            logger.warning(f"Неверное имя пользователя Steam: {payload['username']}")
            return {"status": False, "error": "invalid_steam_username"}

        elif error_code == -2:
            logger.warning("Недостаточно средств на балансе")
            return {"status": False, "error": "insufficient_funds"}

        elif error_code == -5:
            logger.warning("Доступ запрещен")
            return {"status": False, "error": "access_denied"}

        else:
            logger.error(f"Неизвестная ошибка: {error_code}")
            return {"status": False, "error": f"unknown_error_{error_code}"}
            
    except Exception as e:
        logger.error(f"Ошибка при проверке логина Steam: {e}")
        return {"status": False}


# ==============================
# Пополнение Steam
# ==============================

@router.post("/topup")
async def topup_steam_route(
    request: Request,
    payload: topup_steam,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Отправляет запрос на пополнение Steam через API Dessly.
    Возвращает статус операции и код ошибки, если есть.
    """

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")

    url = f"{dessly_base_url_topup}/topup"
    headers = {
        "Content-Type": "application/json",
        "apikey": payload.dessly_token,
    }
    data = {
        "username": payload.username,
        "amount": payload.amount,
        "reference": payload.reference,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=data, headers=headers) as response:
                response_data = await response.json()
        
        error_code = response_data.get("error_code")
        status = response_data.get("status")
        transaction_id = response_data.get("transaction_id")

        logger.warning("Error code received from Dessly API topup: %s", error_code)
        
        if status == "pending" or error_code == 0 or transaction_id is not None:
            logger.info(f"Пополнение Steam успешно выполнено: {response_data}")
            return {
                "status": True,
                "error": None,
                "transaction_id": response_data.get("transaction_id")
            }

        elif error_code == -100:
            logger.warning(f"Неверное имя пользователя Steam: {data['username']}")
            return {"status": False, "error": "invalid_steam_username"}

        elif error_code == -2:
            logger.warning("Недостаточно средств на балансе")
            return {"status": False, "error": "insufficient_funds"}

        elif error_code == -5:
            logger.warning("Доступ запрещен")
            return {"status": False, "error": "access_denied"}

        elif error_code == -7:
            logger.warning("Пополнение не удалось: ошибка транзакции")
            return {"status": False, "error": "transaction_failed"}

        else:
            logger.error(f"Неизвестная ошибка при пополнении: {error_code}")
            return {"status": False, "error": f"unknown_error_{error_code}"}

    except Exception as e:
        logger.error(f"Ошибка при запросе к API Dessly (topup): {e}")
        return {"status": False, "error": "connection_error"}
    

# ==============================
# Получение списка игр
# ==============================

@router.post("/games")
async def games_gift(
    request: Request,
    payload: get_all_games,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Получение списка игр
    """

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    url = f"{dessly_base_url_gift}/games"
    headers = {
        "Content-Type": "application/json",
        "apikey": payload.dessly_token,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                response_data = await response.json()

        # Если пришли игры → успех
        if "games" in response_data:
            logger.info("Список игр успешно получен")
            return {"status": True, "error": None, "games": response_data["games"]}

        # Если пришла ошибка → обрабатываем
        error_code = response_data.get("error_code")

        if error_code == -1:
            logger.warning("Сервер не ответил")
            return {"status": False, "error": "server_error", "games": None}

        if error_code == -5:
            logger.warning("Доступ запрещен")
            return {"status": False, "error": "access_denied", "games": None}

        # Неизвестный error_code (если появятся новые)
        logger.error(f"Неизвестная ошибка: {error_code}")
        return {"status": False, "error": f"unknown_error_{error_code}", "games": None}

    except Exception as e:
        logger.error(f"Ошибка при получении списка игр Steam: {e}")
        return {"status": False}


# ==============================
# Получение данных игры
# ==============================

@router.post("/game")
async def data_game_gift(
    request: Request,
    payload: get_data_game,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Получение данных игры
    """

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    url = f"{dessly_base_url_gift}/games/{payload.app_id}"
    headers = {
        "Content-Type": "application/json",
        "apikey": payload.dessly_token,
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                response_data = await response.json()

        # Если пришли игры → успех
        if "game" in response_data:
            logger.info("Данные игры успешно получены")
            return {"status": True, "error": None, "game": response_data["game"]}

        # Если пришла ошибка → обрабатываем
        error_code = response_data.get("error_code")

        if error_code == -1:
            logger.warning("Сервер не ответил")
            return {"status": False, "error": "server_error", "games": None}

        if error_code == -5:
            logger.warning("Доступ запрещен")
            return {"status": False, "error": "access_denied", "games": None}

        # Неизвестный error_code (если появятся новые)
        logger.error(f"Неизвестная ошибка: {error_code}")
        return {"status": False, "error": f"unknown_error_{error_code}", "games": None}

    except Exception as e:
        logger.error(f"Ошибка при получении данных игры Steam: {e}")
        return {"status": False}