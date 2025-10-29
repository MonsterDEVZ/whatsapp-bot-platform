#!/bin/bash

# ==============================================================================
# Setup Environment Variables Script
# ==============================================================================
#
# Интерактивный скрипт для создания .env файла
#
# Usage: ./scripts/setup_env.sh
#
# ==============================================================================

set -e

echo "=================================================="
echo "  WhatsApp Bot Platform - Environment Setup"
echo "=================================================="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для запроса значения
ask() {
    local prompt="$1"
    local default="$2"
    local value

    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " value
        value="${value:-$default}"
    else
        read -p "$prompt: " value
    fi

    echo "$value"
}

# Функция для запроса секретного значения (скрытый ввод)
ask_secret() {
    local prompt="$1"
    local value

    read -s -p "$prompt: " value
    echo ""
    echo "$value"
}

# Функция для запроса yes/no
ask_yn() {
    local prompt="$1"
    local response

    while true; do
        read -p "$prompt (y/n): " response
        case $response in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Введите y или n.";;
        esac
    done
}

echo -e "${YELLOW}Выберите окружение:${NC}"
echo "1) Local Development (локальная разработка)"
echo "2) Production (Railway/Heroku)"
echo ""

read -p "Выбор [1]: " env_choice
env_choice="${env_choice:-1}"

ENV_FILE=".env"

echo ""
echo -e "${GREEN}Создаём $ENV_FILE...${NC}"
echo ""

# ==============================================================================
# DATABASE
# ==============================================================================

echo -e "${YELLOW}=== DATABASE CONFIGURATION ===${NC}"

if [ "$env_choice" = "1" ]; then
    # Local development
    DB_HOST=$(ask "PostgreSQL Host" "localhost")
    DB_PORT=$(ask "PostgreSQL Port" "5432")
    DB_NAME=$(ask "Database Name" "whatsapp_bot_dev")
    DB_USER=$(ask "Database User" "postgres")
    DB_PASSWORD=$(ask_secret "Database Password")
else
    # Production (Railway)
    echo "Для Railway используйте reference на PostgreSQL сервис"
    DB_HOST="\${{Postgres.PGHOST}}"
    DB_PORT="\${{Postgres.PGPORT}}"
    DB_NAME="\${{Postgres.PGDATABASE}}"
    DB_USER="\${{Postgres.PGUSER}}"
    DB_PASSWORD="\${{Postgres.PGPASSWORD}}"
fi

# ==============================================================================
# EVOPOLIKI
# ==============================================================================

echo ""
echo -e "${YELLOW}=== EVOPOLIKI CONFIGURATION ===${NC}"

EVOPOLIKI_INSTANCE_ID=$(ask "EVOPOLIKI WhatsApp Instance ID" "7103000000")
EVOPOLIKI_API_TOKEN=$(ask_secret "EVOPOLIKI API Token")
EVOPOLIKI_PHONE=$(ask "EVOPOLIKI Phone Number (optional)" "+996XXXXXXXXX")

if ask_yn "Включить AI режим для EVOPOLIKI?"; then
    EVOPOLIKI_DIALOG_MODE="true"
    EVOPOLIKI_OPENAI_KEY=$(ask_secret "EVOPOLIKI OpenAI API Key")
    EVOPOLIKI_ASSISTANT_ID=$(ask "EVOPOLIKI Assistant ID")
else
    EVOPOLIKI_DIALOG_MODE="false"
    EVOPOLIKI_OPENAI_KEY=""
    EVOPOLIKI_ASSISTANT_ID=""
fi

# ==============================================================================
# FIVE_DELUXE
# ==============================================================================

echo ""
echo -e "${YELLOW}=== FIVE_DELUXE CONFIGURATION ===${NC}"

if ask_yn "Настроить FIVE_DELUXE tenant?"; then
    FIVE_DELUXE_INSTANCE_ID=$(ask "FIVE_DELUXE WhatsApp Instance ID" "7104000000")
    FIVE_DELUXE_API_TOKEN=$(ask_secret "FIVE_DELUXE API Token")
    FIVE_DELUXE_PHONE=$(ask "FIVE_DELUXE Phone Number (optional)" "+996YYYYYYYYY")

    if ask_yn "Включить AI режим для FIVE_DELUXE?"; then
        FIVE_DELUXE_DIALOG_MODE="true"
        FIVE_DELUXE_OPENAI_KEY=$(ask_secret "FIVE_DELUXE OpenAI API Key")
        FIVE_DELUXE_ASSISTANT_ID=$(ask "FIVE_DELUXE Assistant ID")
    else
        FIVE_DELUXE_DIALOG_MODE="false"
        FIVE_DELUXE_OPENAI_KEY=""
        FIVE_DELUXE_ASSISTANT_ID=""
    fi
    SETUP_FIVE_DELUXE=true
else
    SETUP_FIVE_DELUXE=false
fi

# ==============================================================================
# AIRTABLE
# ==============================================================================

echo ""
echo -e "${YELLOW}=== AIRTABLE CONFIGURATION (optional) ===${NC}"

if ask_yn "Настроить Airtable интеграцию?"; then
    AIRTABLE_API_KEY=$(ask_secret "Airtable API Key")
    AIRTABLE_BASE_ID=$(ask "Airtable Base ID")
    AIRTABLE_TABLE_NAME=$(ask "Airtable Table Name" "Заявки с ботов")
    SETUP_AIRTABLE=true
else
    SETUP_AIRTABLE=false
fi

# ==============================================================================
# SERVER
# ==============================================================================

echo ""
echo -e "${YELLOW}=== SERVER CONFIGURATION ===${NC}"

PORT=$(ask "Server Port" "8000")

if [ "$env_choice" = "1" ]; then
    DEBUG="true"
else
    DEBUG="false"
fi

# ==============================================================================
# WRITE .ENV FILE
# ==============================================================================

echo ""
echo -e "${GREEN}Создаём файл $ENV_FILE...${NC}"

cat > "$ENV_FILE" << EOF
# ==============================================================================
# WhatsApp Bot Platform - Environment Variables
# Generated on $(date)
# ==============================================================================

# ==============================================================================
# DATABASE
# ==============================================================================

DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# ==============================================================================
# EVOPOLIKI
# ==============================================================================

EVOPOLIKI_WHATSAPP_INSTANCE_ID=$EVOPOLIKI_INSTANCE_ID
EVOPOLIKI_WHATSAPP_API_TOKEN=$EVOPOLIKI_API_TOKEN
EVOPOLIKI_WHATSAPP_PHONE_NUMBER=$EVOPOLIKI_PHONE
EVOPOLIKI_ENABLE_DIALOG_MODE=$EVOPOLIKI_DIALOG_MODE
EOF

if [ "$EVOPOLIKI_DIALOG_MODE" = "true" ]; then
    cat >> "$ENV_FILE" << EOF
EVOPOLIKI_OPENAI_API_KEY=$EVOPOLIKI_OPENAI_KEY
EVOPOLIKI_OPENAI_ASSISTANT_ID=$EVOPOLIKI_ASSISTANT_ID
EOF
fi

if [ "$SETUP_FIVE_DELUXE" = true ]; then
    cat >> "$ENV_FILE" << EOF

# ==============================================================================
# FIVE_DELUXE
# ==============================================================================

FIVE_DELUXE_WHATSAPP_INSTANCE_ID=$FIVE_DELUXE_INSTANCE_ID
FIVE_DELUXE_WHATSAPP_API_TOKEN=$FIVE_DELUXE_API_TOKEN
FIVE_DELUXE_WHATSAPP_PHONE_NUMBER=$FIVE_DELUXE_PHONE
FIVE_DELUXE_ENABLE_DIALOG_MODE=$FIVE_DELUXE_DIALOG_MODE
EOF

    if [ "$FIVE_DELUXE_DIALOG_MODE" = "true" ]; then
        cat >> "$ENV_FILE" << EOF
FIVE_DELUXE_OPENAI_API_KEY=$FIVE_DELUXE_OPENAI_KEY
FIVE_DELUXE_OPENAI_ASSISTANT_ID=$FIVE_DELUXE_ASSISTANT_ID
EOF
    fi
fi

if [ "$SETUP_AIRTABLE" = true ]; then
    cat >> "$ENV_FILE" << EOF

# ==============================================================================
# AIRTABLE
# ==============================================================================

AIRTABLE_API_KEY=$AIRTABLE_API_KEY
AIRTABLE_BASE_ID=$AIRTABLE_BASE_ID
AIRTABLE_TABLE_NAME=$AIRTABLE_TABLE_NAME
EOF
fi

cat >> "$ENV_FILE" << EOF

# ==============================================================================
# SERVER
# ==============================================================================

PORT=$PORT
DEBUG=$DEBUG
EOF

echo ""
echo -e "${GREEN}✅ Файл $ENV_FILE создан успешно!${NC}"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo "1. Проверьте файл: cat $ENV_FILE"
echo "2. Запустите PostgreSQL (если локально): docker-compose up -d postgres"
echo "3. Запустите сервер: python main.py"
echo ""
echo -e "${RED}ВАЖНО: Не коммитьте .env файл в Git!${NC}"
echo ""
