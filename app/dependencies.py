"""
Файл с зависимостями FastAPI-приложения.
Здесь реализована проверка доступа к API через JWT cookie или API-токен с whitelist (теперь в auth.py).
Также реализован лог запросов для аудита.
"""

from fastapi import Request, HTTPException
from app.database import SessionLocal
from app.config import settings
from cl import logger

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_docs_access(request: Request):
    token = request.headers.get("X-Docs-Token")
    logger.debug(f"Received X-Docs-Token: {token}")
    if token != settings.DOCS_SECRET_TOKEN:
        logger.warning("Access to documentation denied.")
        raise HTTPException(status_code=403, detail="Access to documentation denied.")
    logger.info("Access to documentation granted.")