# FinPilot AI - Automated Customer Payment Reminder System

## Implementation Status: BACKEND COMPLETE ✅

---

## What Has Been Implemented

### 1. Database Models & Migrations ✅

**Models Created/Updated:**
- `ReminderSchedule` - Container for multi-step reminder workflows
- `ReminderStep` - Individual reminder stages with offset triggers
- `ReminderJob` - Enhanced with snapshot data, sent data, and custom edits
- `ReminderTemplate` - Email templates (existing, preserved)
- `MessageLog` - Email delivery tracking (existing, preserved)

**Migration Applied:**
- `reminders/0003_reminderschedule_reminderstep_and_more.py` ✅ APPLIED

**Key Features:**
- Snapshot of invoice financials at scheduling time
- Actual sent financials recorded when dispatched
- Support for both offset_from_due and offset_from_issue triggers
- Manual approval workflow with custom intro/closing messages
- Organization-scoped with timezone support

---

### 2. Enhanced Email Rendering System ✅

**File:** `backend/reminders/email_rendering.py`

**Capabilities:**
- ✅ Builds comprehensive context from invoice, customer, organization data
- ✅ Includes **invoice line items** with product descriptions, quantities, prices
- ✅ Includes **payment history** with individual transactions, dates, methods
- ✅ Calculates outstanding balance, overdue days dynamically
- ✅ Generates professional HTML emails with:
  - Responsive table layouts for line items
  - Payment history table
  - Financial summary box
  - Tone-appropriate messaging (issue, friendly, gentle, serious)
  - Business branding (org name, address, contact info)

**Functions:**
- `build_invoice_context()` - Extracts all invoice/payment data
- `render_html_email_body()` - Generates rich HTML email
- `generate_email_subject()` - Creates tone-appropriate subject lines
- `money_display()` - Formats paise to ₹X,XXX.XX

---

### 3. Celery Task Scheduling ✅

**File:** `backend/reminders/schedule_tasks.py`

**Tasks:**
- `schedule_step_reminders()` - **Main hourly task** that:
  - Processes all enabled schedules
  - Evaluates each step's offset trigger
  - Finds eligible invoices
  - Creates ReminderJobs with financial snapshots
  - Respects customer opt-outs and exclusions
  - Prevents duplicates via idempotency keys
  - Creates notifications for manual approval mode
  - Auto-dispatches for automatic mode steps

- `cancel_reminders_for_paid_invoice(invoice_id)` - Cancels pending reminders when invoice is fully paid

- `cleanup_old_reminder_jobs(days=90)` - Housekeeping task

**Features:**
- Organization timezone-aware scheduling
- Business hours respect (send_hour_start, send_hour_end)
- Skip weekdays support
- Idempotency to prevent duplicate reminders
- Balance recalculation before creating jobs

---

### 4. Email Dispatch System ✅

**File:** `backend/reminders/dispatch_tasks.py`

**Task:** `dispatch_reminder_email(job_id)`

**Workflow:**
1. Final eligibility checks (balance > 0, not voided, customer hasn't opted out)
2. Build rich email context with invoice details and payment history
3. Render HTML email using tone-appropriate template
4. Apply custom intro/closing if provided by approver
5. Send via Django's configured email backend
6. Update job status to DISPATCHED with sent snapshot
7. Retry with exponential backoff on failure (max 5 retries)
8. Create notifications for finance users on permanent failure

**Safety Features:**
- Recomputes outstanding balance before sending
- Blocks if invoice paid/voided since approval
- Stores HTML preview in job record
- Comprehensive error logging

---

### 5. REST API Endpoints ✅

**Files:**
- `backend/reminders/schedule_views.py` - New schedule/step viewsets
- `backend/reminders/schedule_serializers.py` - Enhanced serializers
- `backend/reminders/seed_api.py` - Setup endpoint
- `backend/reminders/urls.py` - Updated routes

**New Endpoints:**

#### Schedule Management
- `GET /api/v1/reminders/schedules/` - List schedules
- `POST /api/v1/reminders/schedules/` - Create schedule
- `GET /api/v1/reminders/schedules/{id}/` - Schedule details
- `PATCH /api/v1/reminders/schedules/{id}/` - Update schedule
- `DELETE /api/v1/reminders/schedules/{id}/` - Delete schedule

#### Step Management
- `GET /api/v1/reminders/steps/` - List steps
- `POST /api/v1/reminders/steps/` - Create step
- `GET /api/v1/reminders/steps/{id}/` - Step details
- `PATCH /api/v1/reminders/steps/{id}/` - Update step
- `DELETE /api/v1/reminders/steps/{id}/` - Delete step
- `POST /api/v1/reminders/steps/{id}/activate-auto/` - Enable automatic sending
- `POST /api/v1/reminders/steps/{id}/deactivate-auto/` - Disable automatic sending

#### Reminder Job Management (Enhanced)
- `GET /api/v1/reminders/jobs-v2/` - List jobs with enhanced data
  - Filters: `?status=proposed`, `?invoice=<id>`, `?needs_manual_followup=true`
  - Include preview: `?include_preview=true` (adds full HTML to response)
- `GET /api/v1/reminders/jobs-v2/{id}/` - Job details with preview
- `POST /api/v1/reminders/jobs-v2/{id}/approve/` - Approve and dispatch
  - Body: `{"custom_intro": "...", "custom_closing": "..."}`
- `POST /api/v1/reminders/jobs-v2/{id}/reject/` - Reject reminder
- `POST /api/v1/reminders/jobs-v2/{id}/mark_for_followup/` - Flag for manual action

#### Seeding
- `POST /api/v1/reminders/seed-defaults/` - Create default templates and 4-step schedule

---

### 6. Reminder Lifecycle (Your Exact Requirements) ✅

**Default 4-Step Schedule:**

| Step | Trigger | Offset | Tone | Template | Purpose |
|------|---------|--------|------|----------|---------|
| 1 | Invoice Issue | 0 days from issue_date | issue | Invoice Issue Notification | Initial invoice email |
| 2 | Before Due | -7 days from due_date | friendly | Friendly Payment Reminder | Payment approaching |
| 3 | After Due | +3 days from due_date | gentle | Gentle Overdue Reminder | First overdue notice |
| 4 | After Due | +15 days from due_date | serious | Final Payment Notice | Final notice |

**All steps default to MANUAL approval for safety.**

---

## Email Content Requirements ✅ FULLY IMPLEMENTED

Every reminder email contains:

### Customer & Invoice Header
- Customer name and contact
- Invoice number
- Invoice date
- Due date
- Days overdue (if applicable)
- Days until due (if upcoming)

### Invoice Line Items Table
| Description | Qty | Unit Price | Amount |
|-------------|-----|------------|--------|
| Laptop × 2 | 2 | ₹40,000 | ₹80,000 (+GST 18%) |
| Monitor × 2 | 2 | ₹10,000 | ₹20,000 (+GST 18%) |

### Payment History Table
| Date | Amount Paid | Method | Reference |
|------|-------------|--------|-----------|
| 2026-12-05 | ₹15,000 | Bank Transfer | TXN123456 |
| 2026-12-12 | ₹10,000 | UPI | UPI/789012 |

### Financial Summary
- Subtotal
- Discount (if any)
- Tax (GST)
- **Total Invoice Amount**
- Amount Paid
- **Outstanding Balance** (highlighted if overdue)

### Business Information
- Organization name
- Business email
- Contact phone
- Payment instructions

---

## Configuration & Environment Variables

### Required for Email Sending

Add to `backend/.env`:

```env
# SMTP Configuration (for production email sending)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
EMAIL_FROM=noreply@yourcompany.com

# Celery (already configured)
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
```

### For Development
Currently uses console backend (emails print to terminal). No SMTP needed for testing.

---

## Running the System

### 1. Start Docker Services (PostgreSQL + Redis)
```bash
docker-compose up -d
```

### 2. Start Django Backend (Terminal 1)
```bash
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

### 3. Start Celery Worker (Terminal 2)
```bash
cd backend
.\.venv\Scripts\Activate.ps1
celery -A config worker -l info
```

### 4. Start Celery Beat Scheduler (Terminal 3)
```bash
cd backend
.\.venv\Scripts\Activate.ps1
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 5. Configure Celery Beat Schedule (One-Time Setup)

After starting Celery Beat, configure the hourly task via Django Admin or shell:

```python
python manage.py shell

from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json

# Create hourly schedule
schedule, _ = IntervalSchedule.objects.get_or_create(
    every=1,
    period=IntervalSchedule.HOURS,
)

# Create periodic task
PeriodicTask.objects.get_or_create(
    name='Schedule Payment Reminders (Hourly)',
    defaults={
        'interval': schedule,
        'task': 'reminders.schedule_step_reminders',
        'enabled': True,
    }
)

print("✅ Celery Beat task configured successfully!")
```

---

## First-Time Setup for an Organization

### Option 1: Via API (Recommended)
```bash
# Get your organization ID from the dashboard or:
curl -H "X-Organization-ID: YOUR_ORG_ID" \
     -H "Cookie: sessionid=YOUR_SESSION" \
     -X POST http://localhost:8000/api/v1/reminders/seed-defaults/
```

### Option 2: Via Django Shell
```python
python manage.py shell

from core.models import Organization
from reminders.models import ReminderTemplate, ReminderSchedule, ReminderStep

org = Organization.objects.first()  # Or get by ID
user = org.memberships.filter(role='owner').first().user

# Templates will be created by seed endpoint
# Or manually via admin/API
```

---

## Testing the System

### Scenario 1: Create Test Invoice and Trigger Reminders

```python
from core.models import Organization, Customer, Invoice, InvoiceItem
from datetime import date, timedelta
from django.contrib.auth import get_User_model

User = get_User_model()
org = Organization.objects.first()
user = org.memberships.first().user

# Create customer
customer = Customer.objects.create(
    organization=org,
    name="Test Customer Ltd",
    email="test@example.com",
    payment_terms_days=30,
)

# Create invoice
invoice = Invoice.objects.create(
    organization=org,
    customer=customer,
    invoice_number="INV-TEST-001",
    invoice_date=date.today() - timedelta(days=10),
    due_date=date.today() + timedelta(days=5),  # Due in 5 days
    subtotal_minor=100000,  # ₹1,000
    tax_minor=18000,  # 18% GST
    total_minor=118000,
    status="issued",
    created_by=user,
)

# Add line item
InvoiceItem.objects.create(
    organization=org,
    invoice=invoice,
    description="Test Product",
    quantity=1,
    unit_price_minor=100000,
    line_total_minor=100000,
    gst_rate_bps=1800,  # 18%
    gst_tax_minor=18000,
)

print(f"✅ Created invoice {invoice.invoice_number}")
print(f"   Due in {(invoice.due_date - date.today()).days} days")
```

### Scenario 2: Check Pending Approvals

```bash
curl -H "X-Organization-ID: YOUR_ORG_ID" \
     -H "Cookie: sessionid=YOUR_SESSION" \
     "http://localhost:8000/api/v1/reminders/jobs-v2/?status=proposed"
```

### Scenario 3: Preview and Approve Reminder

```bash
# Get preview with HTML
curl -H "X-Organization-ID: YOUR_ORG_ID" \
     -H "Cookie: sessionid=YOUR_SESSION" \
     "http://localhost:8000/api/v1/reminders/jobs-v2/{JOB_ID}/?include_preview=true"

# Approve and send
curl -H "X-Organization-ID: YOUR_ORG_ID" \
     -H "Cookie: sessionid=YOUR_SESSION" \
     -H "Content-Type: application/json" \
     -X POST \
     -d '{"custom_intro": "We hope you are well."}' \
     "http://localhost:8000/api/v1/reminders/jobs-v2/{JOB_ID}/approve/"
```

---

## Files Created/Modified

### New Files Created ✅
1. `backend/reminders/email_rendering.py` - Rich email generation
2. `backend/reminders/schedule_tasks.py` - Celery scheduling tasks
3. `backend/reminders/dispatch_tasks.py` - Email dispatch with retry logic
4. `backend/reminders/schedule_serializers.py` - Enhanced serializers
5. `backend/reminders/schedule_views.py` - Schedule/Step/Job v2 viewsets
6. `backend/reminders/seed_api.py` - Default setup endpoint
7. `backend/reminders/management/__init__.py` - Management module init
8. `backend/reminders/management/commands/__init__.py` - Commands init

### Modified Files ✅
1. `backend/reminders/models.py` - Already had ReminderSchedule/ReminderStep, verified
2. `backend/reminders/urls.py` - Added new endpoints
3. `backend/reminders/migrations/0003_*.py` - Applied migration

### Files NOT Modified (Preserved) ✅
- `backend/reminders/views.py` - Original views intact
- `backend/reminders/serializers.py` - Original serializers intact
- `backend/reminders/tasks.py` - Original tasks intact (deprecated but preserved)
- `backend/messaging/tasks.py` - Original dispatch logic preserved
- All invoice, payment, customer models - Unchanged
- Frontend - To be implemented next

---

## What Needs to be Done Next

### Frontend Implementation (Reminders Page)

**Required Components:**
1. Schedule management UI (list, create, edit schedules)
2. Step configuration UI (add/edit/reorder steps with offsets)
3. Pending approvals list with filters
4. Email preview modal with HTML rendering
5. Approve/Reject actions with custom message editing
6. Sent reminders history with delivery status
7. Failed deliveries list with retry option
8. Customer exclusion management

**API Integration:**
- Use `/api/v1/reminders/schedules/` for schedule CRUD
- Use `/api/v1/reminders/steps/` for step CRUD
- Use `/api/v1/reminders/jobs-v2/` for approval workflow
- Use `?include_preview=true` to fetch email HTML
- Filter jobs: `?status=proposed`, `?status__in=dispatched,failed`

---

## Security & Safety Features ✅

1. **Manual approval by default** - No auto-send unless explicitly enabled
2. **Organization isolation** - All queries are org-scoped
3. **Permission checks** - Only finance roles can approve/configure
4. **Idempotency** - Duplicate reminders prevented via unique keys
5. **Balance rechecks** - Outstanding amount verified before every send
6. **Customer opt-out** - Respected at all stages
7. **Audit trail** - All actions logged in AuditLog
8. **Error notifications** - Finance users notified of failures
9. **Retry logic** - Exponential backoff for temporary failures
10. **Template escaping** - HTML-safe placeholder substitution

---

## Testing Checklist

- [ ] New invoice creates Step 1 job (invoice issue)
- [ ] 7 days before due creates Step 2 job
- [ ] 3 days after due creates Step 3 job
- [ ] 15 days after due creates Step 4 job
- [ ] Partial payment updates outstanding amount in preview
- [ ] Full payment cancels pending jobs
- [ ] Rejected jobs are not sent
- [ ] Unapproved jobs are not sent
- [ ] Duplicate Celery runs don't create duplicate jobs
- [ ] Failed emails are retried with backoff
- [ ] Different orgs cannot see each other's jobs
- [ ] Email contains line items, payment history, accurate balances
- [ ] Custom intro/closing messages are included in sent email

---

## Known Limitations / Future Enhancements

1. **WhatsApp support** - Model structure ready, provider integration needed
2. **Email templates** - Currently plain text in context, could add Jinja2
3. **Subscription limits** - `check_plan_limits` task exists but not enforced
4. **Analytics** - Could add dashboard for reminder effectiveness
5. **A/B testing** - Could test different subject lines/tones
6. **Customer portal** - Let customers view their invoices/payments online
7. **Payment link generation** - Include payment gateway links in emails
8. **Multi-language** - Currently English only

---

## Troubleshooting

### Reminders not being created
- Check Celery Beat is running
- Check schedule is `enabled=True`
- Check steps are `enabled=True`
- Check customer hasn't opted out
- Check invoice status is "issued" (not draft/void)
- Check offset calculation matches today's date

### Emails not sending
- Check Celery worker is running
- Check EMAIL_* settings in `.env`
- Check console output if using console backend
- Check MessageLog for error_detail
- Check job.block_reason if status=blocked

### "Invoice already paid" block
- This is correct behavior - prevents sending reminder for $0 balance
- Check invoice.allocations to verify payment records

---

## Support & Maintenance

### Monitoring
- Check Celery worker logs for task execution
- Check MessageLog table for delivery status
- Check AuditLog for all reminder actions
- Check Notification table for approval alerts

### Backup Strategy
- ReminderJob records should be retained indefinitely (audit trail)
- MessageLog records should be retained per compliance requirements
- Templates and schedules are configuration data - backup critical

---

## API Response Examples

### Pending Approval (with Preview)
```json
{
  "id": "uuid",
  "status": "proposed",
  "invoice_number": "INV-1001",
  "customer_name": "ABC Corp",
  "customer_email": "finance@abccorp.com",
  "snapshot_outstanding_minor": 105000,
  "current_outstanding_minor": 105000,
  "email_preview_subject": "Payment Reminder: Invoice INV-1001",
  "email_preview_html": "<!DOCTYPE html>...",
  "scheduled_date": "2026-12-24",
  "step_number": 2,
  "step_tone": "friendly"
}
```

### Sent History
```json
{
  "id": "uuid",
  "status": "dispatched",
  "invoice_number": "INV-1001",
  "sent_outstanding_minor": 80000,
  "sent_days_overdue": 0,
  "dispatched_at": "2026-12-24T10:15:00Z",
  "sent_html_body": "<!DOCTYPE html>..."
}
```

---

**Implementation Date:** December 2024  
**Status:** Backend Complete ✅ | Frontend Pending  
**Next Step:** Build Reminders page in React with approval workflow UI
