"""
Модуль для управления белым списком доменов и IP-адресов.
Whitelisting применяется только к level 0 + enabled.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List
import re
import ipaddress
from sqlalchemy.orm import Session
from cl import logger
from app.database import WhitelistedEntry
from app.dependencies import get_db
from app.auth import get_current_user_or_api_token, require_access_level, create_audit_record


router = APIRouter(prefix="/whitelist", tags=["whitelist"])


# ==============================
# Pydantic-модели
# ==============================

class WhiteDomainItem(BaseModel):
    uuid: str
    value: str

    class Config:
        from_attributes = True


class WhiteDomainCreate(BaseModel):
    value: str


# ==============================
# Проверка доменов/IP
# ==============================

def is_valid_domain(domain: str) -> bool:
    if len(domain) > 253:
        return False
    labels = domain.split('.')
    if any(not re.match(r'^[a-zA-Z0-9-]{1,63}$', label) for label in labels):
        return False
    if any(label.startswith('-') or label.endswith('-') for label in labels):
        return False
    if not re.search(r'[a-zA-Z]{2,}$', labels[-1]):
        return False
    return True


def validate_value(value: str) -> bool:
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return is_valid_domain(value)


# ==============================
# Роуты
# ==============================

@router.get("/list", response_model=List[WhiteDomainItem])
def list_white_domains(
    request: Request,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """
    Получить список разрешённых IP/доменов (своих, по user_id).
    Доступ: уровень 0+ (только чтение)
    """

    logger.info(f"Listing whitelist entries for auth type: {auth_data['type']}")
    if auth_data["type"] == "api_token":
        token = auth_data["token_obj"]
        require_access_level(token, 1)
        entries = db.query(WhitelistedEntry).all()
    else:
        return HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )

    # Проверка прав
    if token.access_level == 0:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )

    return [WhiteDomainItem.from_orm(e) for e in entries]


@router.post("/add/{userid}", response_model=WhiteDomainItem, status_code=201)
def add_white_domain(
    item: WhiteDomainCreate,
    request: Request,
    userid: str,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """
    Добавить IP или домен в белый список (для своего user_id).
    Доступ: уровень 1+
    """
    if auth_data["type"] == "api_token":
        token = auth_data["token_obj"]
        require_access_level(token, 1)
        username = f"TOKEN({token.name})"
    else:
        return HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )

    # Проверка прав
    if token.access_level == 0:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )

    if not validate_value(item.value):
        raise HTTPException(status_code=400, detail="Неверный формат IP или домена")

    # Проверка exists per user (теперь matches с composite unique)
    exists = db.query(WhitelistedEntry).filter(WhitelistedEntry.value == item.value).first()
    if exists:
        raise HTTPException(status_code=400, detail="Этот IP или домен уже добавлен")

    new_entry = WhitelistedEntry(value=item.value, user_id=userid)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    create_audit_record(db, request, token)  # Добавили аудит для consistency
    logger.info(f"{username} добавил домен/IP в whitelist: {item.value}")
    return WhiteDomainItem.from_orm(new_entry)


@router.get("/delete/{entry_uuid}", status_code=204)
def delete_white_domain(
    entry_uuid: str,
    request: Request,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """
    Удалить IP или домен из белого списка (по UUID).
    Доступ: уровень 2+
    """
    if auth_data["type"] == "api_token":
        token = auth_data["token_obj"]
        require_access_level(token, 2)
        user_id = token.user_id
        username = f"TOKEN({token.name})"
    else:
        return HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )
    
    # Проверка прав
    if token.access_level == 0:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )

    logger.info(f"{username} пытается удалить запись whitelist с UUID: {entry_uuid}")

    entry = (
        db.query(WhitelistedEntry)
        .filter(WhitelistedEntry.uuid == entry_uuid)
        .first()
    )

    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    db.delete(entry)
    db.commit()
    logger.info(f"{username} удалил домен/IP из whitelist: {entry.value}")
    return {"detail": "Запись успешно удалена"}