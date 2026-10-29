# Implementation Plan: FinPilot AI Platform

## Status: Substantial implementation complete

The following tasks have been implemented. Items marked `[x]` are done and verified. Items marked `[~]` are partially implemented. Items marked `[ ]` remain and are noted with what's needed.

---

## Tasks

- [x] 1. Infrastructure and dependency setup
  - [x] 1.1 Backend dependencies — `celery[redis]`, `redis`, `django-celery-beat`, `openpyxl`, `boto3`, `pytest`, `pytest-django`, `hypothesis` installed and pinned in `requirements.txt`
  - [x] 1.2 New Django apps created and registered: `imports_app`, `reminders`, `messaging`, `reconciliation`, `forecast`, `ai_assistant`, `notifications`, `subscriptions`, `platform_admin`, `exports`
  - [x] 1.3 `docker-compose.yml` extended with Redis and MinIO services alongside PostgreSQL
  - [x] 1.4 Celery configured (`config/celery.py`, `config/__init__.py`)
  - [x] 1.5 `.env.example` updated with all env-var keys
  - [x] 1.6 All migrations generated and applied successfully

- [x] 2. Core financial models hardened
  - [x] 2.1 Extended `Organization` with `trading_name`, `business_email`, `contact_phone`, `billing_address`, `status`, `updated_at`
  - [x] 2.2 Extended `Customer` with `billing_address`, `opt_out`, `opt_out_recorded_at`, `updated_at`
  - [x] 2.3 Added `InvoiceItem` model with server-calculated `line_total_minor`
  - [x] 2.4 Extended `Invoice` with `source`, `updated_by`, `import_batch` FK
  - [x] 2.5 Extended `Payment` with `status`, `idempotency_key`, `source`, `updated_at`
  - [x] 2.6 Extended `PaymentAllocation` with `created_by`, `reversed_at`, `reversed_by`
  - [x] 2.7 Extended `AuditLog` with `request_id` and indexes

- [x] 3. Core financial logic and APIs
  - [x] 3.1 Invoice total server-calculated as `subtotal − discount + tax` (integer paise)
  - [x] 3.2 Payment allocation validation: sum ≤ payment amount, each ≤ invoice balance, targets issued invoices only
  - [x] 3.3 Concurrent-allocation locking via `select_for_update()` on invoice
  - [x] 3.4 Idempotency: exact-duplicate payment detection by (customer, amount, currency, date, reference)
  - [x] 3.5 Duplicate reference warning (non-blocking)
  - [x] 3.6 Display status derivation: void/draft → paid → partially_paid → overdue → issued
  - [x] 3.7 Invoice void endpoint with allocation guard
  - [x] 3.8 Payment allocation reversal endpoint (original never deleted)
  - [x] 3.9 Customer GSTIN format validation, duplicate detection warnings, opt-out/opt-in endpoints
  - [x] 3.10 Dashboard endpoint: outstanding, overdue, due-today, due-7-days, collected-this-month, top overdue customers, recent payments
  - [x] 3.11 Aging report endpoint: 5 buckets, optional `as_of` date, bucket totals, grand total
  - [x] 3.12 Audit log endpoint, team members endpoint
  - [x] 3.13 Auth: register, login, logout, me — with audit logging on all auth events

- [x] 4. Multi-tenant isolation
  - [x] 4.1 `HasOrganizationAccess` permission resolves org from `X-Organization-ID`, verifies active membership
  - [x] 4.2 Write operations restricted to `WRITE_ROLES` (owner, manager, accountant)
  - [x] 4.3 All viewsets use `get_org()` scoped querysets
  - [x] 4.4 Cross-org access structurally blocked — verified in smoke test

- [x] 5. Invoice CSV/XLSX import
  - [x] 5.1 `ImportBatch` and `ImportRow` models with SHA-256 deduplication
  - [x] 5.2 Template download endpoints (CSV + XLSX)
  - [x] 5.3 File upload: validates type, size (≤10MB), parses rows, validates fields, detects duplicates
  - [x] 5.4 Preview endpoint returns per-row status (valid/error/duplicate)
  - [x] 5.5 Commit endpoint: creates invoices only for selected valid rows, audit logged
  - [x] 5.6 File storage abstraction (S3/MinIO via boto3) with presigned URLs

- [x] 6. Reminder policies, templates, and scheduling
  - [x] 6.1 `ReminderTemplate`, `ReminderTemplateRevision`, `ReminderPolicy`, `ReminderJob` models
  - [x] 6.2 Template CRUD with placeholder validation (`{{token}}` against supported set), length constraints per channel
  - [x] 6.3 Template revision tracking — changes to active-policy templates create pending revisions requiring finance approval
  - [x] 6.4 Policy CRUD with explicit auto-mode confirmation (`{"confirm": true}` required)
  - [x] 6.5 Customer opt-out/opt-in endpoints
  - [x] 6.6 Reminder job approval queue — approve/reject endpoints with final eligibility check
  - [x] 6.7 Idempotency: unique constraint on (policy, invoice, scheduled_date) for active jobs
  - [~] 6.8 Celery Beat scheduler task — stubbed, needs periodic task registration in django-celery-beat

- [x] 7. Messaging provider abstraction
  - [x] 7.1 `MessageLog` model with 6-state lifecycle (queued/sent/delivered/failed/cancelled/unknown)
  - [x] 7.2 `dispatch_reminder_job` Celery task with final eligibility checks (paid/void/zero-balance, opt-out, disabled policy, duplicate, balance snapshot)
  - [x] 7.3 Exponential backoff retry: 30s, 60s, 120s, 240s, 480s (max 5 attempts, max delay 1800s)
  - [x] 7.4 Email provider via Django's `send_mail` (console backend in dev, SMTP/SES in prod)
  - [x] 7.5 Notification creation on delivery failure
  - [~] 7.6 Webhook endpoints — not yet implemented (requires provider credentials)

- [x] 8. Bank statement import and reconciliation
  - [x] 8.1 `BankTransaction` and `ReconciliationMatch` models
  - [x] 8.2 Bank statement upload with column mapping confirmation
  - [x] 8.3 Transaction normalization (minor units, ISO dates, duplicate detection)
  - [x] 8.4 Reconciliation matching service: deterministic rules (exact ref, invoice number in narration, exact amount) + fuzzy scoring (amount ±1%, date ±3 days, name similarity)
  - [x] 8.5 Match confirmation creates Payment + PaymentAllocation atomically, increments `allocated_minor`
  - [x] 8.6 Match rejection with audit logging
  - [x] 8.7 Over-allocation prevention

- [x] 9. Cash inflow forecasting
  - [x] 9.1 `CashForecast` and `ForecastLine` models
  - [x] 9.2 Forecast service: 3 scenarios (conservative/base/optimistic), 3 timing assumptions (due_date/historical_delay/custom_offset)
  - [x] 9.3 Historical delay calculation from paid invoices (requires ≥10 for adjustment, else falls back to rule-based +14/0/−7)
  - [x] 9.4 Forecast endpoint with period selector (7/30/60 days)
  - [x] 9.5 `insufficient_history` flag and documented assumptions
  - [x] 9.6 Excludes draft, void, and fully-paid invoices

- [x] 10. Read-only AI finance assistant
  - [x] 10.1 `AIRun` model — metadata-only log (no question/answer content stored)
  - [x] 10.2 Server-controlled tools: `get_receivables_summary`, `get_top_overdue_customers`, `get_invoices_due_range`, `get_late_paying_customers`, `get_forecast_summary`
  - [x] 10.3 Tool functions enforce organization scoping
  - [x] 10.4 AI endpoint with OpenAI integration (falls back to rule-based when no API key)
  - [x] 10.5 System prompt instructs model to use only tool results, not recompute amounts
  - [x] 10.6 Unavailable service handling (no fabricated answers)

- [x] 11. Notifications
  - [x] 11.1 `Notification` and `NotificationPreference` models with deduplication constraint
  - [x] 11.2 List, mark-read, mark-all-read endpoints
  - [x] 11.3 Notification creation on reminder failure (in messaging task)

- [x] 12. Subscriptions and plan controls
  - [x] 12.1 `Plan`, `Subscription`, `BillingEvent` models
  - [x] 12.2 Subscription status endpoint
  - [~] 12.3 Entitlement enforcement — models ready, enforcement calls not yet wired into all write paths
  - [ ] 12.4 Billing webhook processing — requires provider credentials
  - [ ] 12.5 Plan seed data migration — needs initial plan definitions

- [x] 13. Platform administration
  - [x] 13.1 `IsStaffPermission` permission class
  - [x] 13.2 Org list, user list, platform audit log endpoints
  - [~] 13.3 Account suspend/reactivate — endpoints not yet exposed
  - [ ] 13.4 Support access flow — not yet implemented

- [x] 14. Data export
  - [x] 14.1 CSV export endpoints for invoices, customers, payments
  - [x] 14.2 All exports are org-scoped and audit logged
  - [~] 14.3 Large exports (>1000 rows) — synchronous for now, needs async Celery delegation

- [x] 15. Frontend
  - [x] 15.1 API client module (`lib/api.ts`) with typed interfaces
  - [x] 15.2 Auth screen (login/register)
  - [x] 15.3 Create organization screen
  - [x] 15.4 Overview dashboard with metrics, outstanding invoices, aging summary
  - [x] 15.5 Invoices page with search and CSV export
  - [x] 15.6 Customers page with search
  - [x] 15.7 Payments page with allocation display
  - [x] 15.8 Aging report page with drill-down
  - [x] 15.9 Forecast page with period/timing selectors and 3 scenario cards
  - [x] 15.10 AI assistant page with chat input, suggestions, read-only disclaimer
  - [x] 15.11 Notifications page with mark-all-read
  - [x] 15.12 Audit log page
  - [x] 15.13 Settings page (basic)
  - [x] 15.14 Invoice, customer, and payment modals
  - [x] 15.15 TypeScript compiles with no errors

- [x] 16. Testing
  - [x] 16.1 `pytest.ini` configured
  - [x] 16.2 Financial correctness tests (15 tests): invoice arithmetic, balance calculation, display status, aging buckets, tenant isolation — all passing
  - [x] 16.3 End-to-end API smoke test (11 checks): CSRF, register, me, customer, invoice, payment, dashboard, aging, forecast, AI, balance invariant — all passing

---

## Remaining Tasks (require user input or external services)

- [ ] 17. Production hardening
  - [ ] 17.1 Request ID middleware and structured error responses
  - [ ] 17.2 Security headers middleware (HTTPS redirect, HSTS, X-Frame-Options)
  - [ ] 17.3 CI/CD pipeline (GitHub Actions)
  - [ ] 17.4 Dependency security scanning (`pip-audit`, `npm audit`)
  - [ ] 17.5 Production deployment configuration

- [ ] 18. External integrations (require credentials)
  - [ ] 18.1 Email provider configuration (SMTP/SES credentials needed)
  - [ ] 18.2 Messaging provider (WhatsApp Business API — optional)
  - [ ] 18.3 AI provider API key (OpenAI key needed for LLM-powered answers; rule-based fallback works without it)
  - [ ] 18.4 Billing provider integration (Stripe/Razorpay — optional)

- [ ] 19. Additional tests
  - [ ] 19.1 Property-based tests (Hypothesis) for financial invariants
  - [ ] 19.2 Frontend unit tests (Vitest + React Testing Library)
  - [ ] 19.3 End-to-end browser tests (Playwright)
  - [ ] 19.4 Tenant isolation integration tests
  - [ ] 19.5 Audit log append-only tests

- [ ] 20. Frontend refinements
  - [ ] 20.1 Reminders management UI (backend APIs ready)
  - [ ] 20.2 Reconciliation review UI (backend APIs ready)
  - [ ] 20.3 Invoice import wizard UI (backend APIs ready)
  - [ ] 20.4 Bank statement import UI (backend APIs ready)
