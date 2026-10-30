# 🔧 Fix: 403 Forbidden & AI Assistant Errors

## Current Errors

1. ❌ `GET /api/v1/auth/me/ 403 (Forbidden)` - Authentication failure
2. ❌ `GET /api/v1/notifications/ 500 (Internal Server Error)` - Backend error
3. ❌ "The AI service is temporarily unavailable" - AI Assistant not working

## Root Cause

The **frontend Vite dev server started BEFORE the backend server** was running. This causes:
- The Vite proxy not connecting to backend properly
- API requests going to wrong endpoint
- Session/authentication not working

## ✅ Complete Fix

### Solution 1: Restart Frontend Dev Server (Recommended)

**Step 1:** Stop the current frontend server
- Go to the terminal running `npm run dev` or `yarn dev`
- Press `Ctrl+C` to stop it

**Step 2:** Restart the frontend server
```powershell
cd "c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend"
npm run dev
```

**Step 3:** Clear browser cache and refresh
- Press `Ctrl+Shift+R` (hard refresh) in your browser
- Or clear cookies for localhost:5173

### Solution 2: Complete Restart (Most Reliable)

Use the restart script I created:

```powershell
cd "c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI"
.\restart-all.ps1
```

---

## 🔍 Why This Happens

### The Vite Proxy Configuration

In `frontend/vite.config.ts`:
```typescript
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8000'
  }
}
```

This tells Vite: "When you see requests to `/api/*`, proxy them to the backend at port 8000"

### The Problem

- **Frontend started:** 11:30 AM (Process ID 10344)
- **Backend started:** 4:47 PM (Process ID varies)
- **Gap:** 5+ hours between starts

When the frontend started, the backend wasn't running, so:
1. Vite couldn't establish proxy connection
2. Requests go directly to `http://localhost:5173/api/...`
3. Vite returns 403/500 because those endpoints don't exist on port 5173

---

## 📋 Verification Steps

### 1. Check Both Servers Are Running

**Backend (Django):**
```powershell
curl.exe http://127.0.0.1:8000/api/v1/auth/csrf/
```
Should return HTTP 200

**Frontend (Vite):**
```powershell
curl.exe http://localhost:5173/
```
Should return HTML

### 2. Check Proxy Is Working

After restarting frontend, check browser Network tab:
- API requests should show `http://localhost:5173/api/v1/...`
- But they're actually proxied to `http://127.0.0.1:8000/api/v1/...`
- Status should be 200 (not 403)

### 3. Test Authentication

1. Go to http://localhost:5173
2. Log in (or register if new user)
3. Check browser console - no 403 errors
4. Dashboard should load with data

### 4. Test AI Assistant

1. Navigate to "AI Assistant" in sidebar
2. Ask: "Which invoices are due next week?"
3. Should get intelligent response (after adding valid OpenAI key)

---

## 🚨 Additional Issues to Fix

### Issue 1: OpenAI API Key Still Needs Update

You still need to add a valid OpenAI API key:

1. Get key from: https://platform.openai.com/api-keys
2. Edit `backend\.env`
3. Replace `YOUR_ACTUAL_OPENAI_API_KEY_HERE` with real key
4. Restart backend server

Without this, AI Assistant will keep showing errors.

### Issue 2: Session Timeout

Your session cookies expire after 30 minutes:
```python
SESSION_COOKIE_AGE = 1800  # 30 minutes in settings.py
```

If you've been idle for 30+ minutes:
1. You'll get 403 errors
2. You need to log in again
3. Browser should automatically redirect to login

---

## 🛠 Common Troubleshooting

### "Still getting 403 after restart"

**Check 1:** Are you logged in?
- Look for login form vs dashboard
- Check browser cookies (F12 → Application → Cookies)
- Should see `sessionid` and `csrftoken` cookies

**Check 2:** Is X-Organization-ID header being sent?
- Open F12 → Network tab
- Click any API request
- Check Request Headers
- Should see `X-Organization-ID: <your-org-id>`

**Check 3:** Backend authentication
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py shell
```
```python
from django.contrib.auth.models import User
User.objects.all()  # Should show your user
```

### "Notifications still showing 500 error"

This happens when not authenticated. After restarting frontend:
1. Log out completely
2. Clear all cookies
3. Log back in
4. Notifications should load

### "AI Assistant still shows error"

Two separate issues:
1. **Backend connection** - Fixed by restarting frontend
2. **OpenAI API key** - You must add valid key in `.env`

---

## 📝 Complete Startup Sequence (For Future)

To avoid this issue in the future, **always start in this order:**

### 1. Start Docker Services
```powershell
docker-compose up -d
```
Wait for healthy status (10-15 seconds)

### 2. Start Backend
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

### 3. Start Frontend (in new terminal)
```powershell
cd frontend
npm run dev
```

### 4. Access Application
Open http://localhost:5173

---

## ✅ Quick Fix Summary

```powershell
# 1. Backend is already running ✓
# 2. Restart frontend:
cd "c:\Users\abhis\OneDrive\Documents\ChatGPT\FinPilot AI\frontend"
# Press Ctrl+C in the terminal running frontend
npm run dev

# 3. In browser: Ctrl+Shift+R to hard refresh

# 4. Update OpenAI key in backend\.env (don't forget this!)
```

---

## 🎯 Expected Results After Fix

- ✅ No 403 errors in browser console
- ✅ Dashboard loads with financial data
- ✅ Notifications load without 500 errors
- ✅ All API requests work
- ⚠️ AI Assistant works (after adding valid OpenAI key)

---

**Current Status:**
- ✅ Backend: Running on port 8000
- ✅ Database: Running (PostgreSQL)
- ✅ Redis: Running
- ⚠️ Frontend: Needs restart to fix proxy
- ❌ OpenAI: Needs valid API key
