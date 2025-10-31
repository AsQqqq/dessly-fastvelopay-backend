# Используем официальный Python образ
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект в контейнер
COPY . .

# Создаем директории для логов
RUN mkdir -p /app/logs

# Экспорт переменных окружения (если есть .env)
# Здесь .env должен быть в корне проекта
ENV ENV_FILE=/app/.env

# Открываем порт для uvicorn
EXPOSE 8080

# Запуск uvicorn с поддержкой проксирования заголовка X-Forwarded-For
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload", "--proxy-headers"]
