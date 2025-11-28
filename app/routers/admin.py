"""
Модуль админки
"""

from app.auth import get_current_user_or_api_token, generate_api_token, require_access_level, create_audit_record, get_require_access_level
from app.auth import require_access_level, get_current_user_or_api_token
from fastapi import APIRouter, HTTPException, Header, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from app.config import get_config_value
from app.dependencies import get_db
from sqlalchemy.orm import Session
from cl import logger
import os

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.auth import (
    get_api_token_from_header,
    get_token_from_header,
    require_access_level
)
from app.database import APIToken
from cl import logger


router = APIRouter(prefix="/admin", tags=["admin"])

folder_update = "files"

# Подключаем Jinja2 для шаблонов
templates = Jinja2Templates(directory="app/templates")

@router.get("/login")
async def admin_login_page(request: Request):
    return templates.TemplateResponse(
        "admin/login.html",
        {"request": request}
    )


@router.post("/login")
async def admin_login(
        request: Request,
        token: str = Form(...),
        db: Session = Depends(get_db)
):
    """Проверка API-токена и вход"""

    # Извлечь API токен из формы
    token_obj: APIToken = db.query(APIToken).filter(APIToken.key == token).first()

    if not token_obj:
        raise HTTPException(status_code=401, detail="Неверный токен")

    # Проверка уровня доступа
    require_access_level(token_obj, 1)

    # Успешный вход → ставим куки
    response = RedirectResponse(url="/admin/index", status_code=302)
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=False,
        secure=False,   # поставь True если HTTPS
        samesite="Lax",
        domain=None
    )

    logger.info(f"User {token_obj.user.username} вошел в админку (lvl={token_obj.access_level})")
    return response


@router.get("/index")
async def admin_index(request: Request, db: Session = Depends(get_db)):
    """Главная страница админки"""

    token = request.cookies.get("admin_token")
    if not token:
        return RedirectResponse("/admin/login")

    token_obj = db.query(APIToken).filter(APIToken.key == token).first()
    if not token_obj:
        return RedirectResponse("/admin/login")

    require_access_level(token_obj, 1)

    return templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "user": token_obj.user.username,
            "level": token_obj.access_level
        }
    )


@router.get("/tokens")
async def admin_tokens(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("admin_token")
    if not token:
        return RedirectResponse("/admin/login")

    token_obj = db.query(APIToken).filter(APIToken.key == token).first()
    if not token_obj:
        return RedirectResponse("/admin/login")

    require_access_level(token_obj, 1)

    return templates.TemplateResponse(
        "admin/tokens.html",
        {
            "request": request,
            "user": token_obj.user.username,
            "level": token_obj.access_level
        }
    )


@router.get("/news")
async def admin_news(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("admin_token")
    if not token:
        return RedirectResponse("/admin/login")

    token_obj = db.query(APIToken).filter(APIToken.key == token).first()
    if not token_obj:
        return RedirectResponse("/admin/login")

    require_access_level(token_obj, 1)

    return templates.TemplateResponse(
        "admin/news.html",
        {
            "request": request,
            "user": token_obj.user.username,
            "level": token_obj.access_level
        }
    )


@router.get("/update")
async def admin_update(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("admin_token")
    if not token:
        return RedirectResponse("/admin/login")

    token_obj = db.query(APIToken).filter(APIToken.key == token).first()
    if not token_obj:
        return RedirectResponse("/admin/login")

    require_access_level(token_obj, 1)

    return templates.TemplateResponse(
        "admin/update.html",
        {
            "request": request,
            "user": token_obj.user.username,
            "level": token_obj.access_level
        }
    )