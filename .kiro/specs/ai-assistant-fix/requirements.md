# AI Assistant "Unavailable" Error — Requirements

## Problem

When a user asks the AI assistant a question (e.g. "Which 5 customers owe the most?"), the UI shows:

> **Assistant Unavailable**
> The AI service is temporarily unavailable. Please try again in a moment.
> Request ID: 4e37517c-f3b6-4e21-8be1-989e2ce8269f

## Root Cause Analysis

### Primary cause — Invalid / expired OpenAI API key
The `.env` file has `OPENAI_API_KEY` set, so the `no API key configured` guard in `views.py` passes.
However, when the key is **invalid or expired**, OpenAI returns an `AuthenticationError`.

In the original code, `openai.AuthenticationError` was **not caught separately**; it fell through
to the generic `openai.APIError` handler, which returned `error_type: "llm_api_error"` and HTTP 503.
The frontend mapped this to the generic "temporarily unavailable" message — not actionable for the user.

### Secondary cause — No `OPENAI_MODEL` env var
The model is hardcoded as `gpt-4o-mini` in `views.py` with no override, making key rotation harder
to test without code changes.

### Error chain
```
OpenAI API (401 AuthenticationError)
  → openai.APIError handler in views.py
  → HTTP 503, error_type="llm_api_error"
  → Frontend: "Assistant Unavailable" (generic, not actionable)
```

## Requirements

### R1 — Catch authentication errors explicitly
The backend MUST catch `openai.AuthenticationError` before the generic `openai.APIError` handler
and return a response with:
- `error_type: "llm_unavailable"`
- A message that tells the user the API key is invalid/expired and needs replacing in `.env`

### R2 — Frontend shows actionable message for auth failures
When `error_type === "llm_unavailable"`, the frontend MUST display the backend's `error.message`
directly (which now contains the actionable text) rather than a generic override.

### R3 — Separate `llm_api_error` display from `llm_unavailable`
`llm_api_error` (transient service errors) should continue to say "try again in a moment".
`llm_unavailable` (key missing/invalid, service down) should say "check your API key / config".

### R4 — Valid API key required
The `OPENAI_API_KEY` in `.env` must be a live, creditable OpenAI key.
The user must replace the expired key and restart the backend.

## Acceptance Criteria

- [ ] A bad/expired API key produces the message: "AI service authentication failed. The API key is invalid or expired. Update OPENAI_API_KEY in the .env file and restart the backend."
- [ ] The frontend displays this exact message (not a generic override) in the red error banner.
- [ ] A valid API key produces a correct answer for "Which 5 customers owe the most?"
- [ ] `llm_api_error` still shows "encountered an error, try again."
- [ ] `llm_quota_exceeded` still shows the quota exhausted message.
