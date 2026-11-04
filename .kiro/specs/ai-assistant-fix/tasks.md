# Tasks: AI Assistant Fix

## Status

- [x] **T1** — Backend: catch `openai.AuthenticationError` explicitly in `views.py`  
  Added a new `except openai.AuthenticationError` block *before* the generic `openai.APIError` handler.  
  Returns `error_type: "llm_unavailable"` with an actionable message.  
  File: `backend/ai_assistant/views.py`

- [x] **T2** — Frontend: pass backend message through for `llm_unavailable`  
  Changed `askAI` error handler in `App.tsx` so that `llm_unavailable` uses `apiErr?.message`
  (the backend's actionable text) instead of a hardcoded generic string.  
  File: `frontend/src/App.tsx`

- [x] **T3** — Frontend: separate `llm_api_error` from `llm_unavailable` display  
  `llm_api_error` now shows "encountered an error, try again in a moment."  
  `llm_unavailable` now shows the backend message (key invalid/expired) or a key-check fallback.  
  File: `frontend/src/App.tsx`

- [ ] **T4** — Replace expired OpenAI API key  
  The user must:
  1. Get a new key from https://platform.openai.com/api-keys
  2. Replace `OPENAI_API_KEY=...` in `backend/.env`
  3. Restart the backend (`Ctrl+C` → `python manage.py runserver`)

  **This is a manual step — cannot be automated.**

## Verification

After T4 is complete, test with: "Which 5 customers owe the most?"
Expected: a ranked list of customers with overdue balances in ₹.
