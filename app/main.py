"""
Файл инициализации FastAPI-приложения в API-only режиме.
Отключена автогенерация документации.
Подключены необходимые роутеры.
"""

from fastapi import FastAPI
from app.routers import white_domains, auth
from fastapi.middleware.cors import CORSMiddleware
from cl import logger
import time
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

# Подключаем роутеры
logger.info("Including routers")
app.include_router(white_domains.router)
app.include_router(auth.router)