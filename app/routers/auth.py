"""
Модуль авторизации и проверки API-токенов.
Позволяет пользователю входить по токену, проверять уровень доступа и создавать новых пользователей.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from cl import logger
from app.auth import get_current_user_or_api_token, generate_api_token, require_access_level, create_audit_record
from app.database import APIToken, User
from app.dependencies import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


# ==============================
# Модели Pydantic
# ==============================

class TokenInfoResponse(BaseModel):
    username: str
    token_name: str
    access_level: int
    description: Optional[str] = None

class UserRegisterRequest(BaseModel):
    username: str

class UserRegisterResponse(BaseModel):
    username: str
    uuid: str

class UserListItem(BaseModel):
    username: str
    uuid: str

class APITokenCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    access_level: int = 0

class APITokenListItem(BaseModel):
    name: str
    uuid: str
    access_level: int
    description: Optional[str] = None
    key: str  # Raw token для create (один раз), иначе masked

class UserTokenInfo(BaseModel):
    name: str
    uuid: str
    access_level: int
    description: Optional[str] = None

class UserDetailResponse(BaseModel):
    username: str
    uuid: str
    tokens: List[UserTokenInfo] = []

class APITokenUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    access_level: Optional[int] = None  # только для уровня 2

class UserUpdateRequest(BaseModel):
    username: str


# ==============================
# Пользователи
# ==============================

@router.get("/check", response_model=TokenInfoResponse)
def check_token(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Проверка валидности токена через Authorization: Bearer <token>
    Доступ: любой валидный токен
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    token = auth_data["token_obj"]
    create_audit_record(db, request, token)
    return TokenInfoResponse(
        username=token.user.username,
        token_name=token.name,
        access_level=token.access_level,
        description=token.description,
    )


@router.post("/register", response_model=UserRegisterResponse, status_code=201)
def register_user(
    request_data: UserRegisterRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Регистрация нового пользователя.
    Доступ: уровень 1+
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    token = auth_data["token_obj"]
    require_access_level(token, 1)
    create_audit_record(db, request, token)

    existing = db.query(User).filter(User.username == request_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")

    new_user = User(username=request_data.username)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"{token.user.username} создал нового пользователя: {new_user.username}")

    return UserRegisterResponse(username=new_user.username, uuid=new_user.uuid)


@router.get("/levels", response_model=list)
def list_access_levels(request: Request, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """
    Описание уровней доступа
    Доступ: уровень 2+
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    token = auth_data["token_obj"]
    require_access_level(token, 2)
    create_audit_record(db, request, token)

    return [
        {"access_level": 0, "description": "Только чтение (с whitelist если enabled)"},
        {"access_level": 1, "description": "Базовые действия (создание пользователей, whitelist, без whitelist)"},
        {"access_level": 2, "description": "Полный доступ (удаление токенов, управление системой, без whitelist)"},
    ]


@router.get("/users", response_model=List[UserListItem])
def list_users(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, le=1000),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Получить список пользователей с пагинацией (уровень 1+)"""

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    token = auth_data["token_obj"]
    require_access_level(token, 1)
    create_audit_record(db, request, token)

    users = db.query(User).offset(offset).limit(limit).all()
    return [UserListItem(username=u.username, uuid=u.uuid) for u in users]


@router.get("/user/{user_uuid}", response_model=UserDetailResponse)
def get_user_by_uuid(
    request: Request,
    user_uuid: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Получение информации о пользователе по UUID вместе с его токенами.
    - Уровень 1: показываются только токены уровня 0
    - Уровень 2: показываются все токены
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    token = auth_data["token_obj"]
    require_access_level(token, 1)
    create_audit_record(db, request, token)

    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # фильтрация токенов по уровню запроса
    tokens_query = user.api_tokens
    if token.access_level == 1:
        tokens_query = [t for t in tokens_query if t.access_level == 0]

    tokens_info = [
        UserTokenInfo(
            name=t.name,
            uuid=t.uuid,
            access_level=t.access_level,
            description=t.description
        ) for t in tokens_query
    ]

    return UserDetailResponse(
        username=user.username,
        uuid=user.uuid,
        tokens=tokens_info
    )


# ==============================
# Токены
# ==============================

@router.post("/user/{user_uuid}/token/create", response_model=APITokenListItem, status_code=201)
def create_token_for_user(
    request: Request,
    user_uuid: str,
    token_data: APITokenCreateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Создание нового API токена для пользователя по UUID
    Доступ: уровень 1+
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    token = auth_data["token_obj"]
    require_access_level(token, 1)
    create_audit_record(db, request, token)

    # Находим пользователя
    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Определяем уровень создаваемого токена
    if token.access_level == 1:
        access_level = 0  # для уровня 1 всегда создаем токен уровня 0
    else:
        access_level = token_data.access_level  # уровень 2 может задавать любой уровень

    new_token_info = generate_api_token(
        db,
        name=token_data.name,
        description=token_data.description,
        user_id=user.id,
        access_level=access_level
    )

    logger.info(
        f"{token.user.username} создал токен '{token_data.name}' "
        f"для {user.username} с уровнем {access_level}"
    )

    return APITokenListItem(
        name=new_token_info["name"],
        uuid=new_token_info["uuid"],
        key=new_token_info["token"],  # Raw token (один раз)
        access_level=new_token_info["access_level"],
        description=new_token_info.get("description")
    )



@router.get("/user/{token_uuid}/token/data", response_model=APITokenListItem, status_code=200)
def get_token_data(
    request: Request,
    token_uuid: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Получение информации о токене по его UUID
    - Уровень 1: можно просматривать только токены с access_level=0
    - Уровень 2: можно просматривать все токены
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    requester_token = auth_data["token_obj"]
    require_access_level(requester_token, 1)
    create_audit_record(db, request, requester_token)

    api_token = db.query(APIToken).filter(APIToken.uuid == token_uuid).first()
    if not api_token:
        raise HTTPException(status_code=404, detail="Токен не найден")

    # Проверка прав
    if requester_token.access_level == 1 and api_token.access_level > 0:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )

    return APITokenListItem(
        name=api_token.name,
        uuid=api_token.uuid,
        access_level=api_token.access_level,
        description=api_token.description,
        key=api_token.key
    )


# ==============================
# Удаление токена
# ==============================

@router.get("/token/{token_uuid}", status_code=204)
def delete_token(
    request: Request,
    token_uuid: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):  
    """
    Удаление API токена по его UUID
    Доступ: уровень 1+ (но level 1 не может удалять >0)
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    token_to_delete = db.query(APIToken).filter(APIToken.uuid == token_uuid).first()
    requester_token = auth_data["token_obj"]

    # Проверка прав
    if requester_token.access_level == 1 and token_to_delete.access_level > 0:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав."
        )
    
    require_access_level(requester_token, 1)

    logger.info(f"{requester_token.user.username} пытается удалить токен с UUID: {token_uuid}")

    if not token_to_delete:
        raise HTTPException(status_code=404, detail="Токен не найден")

    db.delete(token_to_delete)
    db.commit()
    logger.info(f"{requester_token.user.username} удалил токен '{token_to_delete.name}'")
    return


# ==============================
# Редактирование токена
# ==============================

@router.put("/token/{token_uuid}/update", response_model=APITokenListItem)
def update_token(
    request: Request,
    token_uuid: str,
    token_data: APITokenUpdateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Редактирование API токена по его UUID
    Доступ: уровень 2+
    """

    auth_data = get_current_user_or_api_token(request, db)

    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    
    requester_token = auth_data["token_obj"]
    require_access_level(requester_token, 2)
    create_audit_record(db, request, requester_token)

    api_token = db.query(APIToken).filter(APIToken.uuid == token_uuid).first()
    
    if token_data.access_level is not None:
        if token_data.access_level not in [1, 2]:
            raise HTTPException(status_code=400, detail="Неверный уровень доступа")
        api_token.access_level = token_data.access_level

    if not api_token:
        raise HTTPException(status_code=404, detail="Токен не найден")
    
    if token_data.name:
        api_token.name = token_data.name
    if token_data.description:
        api_token.description = token_data.description
    

    db.commit()
    db.refresh(api_token)
    logger.info(f"{requester_token.user.username} обновил токен '{api_token.name}'")
    return APITokenListItem(
        name=api_token.name,
        uuid=api_token.uuid,
        access_level=api_token.access_level,
        description=api_token.description,
        key="********"
    )


# ==============================
# Редактирование username пользователя
# ==============================

@router.put("/user/{user_uuid}/update", response_model=UserRegisterResponse)
def update_user(
    request: Request,
    user_uuid: str,
    user_data: UserUpdateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Редактирование username пользователя по его UUID
    Доступ: уровень 2+
    """

    auth_data = get_current_user_or_api_token(request, db)
    if auth_data["type"] == "admin":
        raise HTTPException(status_code=400, detail="Use API token for this endpoint")
    requester_token = auth_data["token_obj"]
    require_access_level(requester_token, 2)
    create_audit_record(db, request, requester_token)

    user = db.query(User).filter(User.uuid == user_uuid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверка на уникальность
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing and existing.id != user.id:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")

    user.username = user_data.username
    db.commit()
    db.refresh(user)
    logger.info(f"{requester_token.user.username} обновил username пользователя '{user.username}'")
    return UserRegisterResponse(username=user.username, uuid=user.uuid)