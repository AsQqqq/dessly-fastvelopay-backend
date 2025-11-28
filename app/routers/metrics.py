from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.auth import get_current_user_or_api_token, require_access_level
from app.database import PluginMetrics, PluginImportantLog, APIToken
from app.dependencies import get_db


router = APIRouter(prefix="/metrics", tags=["metrics"])


# -----------------------------
# Pydantic модели
# -----------------------------

class MetricsPayload(BaseModel):
    plugin_id: str
    version: str
    cardinal_version: str | None = None
    os: str | None = None

    tasks_success: int
    tasks_failed: int
    errors_total: int
    uptime: int


class LogEntry(BaseModel):
    level: str      # ERROR / WARNING / CRITICAL
    message: str


class ImportantLogsPayload(BaseModel):
    plugin_id: str
    entries: list[LogEntry]


# -----------------------------
# Метрики (раз в 10 минут)
# -----------------------------

@router.post("/push")
async def push_metrics(
    payload: MetricsPayload,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """Плагин присылает метрики раз в N минут."""

    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=403, detail="Use API token")

    token: APIToken = auth_data["token_obj"]
    require_access_level(token, 0)

    metrics = (
        db.query(PluginMetrics)
        .filter(PluginMetrics.plugin_id == payload.plugin_id)
        .first()
    )

    if not metrics:
        metrics = PluginMetrics(
            plugin_id=payload.plugin_id,
            token_id=token.id
        )
        db.add(metrics)

    metrics.version = payload.version
    metrics.cardinal_version = payload.cardinal_version
    metrics.os = payload.os

    metrics.tasks_success = payload.tasks_success
    metrics.tasks_failed = payload.tasks_failed
    metrics.errors_total = payload.errors_total
    metrics.uptime = payload.uptime

    metrics.last_heartbeat = datetime.utcnow()

    db.commit()

    return {"status": "ok", "updated": payload.plugin_id}


# -----------------------------
# Важные логи
# -----------------------------

@router.post("/logs")
async def push_important_logs(
    payload: ImportantLogsPayload,
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """Принимает только важные логи: ERROR, WARNING, CRITICAL."""

    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=403, detail="Use API token")

    token: APIToken = auth_data["token_obj"]
    require_access_level(token, 0)

    saved = 0
    for entry in payload.entries:
        log = PluginImportantLog(
            plugin_id=payload.plugin_id,
            token_id=token.id,
            level=entry.level,
            message=entry.message
        )
        db.add(log)
        saved += 1

    db.commit()

    return {"status": "ok", "saved": saved}


# -----------------------------
# Онлайн пользователей
# -----------------------------

@router.get("/online")
async def get_online(
    auth_data=Depends(get_current_user_or_api_token),
    db: Session = Depends(get_db)
):
    """Онлайн = плагин присылал метрики ≤ 15 минут назад."""

    if auth_data["type"] != "api_token":
        raise HTTPException(status_code=403, detail="Use API token")

    token: APIToken = auth_data["token_obj"]
    require_access_level(token, 2)

    threshold = datetime.utcnow() - timedelta(minutes=15)

    count = (
        db.query(PluginMetrics)
        .filter(PluginMetrics.last_heartbeat > threshold)
        .count()
    )

    return {"online": count}
