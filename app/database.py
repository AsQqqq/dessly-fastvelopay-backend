"""
Модуль для управления базой данных пользователей, API ключей, аудита запросов и белого списка.
Используется SQLAlchemy для ORM и SQLite в качестве базы данных.
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, ForeignKey, DateTime, Text
)
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import uuid
from cl import logger

SQLALCHEMY_DATABASE_URL = "sqlite:///./users.db"

logger.info(f"Creating database engine with URL: {SQLALCHEMY_DATABASE_URL}")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


# ==============================
# Таблица пользователей
# ==============================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    funpay_username = Column(String, unique=False, index=True, nullable=True)

    api_tokens = relationship("APIToken", back_populates="user")
    whitelist_entries = relationship("WhitelistedEntry", back_populates="user")

    def __repr__(self):
        return f"<User(username={self.username}, id={self.id}, uuid={self.uuid})>"


# ==============================
# Таблица API ключей
# ==============================

class APIToken(Base):
    __tablename__ = "api_tokens"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    key = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Новый атрибут: уровень доступа
    access_level = Column(Integer, nullable=False, default=0)  
    """
    Уровни доступа:
    0 — только чтение
    1 — базовые действия (добавлять/удалять whitelist, создавать токены, регистрация новых пользователей, удаление токенов уровня 0)
    2 — полный доступ (удаление токенов (всех), настройка сервера, управление системой)
    """

    user = relationship("User", back_populates="api_tokens")
    audits = relationship("RequestAudit", back_populates="api_token")

    def __repr__(self):
        return f"<APIToken(name={self.name}, user_id={self.user_id}, level={self.access_level})>"


# ==============================
# Таблица аудита запросов
# ==============================

class RequestAudit(Base):
    __tablename__ = "request_audit"
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, nullable=False)
    method = Column(String, nullable=False)
    client_ip = Column(String, nullable=False)
    api_token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    api_token = relationship("APIToken", back_populates="audits")

    def __repr__(self):
        return f"<RequestAudit(path={self.path}, client_ip={self.client_ip}, api_token_id={self.api_token_id})>"


# ==============================
# Таблица белого списка (IP или домены)
# ==============================

class WhitelistedEntry(Base):
    __tablename__ = "whitelisted_entries"
    id = Column(Integer, primary_key=True, index=True)
    value = Column(String, unique=True, nullable=False, index=True)  # ip/domain
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="whitelist_entries")

    def __repr__(self):
        return f"<WhitelistedEntry(value={self.value}, user_id={self.user_id})>"


# ==============================
# Инициализация базы данных
# ==============================

logger.info("Creating all tables in the database (if not exist)")
Base.metadata.create_all(bind=engine)
logger.info("Database tables created or already exist")
