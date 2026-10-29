# FinPilot AI

Receivables and payment recovery workspace for Indian MSMEs. This repository starts with the authoritative financial core: organization-scoped customers, invoices, payments, allocations, receivables, and aging. Money is represented as integer paise throughout.

## Requirements
- Docker Desktop (runs PostgreSQL and Redis)
- Python 3.12 or newer
- Node.js 20+

> **Note:** Make sure Docker Desktop is running (whale icon in your system tray is green) before starting.

---

## How to start the project

You need **three terminals** running at the same time: Docker (infra), backend, and frontend.

### 1. Start the infrastructure (PostgreSQL + Redis)

From the project root:

```powershell
docker compose up -d
```

This starts two containers in the background:
- **PostgreSQL** (database) on port `5432`
- **Redis** (message broker) on port `6379`

Verify they are running:

```powershell
docker compose ps
```

### 2. Start the backend (Django)

In a new terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/api/v1/`.
Swagger docs at `http://127.0.0.1:8000/api/schema/swagger-ui/`.

### 3. Start the frontend (React + Vite)

In a third terminal:

```powershell
cd frontend
npm install   # only needed the first time
npm run dev
```

The web app is available at `http://localhost:5173`.

### 4. (Optional) Start the Celery worker

In a fourth terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
celery -A config worker -l info
```

---

## Why Redis and Celery?

This project does work that shouldn't block the web server — sending reminders, processing invoice imports, running forecasts, and syncing notifications. Celery handles these tasks asynchronously so the API stays fast.

**Celery** is the task queue. You write a Python function, send it to Celery, and it runs in the background instead of making the user wait.

**Redis** is the broker that connects them. When the Django server has a task to run, it drops a message into Redis. The Celery worker picks up that message and runs the task. Redis also stores task results so you can check if a job succeeded or failed.

In short:
- **Redis** = the messenger carrying tasks between Django and Celery
- **Celery** = the worker that runs those tasks in the background

Without Redis, Celery has no way to receive tasks. Without Celery, every slow operation would freeze the API until it finishes. They work as a pair.

---

## First-time setup

If this is your first run, you also need to create the database tables and an admin account:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py makemigrations core
python manage.py migrate
python manage.py createsuperuser
```

At the `createsuperuser` prompts, use your email address as both the username and email so you can sign in with your work email. Organization onboarding is available in the app after signing in. During local development, the API uses Django session authentication and CSRF protection.

## Current feature set
- User accounts, organizations, and organization memberships with role checks.
- Customer register and invoice register.
- Draft/issued invoice lifecycle and server-calculated invoice totals.
- Payments and atomic payment allocations across invoices belonging to the same customer.
- Dashboard totals, invoice aging, and audit trail.
- Responsive navigation and financial tables.

Reminders require approval by default; no outbound provider is wired. AI assistant, bank import, subscription billing, OCR, and automatic messaging are not enabled until providers, data contracts, and credentials are chosen. No payment execution, bank credential collection, or automatic reconciliation is included. Do not use with production financial data until security, backup, and deployment reviews are complete.

See `docs/` for architecture, business rules, data model, and setup decisions. Provider keys belong in environment configuration, never source control.
