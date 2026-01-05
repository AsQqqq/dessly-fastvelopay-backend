from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, User, APIToken, RequestAudit, WhitelistedEntry, UpdatePlugin, \
    UserNews, UserNewsRead, PluginMetrics, PluginImportantLog

# ========= Подключения =========

sqlite_engine = create_engine("sqlite:///./users_backup.db", connect_args={"check_same_thread": False})
mysql_engine = create_engine(
    "mysql+pymysql://main:6TEncAe%2AmmKq@jobetacagu.beget.app:3306/main?charset=utf8mb4"
)

SQLiteSession = sessionmaker(bind=sqlite_engine)
MySQLSession = sessionmaker(bind=mysql_engine)

sqlite = SQLiteSession()
mysql = MySQLSession()

# ========= Функция переноса =========

def migrate_table(model):
    print(f"Перенос таблицы {model.__tablename__}...")

    rows = sqlite.query(model).all()
    for row in rows:
        # В MySQL нужно создать НОВЫЙ объект, иначе SQLAlchemy подумает, что он уже в другой сессии
        data = {col.name: getattr(row, col.name) for col in model.__table__.columns}

        new_obj = model(**data)
        mysql.add(new_obj)

    mysql.commit()
    print(f"Готово: перенесено {len(rows)} строк.\n")


# ========= Порядок переноса =========
# Важно: переносить в правильном порядке из-за связей

tables_in_order = [
    User,
    APIToken,
    WhitelistedEntry,

    UserNews,
    UserNewsRead,

    UpdatePlugin,

    PluginMetrics,
    PluginImportantLog,

    RequestAudit,
]

for model in tables_in_order:
    migrate_table(model)

print("✔ Миграция завершена успешно!")
