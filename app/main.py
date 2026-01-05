"""
Файл инициализации FastAPI-приложения в API-only режиме.
Отключена автогенерация документации.
Подключены необходимые роутеры.
"""

from fastapi import FastAPI
from fastapi import Depends, Header, Request
from typing import Optional

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

from app.routers import white_domains, auth, plugin_update, news, download, metrics, admin
from app.routers.dessly import steam, account, currency
from fastapi.middleware.cors import CORSMiddleware
from app.dependencies import get_db
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from app.auth import (
    require_access_level, 
    get_api_token_from_header, 
    create_audit_record
)
from app.database import init_db, close_db
from fastapi.staticfiles import StaticFiles
from cl import logger
import time, json
from app.config import CONFIG_PATH, load_config, config_cache
import collections

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.ws_manager import WebSocketManager
from app.ws.router import websocket_endpoint
from fastapi import Header
import msgpack


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

# Отключаем автогенерацию docs
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

app.mount("/static", StaticFiles(directory="app/static"), name="static")#, lifespan=lifespan)
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

ws_manager = WebSocketManager()

def unpack(data: bytes) -> dict:
    return msgpack.unpackb(data, raw=False)

# @app.websocket("/ws")
# async def websocket_endpoint(
#     ws: WebSocket,
#     authorization: str = Header(None),
#     db: AsyncSession = Depends(get_db),
# ):
#     # авторизация
#     try:
#         token_obj = await get_api_token_from_header(authorization, db)
#     except Exception:
#         await ws.close(code=1008)  # policy violation
#         return

#     await ws_manager.connect(ws)

#     # отправляем конфиг при подключении
#     from app.config import config_cache
#     await ws.send_bytes(
#         msgpack.packb({
#             "type": "config_full",
#             "data": config_cache
#         }, use_bin_type=True)
#     )

#     try:
#         while True:
#             msg = unpack(await ws.receive_bytes())

#             if msg.get("type") == "ping":
#                 await ws.send_bytes(
#                     msgpack.packb({"type": "pong"}, use_bin_type=True)
#                 )

#     except WebSocketDisconnect:
#         await ws_manager.disconnect(ws)

app.add_api_websocket_route("/ws", websocket_endpoint)

@app.get("/ping",
    name="Ping",
    description="Простой роут для проверки доступности сервиса.",
    tags=["Health"])
async def ping(request: Request):
    """Простой роут для проверки доступности сервиса."""
    return {"message": "pong"}

@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/config",
    name="Get Config",
    description="Читает и возвращает текущий конфиг из config.json.",
    tags=["Config"])
@limiter.limit("100/minute")
async def get_config(authorization: Optional[str] = Header(None), request: Request = None, db: Session = Depends(get_db)):
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
@limiter.limit("100/minute")
async def update_config(data: dict, authorization: Optional[str] = Header(None), request: Request = None, db: Session = Depends(get_db)):
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
app.include_router(plugin_update.router)
app.include_router(currency.router)
app.include_router(news.router)
app.include_router(metrics.router)
app.include_router(admin.router)
app.include_router(download.router)