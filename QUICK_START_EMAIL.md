# Quick Start: Enable Email Notifications

## TL;DR

Your email code is working fine. You just need to start the Celery worker.

## In 3 Commands:

```powershell
# Terminal 1 - Backend
cd backend
.\restart-server.ps1

# Terminal 2 - Celery Worker (THIS IS WHAT YOU'RE MISSING)
cd backend
.\start-celery-worker.ps1

# Terminal 3 - Frontend
cd frontend
npm run dev
```

## Why?

When you approve a reminder:
1. ✅ Backend queues an email task
2. ❌ **Celery worker must be running to send it**
3. ✅ Email gets delivered

**Without Celery worker = emails queue forever but never send**

## Verify It's Working

After starting the Celery worker, you should see:

```
 -------------- celery@YOUR-COMPUTER v5.x.x
...
[tasks]
  . reminders.dispatch_tasks.dispatch_reminder_email
  . reminders.schedule_tasks.schedule_reminder_jobs_for_today
```

Then approve a reminder and watch the Celery terminal - you'll see:
```
[INFO] Task reminders.dispatch_tasks.dispatch_reminder_email succeeded
```

## Need More Help?

- **Full setup guide:** `EMAIL_SETUP.md`
- **Investigation report:** `EMAIL_FIX_REPORT.md`
- **Test your config:** `cd backend && python test_email_workflow.py your-email@example.com`

## Common Issues

**Problem:** "Authentication failed"  
**Fix:** Use Gmail App Password, not regular password  
**Link:** https://myaccount.google.com/apppasswords

**Problem:** Celery won't start  
**Fix:** Make sure Docker containers are running: `docker-compose up -d`

**Problem:** Still no email  
**Fix:** Check customer has an email address in the database

---

**That's it.** No code changes needed. Just start the worker. 🚀
