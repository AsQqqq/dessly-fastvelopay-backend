"""
Файл инициализации FastAPI-приложения в API-only режиме.
Отключена автогенерация документации.
Подключены необходимые роутеры.
"""

from fastapi import FastAPI
from fastapi import Depends, Header, Request
from typing import Optional
from app.routers import white_domains, auth
from app.routers.dessly import steam, account
from fastapi.middleware.cors import CORSMiddleware
from app.dependencies import get_db
from sqlalchemy.orm import Session
from app.auth import require_access_level, get_api_token_from_header, create_audit_record
from cl import logger
import time, json
from app.config import CONFIG_PATH, load_config, config_cache
import collections

# Отключаем автогенерацию docs
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
logger.info("FastAPI application initialized (API-only mode)")

def custom_openapi():
    from fastapi.openapi.utils import get_openapi
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Dessly API",
        version="0.0.1",
        description="API-only service",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app_start_time = time.time()
history = collections.deque(maxlen=5400)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping",
    name="Ping",
    description="Простой роут для проверки доступности сервиса.",
    tags=["Health"])
def ping():
    """Простой роут для проверки доступности сервиса."""
    return {"message": "pong"}


@app.get("/config",
    name="Get Config",
    description="Читает и возвращает текущий конфиг из config.json.",
    tags=["Config"])
def get_config(authorization: Optional[str] = Header(None), request: Request = None, db: Session = Depends(get_db)):
    """
    Читает и возвращает текущий конфиг из config.json.
    Доступ: уровень 2+
    """

    token = get_api_token_from_header(authorization, db)
    require_access_level(token, min_level=2)
    create_audit_record(db, request, token)

    load_config()  # Обновляем кэш перед чтением
    return config_cache


@app.post("/config",
    name="Update Config",
    description="Обновляет настройку в config.json по ключу и значению. Принимает JSON: {\"key\": \"whitelist_enabled\", \"value\": false}.",
    tags=["Config"])
def update_config(data: dict, authorization: Optional[str] = Header(None), request: Request = None, db: Session = Depends(get_db)):
    """
    Обновляет настройку в config.json по ключу и значению.
    Доступ: уровень 2+
    """

    token = get_api_token_from_header(authorization, db)
    require_access_level(token, min_level=2)
    create_audit_record(db, request, token)

    if "key" not in data or "value" not in data:
        return {"error": "Required fields: key and value"}
    
    key = data["key"]
    value = data["value"]
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        config[key] = value
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        load_config()  # Обновляем кэш после записи
        logger.info(f"Config updated: {key} = {value}")
        return {"message": f"Updated {key} to {value}", "config": config_cache}
    except FileNotFoundError:
        logger.warning("config.json not found, creating new")
        config = {key: value}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        load_config()
        return {"message": f"Created config with {key} = {value}", "config": config_cache}
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config.json")
        return {"error": "Invalid JSON in config file"}
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return {"error": str(e)}


# Подключаем роутеры
logger.info("Including routers")
app.include_router(white_domains.router)
app.include_router(auth.router)
app.include_router(steam.router)
app.include_router(account.router)