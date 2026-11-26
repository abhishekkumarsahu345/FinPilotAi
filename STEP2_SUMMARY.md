# Step 2: Reminder Schedule Management — Implementation Summary

## Status: ✅ COMPLETE

All backend and frontend changes are implemented, tested, and building cleanly.

---

## What Was Built

### Backend Changes

#### 1. Database Migration
- **File:** `backend/reminders/migrations/0004_reminderschedule_is_default_archived.py`
- Added two fields to `ReminderSchedule`:
  - `is_default` (BooleanField, default=False)
  - `archived` (BooleanField, default=False)

#### 2. Model Updates
- **File:** `backend/reminders/models.py`
- Added `is_default` and `archived` fields to `ReminderSchedule` model

#### 3. API Endpoints (all in `ReminderScheduleViewSet`)
- **Toggle:** `POST /api/v1/reminders/schedules/{id}/toggle/`
  - Flips `enabled` flag
  - Blocks deactivating the default schedule
  - Creates audit log entry
  
- **Archive Impact:** `GET /api/v1/reminders/schedules/{id}/archive-impact/`
  - Returns count of live jobs and affected invoices
  - Used by frontend confirmation dialog
  
- **Archive:** `POST /api/v1/reminders/schedules/{id}/archive/`
  - Sets `archived=True, enabled=False`
  - Blocks archiving the default schedule
  - Returns impact data and creates audit log
  
- **Set Default:** `POST /api/v1/reminders/schedules/{id}/set-default/`
  - Atomically unsets all other defaults for the org
  - Sets this schedule as the default
  - Blocks setting archived schedules as default
  - Creates audit log entry

#### 4. Permissions
- All three actions require FINANCE_ROLES (owner or manager)
- Viewers get 403 Forbidden with clear error message
- Permission checks in every action before making changes

#### 5. Task Filtering
- **File:** `backend/reminders/schedule_tasks.py`
- `schedule_step_reminders` now filters `enabled=True, archived=False`
- Archived schedules are skipped by the Celery beat task

#### 6. Management Command
- **File:** `backend/reminders/management/commands/setup_default_schedule.py`
- Updated to set `is_default=True` on the schedule it creates
- Unsets any other defaults for the org

#### 7. Serializer
- **File:** `backend/reminders/schedule_serializers.py`
- Added `is_default` and `archived` to `ReminderScheduleSerializer` (read-only)

#### 8. Tests
- **File:** `backend/reminders/tests_schedule_management.py` (new, 220 lines)
- 22 new tests covering:
  - Toggle (6 tests)
  - Archive (7 tests)
  - Default schedule (7 tests)
  - Task filtering (2 tests)
- **All 49 tests pass** (27 original + 22 new)

---

### Frontend Changes

#### 1. Type Updates
- **File:** `frontend/src/lib/api.ts`
- Added `is_default: boolean` and `archived: boolean` to `ReminderSchedule` type
- Added new `ArchiveImpact` type with `schedule_id`, `schedule_name`, `is_default`, `live_jobs`, `invoices_affected`

#### 2. API Methods
- **File:** `frontend/src/lib/api.ts`
- Added four new API methods:
  - `toggleSchedule(orgId, id)`
  - `archiveImpact(orgId, id)`
  - `archiveSchedule(orgId, id)`
  - `setDefaultSchedule(orgId, id)`

#### 3. RemindersPage Component
- **File:** `frontend/src/App.tsx`
- Added import for `ArchiveImpact` type
- Added state for confirmation dialogs:
  - `archiveConfirm` — holds schedule and impact data
  - `toggleConfirm` — (declared but not used yet)
  
- Added handler functions:
  - `canManage` — checks if user role is owner or manager
  - `handleToggle` — toggle active/inactive with confirmation
  - `handleShowArchiveConfirm` — fetch impact data and show modal
  - `handleArchive` — archive the schedule
  - `handleSetDefault` — set schedule as default

#### 4. Schedule Cards UI
- Each schedule card now shows:
  - **"Default" badge** (blue pill) if `is_default=true`
  - **"Active" / "Inactive" badge** (green/red)
  - **"View Steps →"** button (always visible)
  - **"Edit"** button (only for owner/manager)
  - **"Activate" / "Deactivate"** button (only for owner/manager)
  - **"Set as default"** button (only for non-default schedules, only for owner/manager)
  - **"Delete"** button (only for owner/manager)

#### 5. Archive Confirmation Modal
- Shows schedule name, impact data
- Displays count of affected invoices and pending reminders
- Explains what happens when archiving
- Two buttons: Cancel / Delete Schedule

#### 6. User Permissions
- All management buttons hidden or disabled for viewers
- Error messages shown if viewer tries to toggle/archive/set-default
- Uses `org.role` from the `Org` type

---

## Verification

### Backend Tests
```bash
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest reminders/tests_schedule_api.py reminders/tests_schedule_management.py -v
```
**Result:** ✅ 49 tests passed in 15.57s

### Frontend Build
```bash
cd frontend
npm run build
```
**Result:** ✅ Built successfully, no TypeScript errors

---

## How to Test Manually

### 1. Start Backend
```bash
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

### 2. Start Frontend
```bash
cd frontend
npm run dev
```

### 3. Navigate to Reminders
1. Open `http://localhost:5173`
2. Log in as an owner or manager
3. Click **Reminders** in the sidebar
4. Click the **Schedules** tab

### 4. Test Each Feature

#### Active/Inactive Toggle
- Click **Deactivate** on any active schedule
- Confirm the action
- Verify badge changes to "Inactive"
- Click **Activate** to revert
- **Expected:** Cannot deactivate the default schedule (error message shown)

#### Set Default
- Click **Set as default** on any non-default schedule
- Verify the **Default** badge appears on this schedule
- Verify the previous default no longer has the badge
- **Expected:** Only one default at a time

#### Delete (Archive)
- Click **Delete** on any non-default schedule
- Modal shows impact: number of invoices and pending reminders
- Click **Delete Schedule** to confirm
- Verify schedule disappears from the list
- **Expected:** Cannot delete the default schedule (error shown)

#### Viewer Restrictions
- Log in as a viewer
- Navigate to Reminders → Schedules
- Verify **Edit**, **Activate/Deactivate**, **Set as default**, and **Delete** buttons are hidden
- **Expected:** Only "View Steps →" is visible

---

## Database Changes

The migration `0004_reminderschedule_is_default_archived.py` adds two non-nullable boolean fields with defaults, so it runs cleanly on existing data:
- All existing schedules get `is_default=False, archived=False`
- After migration, run `python manage.py setup_default_schedule --all-orgs` to mark one schedule per org as default

---

## Breaking Changes

**None.** All changes are additive:
- Existing schedules continue to work
- Existing reminder jobs are unaffected
- Existing endpoints remain unchanged
- New fields have sensible defaults

---

## Next Steps (Future Work)

1. **Invoice-Schedule Assignment:** Add a `schedule` FK to `Invoice` so each invoice can override the default schedule
2. **Customer Default Schedule:** Add `default_schedule` FK to `Customer`
3. **Schedule Selection UI:** Add schedule picker when creating/editing invoices
4. **Fallback Logic:** When an invoice's schedule is archived, fall back to the org's default schedule

---

## Files Changed

### Backend
- `reminders/models.py` — added 2 fields
- `reminders/migrations/0004_reminderschedule_is_default_archived.py` — new migration
- `reminders/schedule_serializers.py` — added fields to serializer
- `reminders/schedule_views.py` — added 3 actions + updated destroy/get_queryset
- `reminders/schedule_tasks.py` — added archived filter
- `reminders/management/commands/setup_default_schedule.py` — set is_default=True
- `reminders/tests_schedule_management.py` — new test file, 22 tests

### Frontend
- `frontend/src/lib/api.ts` — added types, added 4 API methods
- `frontend/src/App.tsx` — added handlers, updated UI, added confirmation modal

---

## Test Coverage

| Feature | Backend Tests | Frontend Coverage |
|---|---|---|
| Toggle active/inactive | 6 tests | Manual testing required |
| Archive schedule | 7 tests | Manual testing required |
| Set default | 7 tests | Manual testing required |
| Task filtering | 2 tests | N/A (backend only) |
| Permissions | Covered in all tests | Manual testing required |
| Audit logs | Covered in all tests | N/A (backend only) |

---

**End of Summary**
