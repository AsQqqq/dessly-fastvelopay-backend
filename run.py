"""
Главный файл для запуска сервера FastAPI с использованием Uvicorn.
"""

import uvicorn
from cl import logger


if __name__ == "__main__":
    logger.info("Запуск сервера")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=True)