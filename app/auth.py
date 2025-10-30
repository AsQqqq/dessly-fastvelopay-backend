"""
Модуль для управления аутентификацией и авторизацией пользователей и API токенов.
Включает:
- Создание и проверка JWT токенов для пользователей (админов).
- Генерация, шифрование и проверка API токенов, хранимых в базе данных.
- Универсальная проверка доступа: либо по JWT, либо по API токену с проверкой по белому списку доменов/IP.
- Управление токенами пользователями (создание, удаление, просмотр).
"""

from fastapi import Depends, HTTPException, Request
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import secrets
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from app.database import APIToken, WhitelistedEntry, SessionLocal, RequestAudit
from app.config import settings
from cryptography.fernet import Fernet
from cl import logger
from app.config import get_config_value

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


def generate_api_token(db: Session, name: str, user_id: int, access_level: int = 0, description: str = None) -> Dict[str, Any]:
    raw_token = secrets.token_urlsafe(32)
    encrypted = encrypt_token(raw_token)
    api = APIToken(name=name, key=encrypted, user_id=user_id, access_level=access_level, description=description)
    db.add(api)
    db.commit()
    db.refresh(api)
    logger.info(f"Generated API token {name} for user_id={user_id}")
    # возвращаем незашифрованный ключ пользователю (один раз)
    return {"name": name, "token": encrypted, "uuid": api.uuid, "access_level": access_level, "description": description}


def get_current_user_or_api_token(request: Request, db: Session = Depends(get_db)):
    """
    Универсальная проверка: либо JWT (admin), либо Bearer API-токен + условный whitelist.
    Whitelist проверяется ТОЛЬКО если whitelist_enabled=true И access_level=0.
    Возвращает dict с type: 'admin' или 'api_token' и сопутствующей информацией.
    """
    # 1) JWT cookie (admin) — всегда без whitelist
    access_cookie = request.cookies.get("access_token")
    if access_cookie:
        username = get_current_user(request)
        logger.debug(f"Admin access by {username}")
        return {"type": "admin", "username": username}

    # 2) Bearer API token
    try:
        token_obj = get_api_token_from_header(request.headers.get("Authorization"), db)
    except HTTPException:
        logger.warning("API token not provided or invalid")
        raise HTTPException(status_code=401, detail="API token required")

    # Извлекаем origin/domain/ip заранее — для лога и условной проверки
    origin = request.headers.get("Origin")
    domain = urlparse(origin).netloc if origin else None
    client_ip = request.client.host

    # 3) Условная проверка whitelist: только для level 0 + enabled
    whitelist_enabled = get_config_value("whitelist", default=True)
    if token_obj.access_level == 0 and whitelist_enabled:
        # Ищем совпадение по WhitelistedEntry.value (может быть ip или домен)
        domain_allowed = db.query(WhitelistedEntry).filter(WhitelistedEntry.value == domain).first() is not None if domain else False
        ip_allowed = db.query(WhitelistedEntry).filter(WhitelistedEntry.value == client_ip).first() is not None

        if not (domain_allowed or ip_allowed):
            logger.warning(f"Level 0 token from non-whitelisted origin/ip: {domain} / {client_ip} (whitelist_enabled={whitelist_enabled})")
            raise HTTPException(status_code=403, detail=f"Access from this IP/domain is not allowed, your IP/domain address - {client_ip} / {domain or 'N/A'}")

    # Всё ок — логируем аудит
    audit = RequestAudit(
        path=request.url.path,
        method=request.method,
        client_ip=client_ip,
        api_token_id=token_obj.id,
    )
    db.add(audit)
    db.commit()
    logger.info(f"Access granted for token_id={token_obj.id} (level={token_obj.access_level}) from {client_ip} / {domain or 'N/A'} (whitelist: {whitelist_enabled})")

    return {"type": "api_token", "token_obj": token_obj}


def require_access_level(token: APIToken, min_level: int):
    """Проверяет, что токен имеет необходимый уровень доступа."""
    if token.access_level < min_level:
        raise HTTPException(
            status_code=403,
            detail=f"Недостаточно прав.",
        )
    

def get_api_token_from_header(
    authorization: Optional[str],
    db: Session
) -> APIToken:
    """Возвращает объект APIToken по заголовку Authorization"""
    token_value = get_token_from_header(authorization)
    if not token_value:
        raise HTTPException(status_code=401, detail="Токен не предоставлен")

    token = db.query(APIToken).filter(APIToken.key == token_value).first()
    if not token:
        raise HTTPException(status_code=401, detail="Неверный или недействительный токен")
    return token


def get_token_from_header(authorization: Optional[str]) -> str:
    """Извлекает токен из заголовка Authorization: Bearer <token>"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Токен не предоставлен")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Неверный формат заголовка Authorization")
    return parts[1]


def create_audit_record(db: Session, request: Request, api_token: APIToken):
    """Создаёт запись аудита в базе данных."""
    audit = RequestAudit(
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host,
        api_token_id=api_token.id,
    )
    db.add(audit)
    db.commit()