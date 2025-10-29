# scripts/create_admin.py
from app.database import SessionLocal, User, APIToken
from cl import logger
import secrets
import uuid


def generate_api_token(db, name: str, user_id: int, access_level: int = 0, description: str = None):
    """
    Генерирует и сохраняет API токен в базу данных.
    """
    key = secrets.token_hex(32)  # 64-символьный токен
    token = APIToken(
        uuid=str(uuid.uuid4()),
        name=name,
        description=description,
        key=key,
        user_id=user_id,
        access_level=access_level
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return {
        "id": token.id,
        "name": token.name,
        "token": key,
        "access_level": token.access_level
    }


def create_admin(username: str = "admin"):
    """
    Создаёт пользователя 'admin' и выдаёт ему API-токен с полным доступом (уровень 2).
    Если админ уже существует — токен не создаётся повторно.
    """
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            existing_token = (
                db.query(APIToken)
                .filter(APIToken.user_id == existing_user.id, APIToken.access_level == 2)
                .first()
            )
            if existing_token:
                logger.info(f"Пользователь '{username}' уже существует с токеном уровня 2.")
                return

            # создаём новый токен, если у админа его ещё нет
            token_info = generate_api_token(
                db,
                name="admin-root-token",
                user_id=existing_user.id,
                access_level=2,
                description="Первичный административный токен"
            )
            logger.info(f"Создан новый API токен для существующего админа '{username}': {token_info['token']}")
            return

        # если админа нет — создаём
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Создан пользователь '{username}' (id={user.id})")

        # создаём токен уровня 2 (максимальный доступ)
        token_info = generate_api_token(
            db,
            name="initial-admin-token",
            user_id=user.id,
            access_level=2,
            description="Первичный административный токен"
        )
        logger.info(f"Создан API токен уровня 2. Сохраните его надёжно (показывается один раз): {token_info['token']}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
