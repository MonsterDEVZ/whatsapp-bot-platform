# WhatsApp Bot Platform

Multi-tenant WhatsApp chatbot platform using GreenAPI for automotive accessories businesses.

## Features

- **Multi-tenant architecture** - Support multiple clients with isolated configurations
- **AI-powered responses** - Integration with OpenAI Assistants API
- **IVR menu fallback** - Traditional menu system when AI is disabled
- **Tenant isolation** - Each client has independent config, credentials, and AI assistant
- **Database integration** - PostgreSQL with async support
- **Airtable integration** - Save orders to Airtable

---

## Quick Start

### Prerequisites

- Python 3.13+
- PostgreSQL database
- GreenAPI WhatsApp account
- OpenAI API key (optional, for AI mode)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MonsterDEVZ/whatsapp-bot-platform.git
   cd whatsapp-bot-platform
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   # Database
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=whatsapp_bot
   DB_USER=postgres
   DB_PASSWORD=your_password

   # Tenant 1: EVOPOLIKI
   EVOPOLIKI_WHATSAPP_INSTANCE_ID=your_instance_id
   EVOPOLIKI_WHATSAPP_API_TOKEN=your_api_token
   EVOPOLIKI_ENABLE_DIALOG_MODE=true
   EVOPOLIKI_OPENAI_API_KEY=sk-xxx
   EVOPOLIKI_OPENAI_ASSISTANT_ID=asst_xxx

   # Tenant 2: FIVE_DELUXE
   FIVE_DELUXE_WHATSAPP_INSTANCE_ID=your_instance_id
   FIVE_DELUXE_WHATSAPP_API_TOKEN=your_api_token
   FIVE_DELUXE_ENABLE_DIALOG_MODE=false
   ```

5. **Run the server:**
   ```bash
   python main.py
   ```

Server will start on `http://0.0.0.0:8000`

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  GreenAPI Webhook → FastAPI Server                     │
├─────────────────────────────────────────────────────────┤
│  1. Identify tenant by instance_id                     │
│  2. Load tenant-scoped Config                          │
│  3. Route to AI or IVR based on enable_dialog_mode     │
│  4. Send response back via GreenAPI                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Tenant-Scoped Components                              │
├─────────────────────────────────────────────────────────┤
│  - Config (credentials, settings, i18n)                │
│  - AssistantManager (OpenAI API)                       │
│  - FSM State (user sessions)                           │
│  - DialogMemory (conversation history)                 │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
whatsapp_platform/
├── main.py                      # Entry point
├── requirements.txt             # Dependencies
├── Dockerfile                   # Docker configuration
├── Procfile                     # Railway/Heroku deployment
│
├── packages/
│   └── core/                    # Shared core logic
│       ├── config.py            # Tenant-scoped configuration
│       ├── ai/                  # OpenAI integration
│       ├── db/                  # Database models & queries
│       ├── handlers/            # Message handlers
│       ├── keyboards/           # WhatsApp UI components
│       ├── locales/             # Translations (ru, ky)
│       ├── memory.py            # Dialog history
│       └── services/            # External services (Airtable)
│
├── apps/
│   └── whatsapp_gateway/
│       ├── main.py              # FastAPI app
│       ├── whatsapp_handlers.py # WhatsApp-specific handlers
│       ├── ivr_handlers_5deluxe.py
│       ├── state_manager.py     # FSM state management
│       └── smart_input_handler.py
│
└── docs/                        # Documentation
    ├── DEPLOYMENT.md
    ├── GREENAPI_SETUP.md
    └── TENANT_SETUP.md
```

---

## Adding a New Tenant

### 1. Set Environment Variables

```bash
NEW_TENANT_WHATSAPP_INSTANCE_ID=xxx
NEW_TENANT_WHATSAPP_API_TOKEN=xxx
NEW_TENANT_ENABLE_DIALOG_MODE=true
NEW_TENANT_OPENAI_API_KEY=sk-xxx
NEW_TENANT_OPENAI_ASSISTANT_ID=asst_xxx
```

### 2. Create Localization Files

```bash
mkdir -p packages/core/locales/new_tenant
cp packages/core/locales/evopoliki/ru.json packages/core/locales/new_tenant/ru.json
# Edit translations
```

### 3. Add to Tenant List

```python
# apps/whatsapp_gateway/main.py:154
tenants = ["evopoliki", "five_deluxe", "new_tenant"]
```

### 4. Restart Server

The new tenant will be loaded automatically.

---

## Environment Variables Reference

### Required (per tenant)

| Variable | Example | Description |
|----------|---------|-------------|
| `{TENANT}_WHATSAPP_INSTANCE_ID` | `7103XXXXXX` | GreenAPI instance ID |
| `{TENANT}_WHATSAPP_API_TOKEN` | `abc123...` | GreenAPI API token |

### Optional (per tenant)

| Variable | Default | Description |
|----------|---------|-------------|
| `{TENANT}_ENABLE_DIALOG_MODE` | `false` | Enable AI assistant (true/false) |
| `{TENANT}_OPENAI_API_KEY` | - | OpenAI API key (required if AI enabled) |
| `{TENANT}_OPENAI_ASSISTANT_ID` | - | OpenAI Assistant ID (required if AI enabled) |
| `{TENANT}_WHATSAPP_PHONE_NUMBER` | - | WhatsApp number (optional) |

### Global

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `whatsapp_bot` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | - | Database password |
| `AIRTABLE_API_KEY` | - | Airtable API key (optional) |
| `AIRTABLE_BASE_ID` | - | Airtable base ID (optional) |

---

## Deployment

### Railway

1. **Connect GitHub repository**

2. **Add environment variables** in Railway dashboard

3. **Deploy automatically** on push to `main` branch

### Docker

```bash
# Build image
docker build -t whatsapp-bot-platform .

# Run container
docker run -p 8000:8000 \
  -e EVOPOLIKI_WHATSAPP_INSTANCE_ID=xxx \
  -e EVOPOLIKI_WHATSAPP_API_TOKEN=xxx \
  whatsapp-bot-platform
```

---

## Monitoring & Logs

### Health Check

```bash
curl http://localhost:8000/
```

Response:
```json
{
  "status": "ok",
  "service": "WhatsApp Gateway",
  "version": "1.0.0",
  "active_tenants": 2
}
```

### View Logs

```bash
# Railway
railway logs --service whatsapp-bot-platform

# Docker
docker logs <container_id>
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/webhook` | POST | GreenAPI webhook receiver |

---

## Testing

### Manual Testing

Send a message to your WhatsApp number configured in GreenAPI.

Expected flow:
1. GreenAPI receives message
2. Sends webhook to `/webhook` endpoint
3. Server identifies tenant
4. Routes to AI or IVR
5. Sends response back via GreenAPI

### Test AI Response

Send: "Привет"

Expected response: AI greeting + menu options

### Test IVR Menu

If `ENABLE_DIALOG_MODE=false`:

Send: "1"

Expected response: Product catalog

---

## Troubleshooting

### Bot not responding

1. Check GreenAPI webhook is set to your server URL
2. Verify environment variables are set correctly
3. Check server logs for errors

### AI not working

1. Verify `ENABLE_DIALOG_MODE=true`
2. Check OpenAI API key is valid
3. Check Assistant ID exists in OpenAI dashboard
4. Review logs for API errors

### Wrong tenant responding

1. Check `instance_id` matches in GreenAPI and env variables
2. Verify tenant slug is correct (lowercase, underscores for hyphens)

---

## Security

- **Never commit `.env` files** to Git
- **Use environment variables** for all secrets
- **Rotate API tokens** regularly
- **Enable HTTPS** in production
- **Restrict webhook endpoint** to GreenAPI IPs (optional)

---

## License

MIT License - see LICENSE file

---

## Support

For issues and feature requests, please create an issue in the GitHub repository.

**Organization:** [MonsterDEVZ](https://github.com/MonsterDEVZ)

**Repository:** [whatsapp-bot-platform](https://github.com/MonsterDEVZ/whatsapp-bot-platform)
