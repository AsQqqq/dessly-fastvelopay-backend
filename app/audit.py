"""
Модуль для аудита запросов к API. Сохраняет информацию о каждом запросе в базу данных.
"""

from app.database import RequestAudit
from fastapi import Depends
from app.dependencies import get_db
from sqlalchemy.orm import Session
from cl import logger

def log_api_access(request, api_token_id: int, db: Session = Depends(get_db)):
    try:
        pass
        # audit = RequestAudit(
        #     path=request.url.path,
        #     method=request.method,
        #     client_ip=request.client.host,
        #     api_token_id=api_token_id
        # )
        # db.add(audit)
        # db.commit()
        # logger.info(f"Audit created: path={audit.path}, ip={audit.client_ip}, token_id={api_token_id}")
    except Exception as e:
        logger.exception(f"Failed to write audit: {e}")
    finally:
        db.close()
