"""
Файл с зависимостями FastAPI-приложения.
Здесь реализована проверка доступа к API через JWT cookie или API-токен с whitelist (теперь в auth.py).
Также реализован лог запросов для аудита.
"""

from fastapi import Request, HTTPException
from app.database import AsyncSessionLocal, User
from app.config import settings
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from cl import logger


async def get_db():
    """Асинхронный генератор сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error in get_db: {e}")
            raise
        finally:
            await session.close()


async def search_users(db: AsyncSession, q: str, limit: int = 100):
    """Асинхронный поиск пользователей"""
    q = (q or "").strip()
    if not q:
        return []

    pattern = f"%{q}%"
    
    stmt = (
        select(User)
        .where(
            or_(
                User.username.like(pattern),
                User.uuid.like(pattern),
                User.funpay_username.like(pattern),
            )
        )
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    return result.scalars().all()


def check_docs_access(request: Request):
    """Синхронная проверка доступа к документации"""
    token = request.headers.get("X-Docs-Token")
    logger.debug(f"Received X-Docs-Token: {token}")
    if token != settings.DOCS_SECRET_TOKEN:
        logger.warning("Access to documentation denied.")
        raise HTTPException(status_code=403, detail="Access to documentation denied.")
    logger.info("Access to documentation granted.")