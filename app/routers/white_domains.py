"""
Модуль для управления белым списком доменов и IP-адресов.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List
import re
import ipaddress
from sqlalchemy.orm import Session
from cl import logger

from app.database import WhitelistedEntry, User
from app.dependencies import get_db
from app.auth import get_current_user


router = APIRouter(prefix="/whitelist", tags=["whitelist"])


# ==============================
# Pydantic-модели
# ==============================
class WhiteDomainItem(BaseModel):
    id: int
    value: str

    class Config:
        orm_mode = True


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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список разрешённых IP/доменов"""
    entries = db.query(WhitelistedEntry).filter(WhitelistedEntry.user_id == user.id).all()
    return [WhiteDomainItem.from_orm(e) for e in entries]


@router.post("/add", response_model=WhiteDomainItem, status_code=201)
def add_white_domain(
    item: WhiteDomainCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Добавить IP или домен в белый список"""

    if not validate_value(item.value):
        raise HTTPException(status_code=400, detail="Неверный формат IP или домена")

    exists = (
        db.query(WhitelistedEntry)
        .filter(WhitelistedEntry.value == item.value, WhitelistedEntry.user_id == user.id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Этот IP или домен уже добавлен")

    new_entry = WhitelistedEntry(value=item.value, user_id=user.id)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    logger.info(f"Пользователь {user.username} добавил домен/IP в whitelist: {item.value}")
    return WhiteDomainItem.from_orm(new_entry)


@router.delete("/delete/{entry_id}", status_code=204)
def delete_white_domain(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удалить IP или домен из белого списка"""

    entry = (
        db.query(WhitelistedEntry)
        .filter(WhitelistedEntry.id == entry_id, WhitelistedEntry.user_id == user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    db.delete(entry)
    db.commit()
    logger.info(f"Пользователь {user.username} удалил домен/IP из whitelist: {entry.value}")
