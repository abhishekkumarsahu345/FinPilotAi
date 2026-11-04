# FinPilot AI — Project Context

This file is loaded automatically at the start of every Kiro session.
It gives the AI complete project knowledge so you never need to re-explain the codebase.

---

## What This Project Is

**FinPilot AI** is a SaaS receivables and cash-flow management tool for Indian businesses (INR, GST-aware).
It lets users track invoices, customers, payments, aging, forecasts, and reconciliation.
The AI assistant answers plain-English questions about the live financial data using LLM function-calling.

---

## Repository Layout

```
FinPilot AI/
├── backend/                  Django 5.x REST API (Python)
│   ├── config/               Django settings, URLs, WSGI, Celery
│   ├── core/                 Main models: Customer, Invoice, Payment, PaymentAllocation, etc.
│   ├── ai_assistant/         LLM assistant endpoint + tools + schemas
│   ├── forecast/             Cash-inflow forecasting service
│   ├── imports_app/          CSV/XLSX invoice import with batch staging
│   ├── exports/              CSV/XLSX export views
│   ├── reminders/            Reminder jobs and policies (backend done, UI pending)
│   ├── reconciliation/       Bank statement reconciliation (backend done, UI pending)
│   ├── messaging/            Outbound email/WhatsApp webhook handling
│   ├── notifications/        In-app notification model
│   ├── subscriptions/        Subscription/plan model (stub)
│   ├── platform_admin/       Superuser admin views
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env                  ← live secrets (never commit)
│   ├── .env.example          ← template with all keys
│   └── restart-server.ps1
│
├── frontend/                 React 19 + TypeScript + Vite SPA
│   └── src/
│       ├── App.tsx           ← ENTIRE app UI in one file (no sub-pages yet)
│       ├── styles.css        ← all styles in one file
│       ├── lib/api.ts        ← all API calls, ApiError class, type definitions
│       └── main.tsx
│
├── docker-compose.yml        PostgreSQL 16 + Redis 7 (MinIO commented out)
├── restart-all.ps1           Dev startup helper script
└── .kiro/steering/           ← this file lives here
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.12 |
| Web framework | Django 5.x + Django REST Framework 3.x |
| Database | PostgreSQL 16 (via docker-compose) |
| Task queue | Celery + Redis 7 |
| File storage | S3-compatible (MinIO locally — currently commented out in docker-compose) |
| AI/LLM | `openai` Python SDK v1.x (package listed as 3.40.0) — uses `openai.OpenAI(api_key, base_url)` |
| Frontend | React 19, TypeScript, Vite 6, lucide-react icons, Recharts |
| Auth | Django session auth (cookie-based, CSRF protected) |
| Dev startup | Two terminals: backend `python manage.py runserver`, frontend `npm run dev` |

---

## How to Start the Dev Environment

```
# 1. Start Docker services (PostgreSQL + Redis)
docker-compose up -d

# 2. Terminal 1 — Backend (port 8000)
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver

# 3. Terminal 2 — Frontend (port 5173)
cd frontend
npm run dev

# 4. Open browser: http://localhost:5173
```

**After changing `.env`:** restart the backend (`Ctrl+C` then `python manage.py runserver`).
The frontend hot-reloads; only the backend needs a restart for env changes.

Vite proxies `/api/*` to `http://127.0.0.1:8000` — no CORS issue in dev.

---

## Environment Variables (backend/.env)

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret | required |
| `DJANGO_DEBUG` | Debug mode | `true` |
| `DB_*` | PostgreSQL connection | `finpilot / finpilot-local-only` |
| `AI_PROVIDER` | Which LLM to use: `openai` or `grok` | `openai` |
| `OPENAI_API_KEY` | OpenAI key (when `AI_PROVIDER=openai`) | — |
| `GROK_API_KEY` | Grok (xAI) key (when `AI_PROVIDER=grok`) | — |
| `GROK_BASE_URL` | Grok base URL | `https://api.x.ai/v1` |
| `GROK_MODEL` | Grok model name | `grok-beta` |
| `CELERY_BROKER_URL` | Redis broker | `redis://127.0.0.1:6379/0` |
| `EMAIL_*` | SMTP config | console backend by default |

**AI provider switching:** currently only `openai` and `grok` are wired up in `views.py`.
DeepSeek, Groq, Mistral are OpenAI-compatible (same SDK, just change `base_url` + model) but
need a new branch added to `ask_assistant()` in `backend/ai_assistant/views.py`.
A multi-provider refactor was discussed but not yet implemented.

---

## Core Django Models (backend/core/models.py)

- **Organization** — tenant root; every record is scoped to one org
- **Membership** — links User ↔ Organization with a role (owner/member)
- **Customer** — a debtor/client with payment terms, GST number, opt-out flag
- **Invoice** — statuses: `draft`, `issued`, `void`; amounts stored as **paise (minor units)**
- **InvoiceItem** — line items on an invoice
- **Payment** — a received payment (method: bank_transfer, upi, cheque, cash, card, other)
- **PaymentAllocation** — links a Payment to an Invoice (partial payments supported)
- **AuditLog** — immutable log of every write operation

**Important:** All monetary amounts are stored as **integers in paise** (₹1 = 100 paise).
Display: divide by 100 and prefix with `₹`.

---

## AI Assistant Architecture (backend/ai_assistant/)

### Flow
```
POST /api/v1/assistant/  {"question": "...", "session_id": "..."}
  → ask_assistant() view (views.py)
  → _execute_with_function_calling()
      → openai.OpenAI(api_key, base_url).chat.completions.create(
            model=model,
            messages=[system_prompt, user_question],
            tools=TOOL_SCHEMAS,    ← OpenAI function-calling format
            tool_choice="auto"
        )
      → LLM calls tools → backend executes them → results fed back to LLM
      → loop up to 6 iterations → final answer text
  → AIRun.objects.create(...)  ← logs usage/errors
  → return {"answer": "...", "basis": {"tools_used": [...], "request_id": "..."}}
```

### Tools (backend/ai_assistant/tools.py + tool_schemas.py)
13 read-only tools. The LLM decides which to call. No keyword routing.

| Tool | Purpose |
|---|---|
| `query_data` | General-purpose: counts, lists, filters, aggregates, groupby |
| `get_receivables_summary` | Total outstanding / overdue / due-soon amounts |
| `get_top_overdue_customers` | Sorted by overdue balance |
| `get_invoices_due_range` | Invoices due in a date window |
| `get_late_paying_customers` | Chronic late payers |
| `get_forecast_summary` | Cash-inflow projection (delegates to forecast.services) |
| `get_customer_details` | Full profile for one customer |
| `get_customer_invoices` | Invoice history for one customer |
| `get_customer_payments` | Payment history for one customer |
| `get_invoice_details` | Single invoice with line items |
| `get_payment_details` | Single payment with allocations |
| `search_customers` | Partial name search |
| `get_recent_activity` | Latest invoices/payments org-wide |

### Error types returned by backend
| `error_type` | Meaning |
|---|---|
| `llm_quota_exceeded` | API key ran out of credits — change key in `.env`, restart backend |
| `llm_unavailable` | AI service down or no key configured |
| `llm_api_error` | Generic API error from the LLM provider |
| `validation_error` | Bad request (empty question, >2000 chars) |
| `unexpected_error` | Unhandled exception — check backend console logs |

---

## Frontend Architecture (frontend/src/)

### Key files
| File | Contents |
|---|---|
| `App.tsx` | Entire SPA — all pages as inline JSX blocks, all state, all handlers |
| `lib/api.ts` | All `fetch` calls, `ApiError` class, all TypeScript types |
| `styles.css` | All styles in one file |

### Pages (all in App.tsx, switched by `page` state)
Overview, Invoices, Customers, Payments, Aging report, Forecast, AI Assistant,
Notifications, Audit Log, Settings, Reminders (coming soon), Reconciliation (coming soon)

### API error handling pattern
`api.ts` throws `ApiError` (not plain `Error`) for non-OK responses.
`ApiError` carries `.error_type`, `.request_id`, `.status`, `.message`.
The AI assistant `askAI` handler in `App.tsx` reads `error_type` to show
a specific banner (orange for quota, red for other errors) instead of raw JSON.

### Important frontend notes
- `components/`, `hooks/`, `pages/` directories exist but are **empty** — everything is inline in `App.tsx`
- No routing library — page switching is a `useState<Page>()` string
- No state management library — plain `useState` / `useCallback`
- Monetary display helper: `money(paise: number)` in `lib/api.ts` → `₹X.XX`
- Date display helper: `fmtDate(dateStr: string)` in `lib/api.ts`

---

## Known Issues / In-Progress Items

- **Reminders and Reconciliation**: backend fully implemented, UI screens are `coming soon` stubs
- **Conversation history**: `conversation_history` parameter is defined in `_execute_with_function_calling` but not yet implemented (not passed from the view)
- **OpenAI model hardcoded**: `gpt-4o-mini` is hardcoded in `views.py`; no `OPENAI_MODEL` env var exists yet
- **Multi-provider support**: only `openai` and `grok` are wired; DeepSeek/Groq/Mistral need new branches
- **MinIO**: commented out in `docker-compose.yml` due to Docker Hub namespace removal — file upload features need a replacement

---

## Development Conventions

- **Amounts**: always integers, always paise. Never floats for money.
- **Org scoping**: every queryset starts with `.filter(organization=org)` — never forget this
- **Read-only AI**: the AI assistant never creates/updates/deletes anything
- **No keyword routing**: the LLM is the only router in the assistant — no `if "overdue" in question` logic
- **Error handling**: use `ApiError` on the frontend, structured `{error, error_type, request_id}` responses from backend
- **Python venv**: always activate `.venv` before running Django commands: `.\.venv\Scripts\Activate.ps1`
