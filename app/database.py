# """
# Модуль для управления базой данных пользователей, API ключей, аудита запросов и белого списка.
# Используется SQLAlchemy для ORM и SQLite в качестве базы данных.
# """

# from sqlalchemy import (
#     Column, Integer, String, text,
#     ForeignKey, DateTime, Text, Boolean, UniqueConstraint
# )
# from sqlalchemy.sql import func
# from sqlalchemy.orm import declarative_base, relationship
# from sqlalchemy.engine.url import make_url
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
# from urllib.parse import quote
# import uuid
# from cl import logger


# # SQLALCHEMY_DATABASE_URL = "sqlite:///./users.db"
# password = quote("6TEncAe*mmKq")
# SQLALCHEMY_DATABASE_URL = (
#     f"mysql+pymysql://main:{password}@jobetacagu.beget.app:3306/main?charset=utf8mb4"
#     # "mysql+pymysql://main:OT7RFZxox&xu@10.16.0.2:3306/main?charset=utf8mb4"
# )
# url = make_url(SQLALCHEMY_DATABASE_URL)


# connect_args = {}
# if url.get_backend_name() == "sqlite":
#     connect_args = {"check_same_thread": False}


# logger.info(f"Creating database engine with URL: {SQLALCHEMY_DATABASE_URL}")
# # engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, 
#     connect_args=connect_args,
#     pool_size=10,
#     max_overflow=20,
#     pool_recycle=1800,
#     pool_pre_ping=True,
# )
# SessionLocal = sessionmaker(bind=engine, autoflush=False)
# Base = declarative_base()


# # ==============================
# # Таблица пользователей
# # ==============================

# class User(Base):
#     __tablename__ = "users"

#     id = Column(Integer, primary_key=True, index=True)
#     uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
#     username = Column(String(100), unique=True, index=True, nullable=False)
#     funpay_username = Column(String(100), index=True, nullable=True)

#     api_tokens = relationship("APIToken", back_populates="user")
#     whitelist_entries = relationship("WhitelistedEntry", back_populates="user")

#     def __repr__(self):
#         return f"<User(username={self.username}, id={self.id}, uuid={self.uuid})>"

# # ==============================
# # Таблица API ключей
# # ==============================

# class APIToken(Base):
#     __tablename__ = "api_tokens"

#     id = Column(Integer, primary_key=True, index=True)
#     uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
#     name = Column(String(255), nullable=False, index=True)
#     description = Column(Text, nullable=True)
    
#     key = Column(String(255), unique=True, nullable=False, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

#     access_level = Column(Integer, nullable=False, default=0)

#     user = relationship("User", back_populates="api_tokens")
#     audits = relationship("RequestAudit", back_populates="api_token")

#     def __repr__(self):
#         return f"<APIToken(name={self.name}, user_id={self.user_id}, level={self.access_level})>"

# # ==============================
# # Таблица аудита запросов
# # ==============================

# class RequestAudit(Base):
#     __tablename__ = "request_audit"

#     id = Column(Integer, primary_key=True, index=True)
    
#     path = Column(String(255), nullable=False)
#     method = Column(String(10), nullable=False)
#     client_ip = Column(String(45), nullable=False)  # IPv6 max length
    
#     api_token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=True)
#     timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

#     api_token = relationship("APIToken", back_populates="audits")

#     def __repr__(self):
#         return f"<RequestAudit(path={self.path}, client_ip={self.client_ip}, api_token_id={self.api_token_id})>"

# # ==============================
# # Таблица белого списка
# # ==============================

# class WhitelistedEntry(Base):
#     __tablename__ = "whitelisted_entries"

#     id = Column(Integer, primary_key=True, index=True)
    
#     uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
#     value = Column(String(255), unique=True, nullable=False, index=True)
    
#     added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

#     user = relationship("User", back_populates="whitelist_entries")

#     def __repr__(self):
#         return f"<WhitelistedEntry(uuid={self.uuid}, value={self.value}, user_id={self.user_id})>"

# # ==============================
# # История обновлений плагинов
# # ==============================

# class UpdatePlugin(Base):
#     __tablename__ = "update_plugin_history"

#     id = Column(Integer, primary_key=True, index=True)
    
#     uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
#     name = Column(String(255), nullable=False, index=True)
    
#     description = Column(Text, nullable=False)
#     last_version = Column(String(50), nullable=False)
#     new_version = Column(String(50), nullable=False)
    
#     timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

# # ==============================
# # Таблица новостей
# # ==============================

# class UserNews(Base):
#     __tablename__ = "news"

#     id = Column(Integer, primary_key=True, index=True)
    
#     uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
#     title = Column(String(255), nullable=False, index=True)
#     content = Column(Text, nullable=False)
    
#     timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
#     is_active = Column(Boolean, default=True, nullable=False, index=True)
    
#     last_checked = Column(DateTime(timezone=True), nullable=True, index=True)

#     def __repr__(self):
#         return f"<News(id={self.id}, title={self.title!r}, timestamp={self.timestamp})>"

# # ==============================
# # Чтение новостей
# # ==============================

# class UserNewsRead(Base):
#     __tablename__ = "user_news_read"
#     __table_args__ = (
#         UniqueConstraint('user_id', 'news_id', name='uix_user_news'),
#     )

#     id = Column(Integer, primary_key=True, index=True)
    
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
#     news_id = Column(Integer, ForeignKey("news.id"), nullable=False, index=True)
    
#     read_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

#     user = relationship("User", backref="read_news")
#     news = relationship("UserNews", backref="read_by_users")

# # ==============================
# # Метрики плагинов
# # ==============================

# class PluginMetrics(Base):
#     __tablename__ = "plugin_metrics"

#     id = Column(Integer, primary_key=True, index=True)

#     plugin_id = Column(String(64), index=True)
#     token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=False)

#     version = Column(String(50), nullable=False)
#     cardinal_version = Column(String(50), nullable=True)
#     os = Column(String(50), nullable=True)

#     tasks_success = Column(Integer, default=0)
#     tasks_failed = Column(Integer, default=0)
#     errors_total = Column(Integer, default=0)

#     uptime = Column(Integer, default=0)

#     last_heartbeat = Column(DateTime(timezone=True), server_default=func.now())

# # ==============================
# # Важные логи плагинов
# # ==============================

# class PluginImportantLog(Base):
#     __tablename__ = "plugin_important_logs"

#     id = Column(Integer, primary_key=True, index=True)

#     plugin_id = Column(String(64), index=True)
#     token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=False)

#     level = Column(String(20), nullable=False)
#     message = Column(Text, nullable=False)

#     timestamp = Column(DateTime(timezone=True), server_default=func.now())

# # ==============================
# # Инициализация БД
# # ==============================

# logger.info("Creating all tables in the database (if not exist)")
# Base.metadata.create_all(bind=engine)
# logger.info("Database tables created or already exist")

# # Включаем поддержку внешних ключей
# if url.get_backend_name() == "sqlite":
#     with engine.connect() as conn:
#         conn.execute(text("PRAGMA foreign_keys=ON"))


"""
Модуль для управления базой данных пользователей, API ключей, аудита запросов и белого списка.
Используется SQLAlchemy для ORM с асинхронной поддержкой и MySQL/SQLite в качестве базы данных.
"""

from sqlalchemy import (
    Column, Integer, String, text,
    ForeignKey, DateTime, Text, Boolean, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from urllib.parse import quote
import uuid
from cl import logger



# Настройка подключения к базе данных
# "mysql+pymysql://main:OT7RFZxox&xu@10.16.0.2:3306/main?charset=utf8mb4"
password = quote("6TEncAe*mmKq")
SQLALCHEMY_DATABASE_URL = (
    f"mysql+aiomysql://main:{password}@jobetacagu.beget.app:3306/main?charset=utf8mb4"
)
url = make_url(SQLALCHEMY_DATABASE_URL)


# Параметры подключения
connect_args = {}
if url.get_backend_name() == "sqlite":
    # Для SQLite используем aiosqlite
    SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./users.db"
    connect_args = {"check_same_thread": False}


logger.info(f"Creating async database engine with URL: {SQLALCHEMY_DATABASE_URL}")

# Создание асинхронного движка
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_size=25,          # ← Увеличьте с 10 до 25
    max_overflow=50,       # ← Увеличьте с 20 до 50
    pool_recycle=3600,     # ← 1 час (было 1800)
    pool_pre_ping=True,
    echo=False,
)

# Создание асинхронной сессии
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


# ==============================
# Таблица пользователей
# ==============================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    username = Column(String(100), unique=True, index=True, nullable=False)
    funpay_username = Column(String(100), index=True, nullable=True)

    api_tokens = relationship("APIToken", back_populates="user", lazy="selectin")
    whitelist_entries = relationship("WhitelistedEntry", back_populates="user", lazy="selectin")

    def __repr__(self):
        return f"<User(username={self.username}, id={self.id}, uuid={self.uuid})>"


# ==============================
# Таблица API ключей
# ==============================

class APIToken(Base):
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    key = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    access_level = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="api_tokens", lazy="selectin")
    audits = relationship("RequestAudit", back_populates="api_token", lazy="selectin")

    def __repr__(self):
        return f"<APIToken(name={self.name}, user_id={self.user_id}, level={self.access_level})>"


# ==============================
# Таблица аудита запросов
# ==============================

class RequestAudit(Base):
    __tablename__ = "request_audit"

    id = Column(Integer, primary_key=True, index=True)
    
    path = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    client_ip = Column(String(45), nullable=False)  # IPv6 max length
    
    api_token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    api_token = relationship("APIToken", back_populates="audits", lazy="selectin")

    def __repr__(self):
        return f"<RequestAudit(path={self.path}, client_ip={self.client_ip}, api_token_id={self.api_token_id})>"


# ==============================
# Таблица белого списка
# ==============================

class WhitelistedEntry(Base):
    __tablename__ = "whitelisted_entries"

    id = Column(Integer, primary_key=True, index=True)
    
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    value = Column(String(255), unique=True, nullable=False, index=True)
    
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="whitelist_entries", lazy="selectin")

    def __repr__(self):
        return f"<WhitelistedEntry(uuid={self.uuid}, value={self.value}, user_id={self.user_id})>"


# ==============================
# История обновлений плагинов
# ==============================

class UpdatePlugin(Base):
    __tablename__ = "update_plugin_history"

    id = Column(Integer, primary_key=True, index=True)
    
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    
    description = Column(Text, nullable=False)
    last_version = Column(String(50), nullable=False)
    new_version = Column(String(50), nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ==============================
# Таблица новостей
# ==============================

class UserNews(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    title = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    last_checked = Column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self):
        return f"<News(id={self.id}, title={self.title!r}, timestamp={self.timestamp})>"


# ==============================
# Чтение новостей
# ==============================

class UserNewsRead(Base):
    __tablename__ = "user_news_read"
    __table_args__ = (
        UniqueConstraint('user_id', 'news_id', name='uix_user_news'),
    )

    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    news_id = Column(Integer, ForeignKey("news.id"), nullable=False, index=True)
    
    read_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="read_news", lazy="selectin")
    news = relationship("UserNews", backref="read_by_users", lazy="selectin")


# ==============================
# Метрики плагинов
# ==============================

class PluginMetrics(Base):
    __tablename__ = "plugin_metrics"

    id = Column(Integer, primary_key=True, index=True)

    plugin_id = Column(String(64), index=True)
    token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=False)

    version = Column(String(50), nullable=False)
    cardinal_version = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)

    tasks_success = Column(Integer, default=0)
    tasks_failed = Column(Integer, default=0)
    errors_total = Column(Integer, default=0)

    uptime = Column(Integer, default=0)

    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now())


# ==============================
# Важные логи плагинов
# ==============================

class PluginImportantLog(Base):
    __tablename__ = "plugin_important_logs"

    id = Column(Integer, primary_key=True, index=True)

    plugin_id = Column(String(64), index=True)
    token_id = Column(Integer, ForeignKey("api_tokens.id"), nullable=False)

    level = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# ==============================
# Инициализация БД
# ==============================

async def init_db():
    """Асинхронная инициализация базы данных"""
    logger.info("Creating all tables in the database (if not exist)")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Включаем поддержку внешних ключей для SQLite
        if url.get_backend_name() == "sqlite":
            await conn.execute(text("PRAGMA foreign_keys=ON"))
    
    logger.info("Database tables created or already exist")


# ==============================
# Утилиты для работы с сессиями
# ==============================

async def get_db():
    """Генератор асинхронной сессии для dependency injection"""
    async with AsyncSessionLocal() as session:
        yield session


async def close_db():
    """Закрытие всех соединений с базой данных"""
    await engine.dispose()
    logger.info("Database connections closed")