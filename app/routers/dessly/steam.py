"""
Модуль для работы с API dessly
Функции пополнения Steam
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import requests
from cl import logger
from app.auth import get_current_user_or_api_token
from app.database import User
from app.dependencies import get_db


router = APIRouter(prefix="/dessly/steam", tags=["steam"])
dessly_base_url = "https://desslyhub.com/api/v1/service/steamtopup"


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


# ==============================
# Проверка логина
# ==============================

@router.post("/check_login")
def check_login_route(
    request: Request,
    payload: check_login,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """
    Проверяет валидность логина и dessly_token для Steam
    """

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    url = f"{dessly_base_url}/check_login"
    headers = {
        "Content-Type": "application/json",
        "apikey": payload.dessly_token,
    }
    payload = {
        "username": payload.username,
        "amount": payload.amount,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        
        response_data = response.json()

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
            
    except requests.RequestException as e:
        logger.error(f"Ошибка при проверке логина Steam: {e}")
        return {"status": False}


# ==============================
# Пополнение Steam
# ==============================

@router.post("/topup")
def topup_steam_route(
    request: Request,
    payload: topup_steam,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db),
):
    """
    Отправляет запрос на пополнение Steam через API Dessly.
    Возвращает статус операции и код ошибки, если есть.
    """

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")

    url = f"{dessly_base_url}/topup"
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
        response = requests.post(url, json=data, headers=headers)
        response_data = response.json()
        
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

    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к API Dessly (topup): {e}")
        return {"status": False, "error": "connection_error"}