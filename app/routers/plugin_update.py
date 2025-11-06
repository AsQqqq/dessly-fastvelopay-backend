"""
Модуль для версиями обновления
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import re, json
from sqlalchemy.orm import Session
from cl import logger
from app.dependencies import get_db
from app.database import UpdatePlugin
from app.auth import get_current_user_or_api_token, require_access_level
from app.config import get_config_value, CONFIG_PATH, load_config


router = APIRouter(prefix="/update", tags=["update"])


# ==============================
# Pydantic-модели
# ==============================

class NewUpdate(BaseModel):
    name: str
    version: str
    description: str


# ==============================
# Проверка версии
# ==============================

def is_version_higher(new: str, old: str) -> bool:
    """Сравнивает версии в формате x.x.x.x"""
    new_parts = [int(p) for p in new.split(".")]
    old_parts = [int(p) for p in old.split(".")]
    return new_parts > old_parts

VERSION_REGEX = r"^\d+\.\d+\.\d+\.\d+$"


# ==============================
# Роуты
# ==============================

@router.get("/version")
async def get_version(
    request: Request,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """
    Получение информации о версиях плагина:
    - Текущая версия
    - Активная версия
    - История всех версий
    """

    if auth_data["type"] != "api_token":
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )

    # Получаем версии из конфигурации
    config_version = get_config_value(key="version_update", default="None")
    config_active_version = get_config_value(key="version_update_active", default="None")

    # Получаем историю обновлений из базы
    updates_history = db.query(UpdatePlugin).order_by(UpdatePlugin.timestamp.desc()).all()
    history_list = [
        {
            "id": u.id,
            "uuid": u.uuid,
            "name": u.name,
            "description": u.description,
            "last_version": u.last_version,
            "new_version": u.new_version,
            "timestamp": u.timestamp.isoformat()
        }
        for u in updates_history
    ]

    logger.info("Получение версии плагина и истории обновлений")

    return {
        "current_version": config_version,
        "active_version": config_active_version,
        "history": history_list
    }


@router.post("/update")
async def new_update(
    payload: NewUpdate,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db),
):
    """Обновление плагина"""
    
    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=403, detail="Недостаточно прав.")
    
    token = auth_data["token_obj"]
    require_access_level(token, 2)

    name = payload.name.strip() if payload.name else None
    version = payload.version.strip()
    description = payload.description.strip() if payload.description else None

    if not version or not re.match(VERSION_REGEX, version):
        raise HTTPException(status_code=400, detail="Неверный формат версии, ожидается 0.0.0.0")
    
    if not description:
        raise HTTPException(status_code=400, detail="Описание обновления обязательно")

    if not name:
        name = f"Update {version}"

    # Получаем текущую версию из config.json
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        current_version = config.get("version_update", "0.0.0.0")
    except Exception:
        current_version = "0.0.0.0"

    if not is_version_higher(version, current_version):
        raise HTTPException(
            status_code=400,
            detail=f"Новая версия ({version}) должна быть выше текущей ({current_version})"
        )

    # Создаём запись в истории
    update_record = UpdatePlugin(
        name=name,
        description=description,
        last_version=current_version,
        new_version=version,
    )
    db.add(update_record)
    db.commit()
    db.refresh(update_record)

    # Обновляем config.json
    try:
        config["version_update"] = version
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        load_config()  # обновляем кэш
        logger.info(f"Plugin updated: {current_version} -> {version}")
    except Exception as e:
        logger.error(f"Ошибка обновления config.json: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления config: {e}")

    return {
        "message": "Обновление успешно применено",
        "update_id": update_record.id,
        "version": version,
        "name": name,
        "description": description
    }


@router.post("/rollback")
async def rollback_update(
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db),
):
    """
    Откат актуальной версии плагина к активной версии у пользователей.
    """
    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=403, detail="Недостаточно прав.")
    
    token = auth_data["token_obj"]
    require_access_level(token, 2)

    # Получаем версии из конфигурации
    active_version = get_config_value("version_update_active", default="0.0.0.0")
    current_version = get_config_value("version_update", default="0.0.0.0")

    # Проверка, нужно ли откатывать
    if is_version_higher(active_version, current_version):
        raise HTTPException(
            status_code=400,
            detail=f"Откат невозможен: активная версия ({active_version}) выше или равна актуальной ({current_version})"
        )

    # Удаляем записи обновлений, которые были после активной версии
    updates_to_remove = db.query(UpdatePlugin).filter(
        UpdatePlugin.new_version == current_version
    ).all()

    # Откатываем актуальную версию в config.json
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        config["version_update"] = active_version

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        load_config()
        logger.info(f"Rollback: версия {current_version} -> {active_version}")

    except Exception as e:
        logger.error(f"Ошибка при откате config.json: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка отката: {e}")

    for update in updates_to_remove:
        db.delete(update)
    db.commit()

    return {
        "message": "Откат успешно выполнен",
        "rolled_back_to": active_version,
        "removed_update_version": current_version
    }