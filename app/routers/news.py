"""
Модуль получения и создания новостей
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
from cl import logger
from app.auth import get_current_user_or_api_token, generate_api_token, require_access_level
from app.database import APIToken, User, UserNews, UserNewsRead
from app.database import get_db
from datetime import datetime


router = APIRouter(prefix="/news", tags=["news"])


# ==============================
# Pydantic-модели
# ==============================

class NewUpdate(BaseModel):
    name: str
    version: str
    description: str


class NewsCreate(BaseModel):
    title: str = Field(..., max_length=255, description="Заголовок новости")
    content: str = Field(..., description="Содержимое новости")
    is_active: bool = Field(default=True, description="Активна ли новость")


# ==============================
# Проверка версии
# ==============================

class NewsOut(BaseModel):
    id: int
    uuid: str
    title: str
    content: str
    timestamp: datetime
    is_active: bool
    is_read: bool

    class Config:
        orm_mode = True


# ==============================
# Роуты
# ==============================


@router.get("/get", response_model=List[NewsOut])
async def get_news(
    request: Request,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Возвращает список активных новостей.
    Добавляет флаг `is_read`, показывающий, читал ли пользователь новость.
    """
    
    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")

    token: APIToken = auth_data["token_obj"]
    user: User = token.user

    logger.info(f"Пользователь {user.username} ({user.id}) запрашивает новости")

    # получаем активные новости
    news_list = db.query(UserNews).filter(UserNews.is_active == True).order_by(UserNews.timestamp.desc()).all()

    # получаем id прочитанных новостей
    read_news_ids = {
        row.news_id for row in db.query(UserNewsRead.news_id)
        .filter(UserNewsRead.user_id == user.id).all()
    }

    # формируем результат
    result = []
    for n in news_list:
        result.append(NewsOut(
            id=n.id,
            uuid=n.uuid,
            title=n.title,
            content=n.content,
            timestamp=n.timestamp,
            is_active=n.is_active,
            is_read=n.id in read_news_ids
        ))

    return result


@router.post("/read/{news_id}")
async def mark_news_as_read(
    news_id: int,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Отмечает новость как прочитанную пользователем.
    Если уже прочитана — возвращает 200 без изменений.
    """
    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")

    token: APIToken = auth_data["token_obj"]
    user: User = token.user

    # проверяем, что новость существует
    news_item = db.query(UserNews).filter(UserNews.id == news_id, UserNews.is_active == True).first()
    if not news_item:
        raise HTTPException(status_code=404, detail="Новость не найдена")

    # проверяем, была ли уже прочитана
    already = db.query(UserNewsRead).filter_by(user_id=user.id, news_id=news_id).first()
    if already:
        logger.info(f"Пользователь {user.username} ({user.id}) уже читал новость {news_id}")
        return {"status": "ok", "message": "Новость уже отмечена как прочитанная"}

    # добавляем запись о прочтении
    new_read = UserNewsRead(user_id=user.id, news_id=news_id)
    db.add(new_read)
    db.commit()
    logger.info(f"Пользователь {user.username} ({user.id}) отметил новость {news_id} как прочитанную")

    return {"status": "ok", "message": "Новость отмечена как прочитанная"}


@router.post("/create")
async def create_news(
    news_data: NewsCreate,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Создание новой новости (только для администратора с access_level >= 2)
    """

    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")

    token: APIToken = auth_data["token_obj"]
    require_access_level(token, 2)

    new_news = UserNews(
        title=news_data.title,
        content=news_data.content,
        is_active=news_data.is_active
    )

    db.add(new_news)
    db.commit()
    db.refresh(new_news)

    logger.info(f"Создана новость {new_news.id}: {new_news.title}")
    return {
        "status": "ok",
        "message": "Новость успешно создана",
        "news": {
            "id": new_news.id,
            "uuid": new_news.uuid,
            "title": new_news.title,
            "content": new_news.content,
            "is_active": new_news.is_active,
            "timestamp": new_news.timestamp
        }
    }


@router.post("/delete/{news_id}")
async def delete_news(
    news_id: int,
    auth_data=Depends(get_current_user_or_api_token),
    db: AsyncSession = Depends(get_db)
):
    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")

    token: APIToken = auth_data["token_obj"]
    require_access_level(token, 2)

    news_item = db.query(UserNews).filter(UserNews.id == news_id).first()
    if not news_item:
        raise HTTPException(status_code=404, detail="Новость не найдена")

    # сначала удаляем все записи о прочтении
    db.query(UserNewsRead).filter(UserNewsRead.news_id == news_id).delete()

    # потом удаляем новость
    db.delete(news_item)
    db.commit()

    logger.info(f"Удалена новость {news_id}")
    return {"status": "ok", "message": f"Новость с ID {news_id} успешно удалена"}