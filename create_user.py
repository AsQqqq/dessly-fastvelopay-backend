# scripts/create_admin.py
from app.database import SessionLocal, User
from app.auth import generate_api_token
from cl import logger

def create_admin(username="admin"):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            logger.info("Admin already exists: %s", username)
            return existing
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created admin user: %s (id=%s)", username, user.id)
        # создадим токен уровня 2 (full)
        token_info = generate_api_token(db, name="initial-admin-token", user_id=user.id, access_level=2)
        logger.info("Created API token. Save this token securely (only shown once): %s", token_info["token"])
        return user
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
