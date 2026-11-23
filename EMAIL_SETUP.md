# Email Notification Setup Guide

## Overview

FinPilot AI sends automated email notifications to customers for invoice reminders. The email system uses:

- **Django's email backend** (SMTP) for actual email sending
- **Celery** for asynchronous task processing
- **Redis** as the Celery message broker

## Architecture

```
Reminder Approval → Celery Task Queued → Celery Worker Processes Task → Email Sent
      (views.py)         (Redis)              (dispatch_tasks.py)      (SMTP)
```

## Why Emails Might Not Send

If emails are not being sent after approval, the most common cause is:

**❌ The Celery worker is not running**

The approval code queues an email task in Redis, but without a Celery worker running, nothing processes that task.

## Required Services

For email notifications to work, you need **THREE** services running:

1. **Backend (Django)** - Port 8000
2. **Celery Worker** - Background task processor
3. **Frontend (Vite)** - Port 5173

Plus Docker services:
- PostgreSQL (port 5432)
- Redis (port 6379)

## Setup Instructions

### 1. Configure SMTP Settings

Edit `backend/.env` and add your SMTP credentials:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_FROM=your-email@gmail.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password-here
EMAIL_USE_TLS=true
```

**For Gmail:**
- Use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password
- Enable 2-factor authentication first
- Generate an app password at: https://myaccount.google.com/apppasswords

### 2. Start All Required Services

#### Option A: Manual Start (Recommended for Development)

Open **THREE** separate PowerShell terminals:

**Terminal 1 - Backend:**
```powershell
cd 'c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\backend'
.\restart-server.ps1
```

**Terminal 2 - Celery Worker (REQUIRED for email):**
```powershell
cd 'c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\backend'
.\start-celery-worker.ps1
```

**Terminal 3 - Frontend:**
```powershell
cd 'c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend'
npm run dev
```

#### Option B: Quick Check

```powershell
# Check if Celery worker is running
Get-Process | Where-Object { $_.ProcessName -eq "python" -and $_.CommandLine -like "*celery*" }

# Check if Redis is running
docker ps --filter "name=redis"
```

## How Email Workflow Works

1. **User approves a reminder job** in the UI
2. Backend endpoint `/api/v1/reminder-jobs/{id}/approve/` is called
3. Job status is updated to `APPROVED` in the database
4. `dispatch_reminder_email.delay(job_id)` is called - this queues a Celery task
5. **Celery worker picks up the task from Redis**
6. Worker executes `dispatch_reminder_email()` in `backend/reminders/dispatch_tasks.py`
7. Email content is rendered using `email_rendering.py`
8. Email is sent via Django's SMTP backend
9. MessageLog and ReminderJob records are updated with sent status

## Testing Email Functionality

### Test 1: Verify SMTP Configuration

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py shell
```

Then in the Django shell:
```python
from django.core.mail import send_mail
from django.conf import settings

# Check settings
print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")

# Send test email
send_mail(
    subject='Test Email from FinPilot AI',
    message='This is a test email.',
    from_email=settings.EMAIL_FROM,
    recipient_list=['your-test-email@example.com'],
    fail_silently=False,
)
print("✓ Email sent successfully!")
```

### Test 2: Verify Celery Worker

With the Celery worker running in a terminal, you should see output like:

```
 -------------- celery@YOUR-COMPUTER v5.x.x
---- **** ----- 
--- * ***  * -- Windows-10-x.x.xxxxx
-- * - **** --- 
- ** ---------- [config]
- ** ---------- .> app:         finpilot:0x...
- ** ---------- .> transport:   redis://127.0.0.1:6379/0
- ** ---------- .> results:     disabled://
- *** --- * --- .> concurrency: 1 (solo)

[tasks]
  . reminders.dispatch_tasks.dispatch_reminder_email
  . reminders.schedule_tasks.schedule_reminder_jobs_for_today
```

### Test 3: Check Message Logs

In the UI or via API:
```
GET /api/v1/messaging/logs/?reminder_job={job_id}
```

Check the `status` field:
- `queued` = Task is waiting for Celery worker
- `sent` = Email was sent successfully
- `failed` = Email sending failed (check error_detail)

## Troubleshooting

### Problem: Email not sent after approval

**Symptoms:**
- Approval succeeds
- Job status changes to `APPROVED`
- But customer doesn't receive email
- MessageLog shows status = `queued` (never `sent`)

**Solution:**
Start the Celery worker:
```powershell
cd backend
.\start-celery-worker.ps1
```

The worker will immediately process any pending queued tasks.

---

### Problem: "Authentication failed" error

**Symptoms:**
Celery worker shows:
```
SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted')
```

**Solution:**
- Use Gmail App Password, not regular password
- Check EMAIL_HOST_USER matches EMAIL_FROM
- Verify EMAIL_HOST_PASSWORD is correct

---

### Problem: Emails go to spam

**Solution:**
- Use a business email domain (not Gmail personal)
- Configure SPF and DKIM DNS records
- Use a transactional email service (SendGrid, AWS SES, etc.)

---

### Problem: Celery worker crashes

**Symptoms:**
Worker terminal shows:
```
Task reminders.dispatch_tasks.dispatch_reminder_email raised unexpected: ...
```

**Solution:**
Check the full error traceback in the Celery worker terminal. Common causes:
- Missing customer email address (check Customer.email field)
- Invalid email template syntax
- Database connection issues

---

## Production Considerations

For production deployment:

1. **Use a dedicated email service:**
   - [SendGrid](https://sendgrid.com/)
   - [AWS SES](https://aws.amazon.com/ses/)
   - [Mailgun](https://www.mailgun.com/)
   - [Postmark](https://postmarkapp.com/)

2. **Run Celery worker as a service:**
   - On Linux: systemd service
   - On Windows: NSSM or Windows Service
   - On Docker: separate container

3. **Enable Celery Beat for scheduled tasks:**
   ```powershell
   celery -A config beat --loglevel=info
   ```

4. **Monitor email delivery:**
   - Check MessageLog table for failures
   - Set up alerts for failed emails
   - Monitor bounce rates

5. **Configure retry logic:**
   The dispatch task already has retry logic built in:
   - Max retries: 5
   - Delay: 30s, 60s, 120s, 240s, 480s (exponential backoff)

## Files Involved

| File | Purpose |
|------|---------|
| `backend/.env` | SMTP credentials configuration |
| `backend/config/settings.py` | Django email settings |
| `backend/config/celery.py` | Celery app configuration |
| `backend/reminders/views.py` | Approval endpoint - queues task |
| `backend/reminders/dispatch_tasks.py` | Celery task - sends email |
| `backend/reminders/email_rendering.py` | Email HTML generation |
| `backend/messaging/models.py` | MessageLog model for tracking |
| `backend/start-celery-worker.ps1` | Helper script to start worker |

## Additional Resources

- [Django Email Documentation](https://docs.djangoproject.com/en/5.0/topics/email/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)

---

**Remember:** The Celery worker MUST be running for emails to send. This is not optional.
