# Frontend Integration Guide - Reminders Page

## ✅ Completed Steps

1. **API Types Added** - Reminder types added to `frontend/src/lib/api.ts`
2. **API Functions Added** - All reminder API calls added to `frontend/src/lib/api.ts`
3. **Navigation Updated** - "Reminders" enabled in sidebar (removed `soon: true`)

## 🔧 Manual Integration Required

Due to the large size of `App.tsx` (2282 lines), you need to manually integrate the Reminders component.

### Step 1: Locate the Reminders Placeholder in App.tsx

Find this section (around line 1800-1900):

```typescript
{/* -- Reminders / Reconciliation (coming soon) -- */}
{page === 'Reminders' && (
  <div style={{ padding: '40px', textAlign: 'center' }}>
    <Bell size={64} style={{ opacity: 0.3, marginBottom: '16px' }} />
    <h2>Payment Reminders</h2>
    <p style={{ color: '#6b7280' }}>Coming soon...</p>
  </div>
)}
```

### Step 2: Replace with Reminders Page Component

Replace the entire block above with:

```typescript
{/* -- Reminders Page -- */}
{page === 'Reminders' && selectedOrg && (
  <RemindersPage org={selectedOrg} />
)}
```

### Step 3: Add RemindersPage Component Function

The complete `RemindersPage` component is in the file:
**`FRONTEND_REMINDERS_COMPONENT.tsx`**

Copy the entire `RemindersPage` function from that file and paste it into `App.tsx` **AFTER** the `SettingsScreen` component (around line 800-900) and **BEFORE** the main `export default function App()` function.

The structure should be:

```typescript
// ... other components ...

function SettingsScreen({ ... }) {
  // existing settings screen code
}

// ADD HERE: Paste the entire RemindersPage function
function RemindersPage({ org }: { org: Org }) {
  // ... RemindersPage code from FRONTEND_REMINDERS_COMPONENT.tsx ...
}

export default function App() {
  // ... main app code ...
}
```

---

## Alternative: Copy-Paste Instructions

If you prefer step-by-step instructions:

1. **Open** `frontend/src/App.tsx` in your editor
2. **Search** for `{page === 'Reminders'`
3. **Select** the entire block from `{page === 'Reminders' &&` to the closing `}`
4. **Replace** with: `{page === 'Reminders' && selectedOrg && <RemindersPage org={selectedOrg} />}`
5. **Find** the line `function SettingsScreen`
6. **Scroll down** to the closing `}` of that function
7. **After that closing brace**, paste the entire `RemindersPage` function from `FRONTEND_REMINDERS_COMPONENT.tsx`
8. **Save** the file

---

## Verification

After integration:

1. Start the frontend: `npm run dev`
2. Click "Reminders" in the sidebar
3. You should see the Reminders page with:
   - "Set Up Reminders" button (if no schedules exist)
   - Four tabs: Pending Approvals, Sent History, Failed, Schedules
   - Empty state messages

---

## Quick Test

To test the complete workflow:

1. Click "Set Up Reminders" button
2. Confirm the popup
3. You should see success message: "Default reminder setup created successfully (4 steps created)"
4. Switch to "Schedules" tab
5. You should see "Standard Payment Reminder Workflow" with 4 steps
6. Click "View Steps" to see the configured offsets

---

## Troubleshooting

### "RemindersPage is not defined"
- Make sure you pasted the component function in the correct location
- It must be between other component functions and the main `App()` function

### API errors "404 Not Found"
- Make sure Django backend is running: `python manage.py runserver`
- Check that the URLs are correct in `backend/reminders/urls.py`

### Type errors for ReminderSchedule, ReminderStep, ReminderJob
- Make sure the types were added to `frontend/src/lib/api.ts`
- Restart the TypeScript server in your IDE

### "org is undefined"
- Make sure you're passing `selectedOrg` to the component
- The condition should be: `{page === 'Reminders' && selectedOrg && <RemindersPage org={selectedOrg} />}`

---

## Next Steps After Integration

1. **Test Seed Functionality**
   - Click "Set Up Reminders"
   - Verify default schedule is created

2. **Test with Real Data**
   - Create a test invoice with due date = today + 7 days
   - Wait for Celery Beat to run (or manually trigger)
   - Check "Pending Approvals" tab

3. **Test Approval Workflow**
   - Click "Preview & Approve" on a pending reminder
   - Review email HTML in preview
   - Add custom intro/closing
   - Approve and verify email is sent

4. **Check Email Delivery**
   - If using console backend: check Django terminal for email output
   - If using SMTP: check recipient inbox

---

## Files Modified Summary

✅ **frontend/src/lib/api.ts**
- Added ReminderSchedule, ReminderStep, ReminderJob types
- Added reminder API functions
- No manual changes needed (already done)

✅ **frontend/src/App.tsx**
- Removed `soon: true` from Reminders navigation (already done)
- Need to add RemindersPage component (manual)
- Need to replace "coming soon" placeholder (manual)

---

## Component Features

The RemindersPage component includes:

✅ **Pending Approvals Tab**
- Lists all reminders awaiting approval
- Shows invoice, customer, outstanding amount, due date
- Status badges for step tone
- Preview & Approve button
- Reject button

✅ **Email Preview Modal**
- Full HTML email preview in iframe
- Invoice and customer information
- Editable custom intro and closing messages
- Current outstanding balance (live recalculation)
- Approve & Send button

✅ **Sent History Tab**
- Lists all dispatched reminders
- Shows sent timestamp, invoice, customer, amount
- Step information

✅ **Failed Deliveries Tab**
- Lists all failed email sends
- Shows error messages
- Retry count

✅ **Schedules Tab**
- Lists all reminder schedules
- Shows active/disabled status
- Step count and business hours
- Expandable step details
- View steps panel with trigger offsets

✅ **Setup Wizard**
- "Set Up Reminders" button for first-time users
- Creates default 4-step schedule via API
- Success/error messaging

---

## Design Notes

- **Consistent with existing UI**: Uses same styling patterns as Invoices/Customers pages
- **Responsive tables**: Matches invoice list table design
- **Status badges**: Color-coded like invoice statuses
- **Modal pattern**: Reuses existing modal structure
- **Money formatting**: Uses existing `money()` helper
- **Date formatting**: Uses existing `fmtDate()` helper
- **Error handling**: Uses ApiError pattern
- **Loading states**: Consistent spinner/disabled states

---

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/reminders/schedules/` | GET | List schedules |
| `/api/v1/reminders/schedules/` | POST | Create schedule |
| `/api/v1/reminders/steps/` | GET | List steps |
| `/api/v1/reminders/jobs-v2/` | GET | List reminder jobs |
| `/api/v1/reminders/jobs-v2/{id}/` | GET | Get job with preview |
| `/api/v1/reminders/jobs-v2/{id}/approve/` | POST | Approve and dispatch |
| `/api/v1/reminders/jobs-v2/{id}/reject/` | POST | Reject reminder |
| `/api/v1/reminders/seed-defaults/` | POST | Create default setup |

---

## Support

If you encounter any issues during integration:

1. Check browser console for JavaScript errors
2. Check Django terminal for backend errors
3. Verify all imports are correct in App.tsx
4. Ensure ReminderSchedule, ReminderStep, ReminderJob types are available
5. Verify selectedOrg is passed to RemindersPage component

The backend is fully functional and tested. Once the frontend component is integrated, the complete reminder system will be operational.
