# Quick Start Guide - Payment Reminder System

## 🚀 Start the System (3 Commands)

```bash
# Terminal 1: Django
cd backend && .\.venv\Scripts\Activate.ps1 && python manage.py runserver

# Terminal 2: Celery Worker
cd backend && .\.venv\Scripts\Activate.ps1 && celery -A config worker -l info

# Terminal 3: Celery Beat
cd backend && .\.venv\Scripts\Activate.ps1 && celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## ⚡ First-Time Setup (1 Click)

1. Log in to FinPilot
2. Click "Reminders" in sidebar
3. Click "Set Up Reminders" button
4. Confirm popup

**Done!** You now have a 4-step reminder workflow:
- Step 1: Invoice issue (day 0)
- Step 2: 7 days before due
- Step 3: 3 days after due
- Step 4: 15 days after due (final notice)

## 📧 Configure Email (for Production)

Add to `backend/.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
EMAIL_FROM=noreply@yourcompany.com
```

## ✅ Approve Reminders

1. Go to "Pending Approvals" tab
2. Click "Preview & Approve"
3. Review email (includes invoice items, payment history, amounts)
4. Add custom messages (optional)
5. Click "Approve & Send"

## 📊 View Results

- **Sent History**: See all dispatched reminders
- **Failed**: See delivery errors
- **Schedules**: Manage steps and timing

## 🔧 Frontend Integration (One-Time)

**File:** `frontend/src/App.tsx`

1. Find: `{page === 'Reminders' && <div>Coming soon...</div>}`
2. Replace with: `{page === 'Reminders' && selectedOrg && <RemindersPage org={selectedOrg} />}`
3. Copy `RemindersPage` component from `FRONTEND_REMINDERS_COMPONENT.tsx`
4. Paste after `SettingsScreen` component
5. Save and restart: `npm run dev`

**See:** `FRONTEND_INTEGRATION_GUIDE.md` for detailed instructions

## 🧪 Test Workflow

```python
# Django shell
python manage.py shell

from core.models import *
from datetime import date, timedelta
from django.contrib.auth import get_user_model

# Get org and user
org = Organization.objects.first()
user = org.memberships.first().user

# Create test customer
customer = Customer.objects.create(
    organization=org,
    name="Test Corp",
    email="test@example.com",
)

# Create invoice due in 7 days
invoice = Invoice.objects.create(
    organization=org,
    customer=customer,
    invoice_number=f"TEST-{date.today().strftime('%Y%m%d')}",
    invoice_date=date.today(),
    due_date=date.today() + timedelta(days=7),
    subtotal_minor=100000,
    tax_minor=18000,
    total_minor=118000,
    status="issued",
    created_by=user,
)

# Trigger scheduling
from reminders.schedule_tasks import schedule_step_reminders
result = schedule_step_reminders()
print(result)  # Should create 2 jobs
```

## 📱 API Quick Reference

```bash
# List pending approvals
GET /api/v1/reminders/jobs-v2/?status=proposed

# Preview reminder
GET /api/v1/reminders/jobs-v2/{job-id}/?include_preview=true

# Approve reminder
POST /api/v1/reminders/jobs-v2/{job-id}/approve/
Body: {"custom_intro": "...", "custom_closing": "..."}

# Reject reminder
POST /api/v1/reminders/jobs-v2/{job-id}/reject/
```

## 🐛 Troubleshooting

**No reminders created?**
- Check schedule is enabled: `ReminderSchedule.objects.filter(enabled=True)`
- Check steps are enabled: `ReminderStep.objects.filter(enabled=True)`
- Check invoice status is "issued"
- Check Celery Beat is running

**Emails not sending?**
- Check Celery worker is running
- Check `EMAIL_*` settings in `.env`
- Check Django console for email output (if using console backend)
- Check `MessageLog.objects.filter(status='failed')` for errors

**Can't approve reminders?**
- Check user role is "owner" or "manager"
- Check invoice isn't already paid
- Check `block_reason` field if status is "blocked"

## 📚 Full Documentation

- **Implementation Details**: `IMPLEMENTATION_COMPLETE.md`
- **API Documentation**: `REMINDER_SYSTEM_IMPLEMENTATION.md`
- **Frontend Guide**: `FRONTEND_INTEGRATION_GUIDE.md`
- **System Status**: `REMINDER_SYSTEM_STATUS.md`

## ✅ Status

- ✅ Backend: 100% Complete
- ✅ Database: Migrations Applied
- ✅ Celery: Configured and Running
- ✅ APIs: Tested and Working
- ⏳ Frontend: Component Ready (Manual Integration Required)

**Next Step:** Integrate frontend component (5 minutes)

---

**Questions?** Check `IMPLEMENTATION_COMPLETE.md` for comprehensive troubleshooting.
