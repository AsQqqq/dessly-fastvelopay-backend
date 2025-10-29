"""
Файл с зависимостями FastAPI-приложения.
Здесь реализована проверка доступа к API через JWT cookie или API-токен с whitelist.
Также реализован лог запросов для аудита.
"""

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from urllib.parse import urlparse
from app.database import WhitelistedEntry, RequestAudit, SessionLocal
from app.auth import get_current_user, get_api_token_from_header
from app.config import settings
from cl import logger

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_docs_access(request: Request):
    token = request.headers.get("X-Docs-Token")
    logger.debug(f"Received X-Docs-Token: {token}")
    if token != settings.DOCS_SECRET_TOKEN:
        logger.warning("Access to documentation denied.")
        raise HTTPException(status_code=403, detail="Access to documentation denied.")
    logger.info("Access to documentation granted.")


def log_request_audit(db: Session, request: Request, api_token_id: int):
    audit = RequestAudit(
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host,
        api_token_id=api_token_id
    )
    db.add(audit)
    db.commit()
    logger.info(f"Audit logged: {audit.path} {audit.client_ip} token_id={api_token_id}")


async def verify_access(request: Request, db: Session = Depends(get_db)):
    """
    Проверка доступа к API: либо JWT cookie, либо X-API-Token + whitelist.
    Возвращает dict с типом доступа.
    """
    # 1) если есть админский JWT — используем
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            username = get_current_user(request)
            logger.debug(f"Admin access by {username}")
            return {"type": "admin", "username": username}
        except HTTPException:
            # упадём к проверке API токена
            pass

    # 2) иначе проверяем API-токен
    token_obj = get_api_token_from_header(request, db)
    if not token_obj:
        logger.warning("No valid API token provided")
        raise HTTPException(status_code=401, detail="API token required")

    # 3) проверяем whitelist по Origin (домен) или IP
    origin = request.headers.get("Origin")
    domain = urlparse(origin).netloc if origin else None
    client_ip = request.client.host

    ip_entry = db.query(WhitelistedEntry).filter(WhitelistedEntry.value == client_ip).first()
    domain_entry = None
    if domain:
        domain_entry = db.query(WhitelistedEntry).filter(WhitelistedEntry.value == domain).first()

    if not ip_entry and not domain_entry:
        log_request_audit(db, request, api_token_id=token_obj.id)
        logger.warning("Valid token used from non-whitelisted source")
        raise HTTPException(status_code=403, detail="Access from this IP/domain is not allowed")

    # Всё ок — логируем и возвращаем
    log_request_audit(db, request, api_token_id=token_obj.id)
    logger.info(f"Access granted for token_id={token_obj.id} from {client_ip} / {domain}")
    return {"type": "api_token", "token_obj": token_obj}
