"""
Модуль скачивания обновлений плагинов только для пользователей с токеном
"""

from app.auth import require_access_level, get_current_user_or_api_token
from fastapi import APIRouter, HTTPException, Header, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from app.config import get_config_value
from app.dependencies import get_db
from sqlalchemy.orm import Session
from cl import logger
import os


router = APIRouter(prefix="/plugin", tags=["plugin"])

folder_update = "files"

# Подключаем Jinja2 для шаблонов
templates = Jinja2Templates(directory="app/templates")

# Словарь файлов для платформ
PLATFORM_FILES = {
    "macos_installer": "installer_macos",
    "macos_zip": "MacOS.zip",
    "linux_desktop_installer": "installer_linux",
    "linux_desktop_zip": "Linux.zip",
    "windows_installer": "installer_windows.exe",
    "windows_zip": "Windows.zip"
}


@router.get("/download")
async def download_update(request: Request):
    """
    Страница скачивания плагина
    """

    # Получаем версии из конфигурации
    config_version = get_config_value(key="version_update", default="None")
    config_active_version = get_config_value(key="version_update_active", default="None")

    # Рендерим страницу download.html
    return templates.TemplateResponse(
        "download.html",
        {
            "request": request,
            "config_version": config_version,
            "config_active_version": config_active_version
        }
    )


@router.get("/download_file")
async def download_file(request: Request, platform_file: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """
    Отдаёт файл плагина по платформе/типу файла, если токен валидный.
    """
    logger.info(f"Запрос на скачивание файла: {platform_file}")
    logger.info(f"Заголовок Authorization: {authorization}")

    # Получаем данные пользователя или токена
    auth_data = get_current_user_or_api_token(request, db)
    logger.info(f"Тип авторизации: {auth_data['type']}")

    # Проверка токена на admin
    if auth_data["type"] == "admin":
        logger.warning("Использован админский доступ, запрет на скачивание через этот эндпоинт")
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")

    requester_token = auth_data["token_obj"]
    require_access_level(requester_token, 0)
    logger.info(f"Токен прошёл проверку уровня доступа: {requester_token.id}")

    # Разбор токена из заголовка
    if not authorization or " " not in authorization:
        logger.error("Некорректный заголовок Authorization")
        raise HTTPException(status_code=400, detail="Authorization header is missing or malformed")
    token = authorization.split(" ")[1]
    logger.info(f"Токен из заголовка: {token[:6]}... (скрыто)")

    # Проверяем токен
    require_access_level(requester_token, 0)

    # Получаем актуальную версию из конфигурации
    version = get_config_value("version_update", default=None)
    logger.info(f"Актуальная версия: {version}")
    if not version:
        logger.error("Актуальная версия не найдена в конфигурации")
        raise HTTPException(status_code=404, detail="Актуальная версия не найдена")

    # Проверка платформенного файла
    if platform_file not in PLATFORM_FILES:
        logger.error(f"Неизвестный файл для платформы: {platform_file}")
        raise HTTPException(status_code=400, detail="Неизвестный файл для платформы")

    file_name = PLATFORM_FILES[platform_file]
    file_path = os.path.join(folder_update, version, file_name)
    logger.info(f"Полный путь к файлу: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"Файл не найден на сервере: {file_path}")
        raise HTTPException(status_code=404, detail=f"Файл '{file_name}' не найден на сервере")

    logger.info(f"Файл найден, готовим отдачу: {file_name}")
    return FileResponse(file_path, filename=file_name)