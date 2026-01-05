"""
Файл конфигурации приложения. Считывает настройки из переменных окружения
и предоставляет их через класс Settings.
"""

import os
from dotenv import load_dotenv
import base64, json
from typing import Optional, List, Dict, Any
from threading import Lock
from cl import logger

from functools import lru_cache
from datetime import datetime, timedelta


_config_cache = None
_config_cache_time = None

load_dotenv()

# Роуты для работы с конфигом
CONFIG_PATH = "config.json"
config_cache: Dict[str, Any] = {}  # Глобальный кэш config
config_lock = Lock()  # Для безопасного обновления

class Settings:
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        logger.warning("SECRET_KEY is not set. JWT will not work without it.")

    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    DOCS_SECRET_TOKEN = os.getenv("DOCS_SECRET_TOKEN", "mydocs123")

    # FERNET_KEY должен быть base64 urlsafe 32 байта (как возвращает Fernet.generate_key())
    FERNET_KEY = os.getenv("FERNET_KEY")
    if not FERNET_KEY:
        logger.error("FERNET_KEY is not set. Token encryption/decryption will fail.")
    else:
        try:
            # проверка что это валидная base64 строка
            base64.urlsafe_b64decode(FERNET_KEY)
        except Exception:
            logger.error("FERNET_KEY is set but invalid base64. Generate with Fernet.generate_key().")
    GITHUB_API = os.getenv("GITHUB_API")
    OWNER = os.getenv("OWNER")
    REPO = os.getenv("REPO")

settings = Settings()



def load_config() -> Dict[str, Any]:
    """Загружает config.json в кэш (thread-safe)."""
    global config_cache
    try:
        with config_lock:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                new_config = json.load(f)
            config_cache.update(new_config)
            logger.debug("Config loaded into cache")
    except FileNotFoundError:
        logger.warning("config.json not found")
        config_cache = {}
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config.json")
        config_cache = {}


def get_config_value(key: str, default=None):
    global _config_cache, _config_cache_time
    
    # Кэш на 60 секунд
    if (_config_cache is None or 
        _config_cache_time is None or
        datetime.now() - _config_cache_time > timedelta(seconds=60)):
        
        load_config()
        _config_cache = config_cache
        _config_cache_time = datetime.now()
    
    return _config_cache.get(key, default)


# Инициализируем кэш при старте
load_config()