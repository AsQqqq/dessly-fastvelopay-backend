"""
Модуль для управления аутентификацией и авторизацией пользователей и API токенов.
Включает:
- Создание и проверка JWT токенов для пользователей (админов).
- Генерация, шифрование и проверка API токенов, хранимых в базе данных.
- Универсальная проверка доступа: либо по JWT, либо по API токену с проверкой по белому списку доменов/IP.
- Управление токенами пользователями (создание, удаление, просмотр).
"""

from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import secrets
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from app.database import APIToken, WhitelistedEntry, SessionLocal
from app.config import settings
from cryptography.fernet import Fernet
from cl import logger

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

# Инициализация Fernet
if not settings.FERNET_KEY:
    raise RuntimeError("FERNET_KEY not set in environment")
fernet = Fernet(settings.FERNET_KEY.encode())

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Пользовательские JWT ---
def create_token(data: dict, expires_minutes: int = None) -> str:
    logger.debug("Creating JWT token")
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=(expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        logger.warning("No access_token cookie")
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return username
    except JWTError:
        logger.warning("Invalid JWT token")
        raise HTTPException(status_code=401, detail="Invalid token")


# --- API tokens (защищённые в БД) ---
def encrypt_token(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(token_enc: Optional[str]) -> Optional[str]:
    if not token_enc:
        return None
    try:
        return fernet.decrypt(token_enc.encode()).decode()
    except Exception as e:
        logger.debug(f"Failed to decrypt token: {e}")
        return None


def generate_api_token(db: Session, name: str, user_id: int, access_level: int = 0) -> Dict[str, Any]:
    raw_token = secrets.token_urlsafe(32)
    encrypted = encrypt_token(raw_token)
    api = APIToken(name=name, key=encrypted, user_id=user_id, access_level=access_level, description=None)
    db.add(api)
    db.commit()
    db.refresh(api)
    logger.info(f"Generated API token {name} for user_id={user_id}")
    # возвращаем незашифрованный ключ пользователю (один раз)
    return {"name": name, "token": raw_token, "uuid": api.uuid}


def get_api_token_from_header(request: Request, db: Session) -> Optional[APIToken]:
    header = request.headers.get("X-API-Token")
    if not header:
        return None
    # Ищем по всем токенам, дешифруя ключи
    all_tokens = db.query(APIToken).all()
    for db_token in all_tokens:
        try:
            if decrypt_token(db_token.key) == header:
                return db_token
        except Exception:
            continue
    return None


def get_current_user_or_api_token(request: Request, db: Session = Depends(get_db)):
    """
    Универсальная проверка: либо JWT (admin), либо X-API-Token + whitelisted domain/ip.
    Возвращает dict с type: 'admin' или 'api_token' и сопутствующей информацией.
    """
    # 1) JWT cookie
    access_cookie = request.cookies.get("access_token")
    if access_cookie:
        username = get_current_user(request)
        return {"type": "admin", "username": username}

    # 2) API token
    token_obj = get_api_token_from_header(request, db)
    if not token_obj:
        logger.warning("API token not provided or invalid")
        raise HTTPException(status_code=401, detail="API token required")

    # Проверка Origin/Ip whitelist
    origin = request.headers.get("Origin")
    domain = urlparse(origin).netloc if origin else None
    client_ip = request.client.host

    # Ищем совпадение по WhitelistedEntry.value (может быть ip или домен)
    domain_allowed = False
    ip_allowed = False
    if domain:
        domain_allowed = db.query(WhitelistedEntry).filter(WhitelistedEntry.value == domain).first() is not None
    ip_allowed = db.query(WhitelistedEntry).filter(WhitelistedEntry.value == client_ip).first() is not None

    if not (domain_allowed or ip_allowed):
        logger.warning(f"Valid token used from non-whitelisted origin/ip: {domain} / {client_ip}")
        raise HTTPException(status_code=403, detail="Access from this IP/domain is not allowed")

    return {"type": "api_token", "token_obj": token_obj}


# --- Управление токенами пользователем (для внутренних роутов admin) ---
def get_user_tokens(db: Session, user_id: int):
    return db.query(APIToken).filter(APIToken.user_id == user_id).all()


def delete_token_by_name(db: Session, name: str, user_id: int) -> bool:
    token = db.query(APIToken).filter(APIToken.name == name, APIToken.user_id == user_id).first()
    if token:
        db.delete(token)
        db.commit()
        logger.info(f"Deleted API token '{name}' for user {user_id}")
        return True
    return False
