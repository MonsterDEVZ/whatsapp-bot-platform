# WhatsApp Gateway Dockerfile
# Build context: корневая директория проекта (chatbot_platform/)
FROM python:3.13-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt /app/requirements.txt
COPY apps/whatsapp_gateway/requirements.txt /app/whatsapp_requirements.txt

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r whatsapp_requirements.txt

# Копируем packages/core (нужен для импорта Config и i18n)
COPY packages /app/packages

# Копируем WhatsApp Gateway приложение
COPY apps/whatsapp_gateway /app/apps/whatsapp_gateway

# Создаем директории для .env файлов
RUN mkdir -p /app/apps/evopoliki /app/apps/five_deluxe

# КРИТИЧЕСКИ ВАЖНО: Устанавливаем PYTHONPATH для доступа к packages
ENV PYTHONPATH="/app"

# Остаемся в корневой директории /app
WORKDIR /app

# Открываем порт
EXPOSE 8000

# Запускаем приложение с абсолютным путем от корня проекта
CMD ["python", "-m", "uvicorn", "apps.whatsapp_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
