"""
Файл конфигурации приложения. Считывает настройки из переменных окружения
и предоставляет их через класс Settings.
"""

import os
from dotenv import load_dotenv
import base64
from cl import logger

load_dotenv()

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

settings = Settings()
