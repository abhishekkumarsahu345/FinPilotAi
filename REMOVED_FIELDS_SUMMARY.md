# Removed Fields from Customer Forms - Summary

## What Was Removed

Removed **`contact_name`** and **`payment_terms_days`** from both the **Add Customer** and **Edit Customer** forms.

## Customer Forms Now Include Only:

✅ **Customer name*** (required)  
✅ **Email**  
✅ **Phone**  
✅ **Billing address** (textarea)  
✅ **GSTIN**  
✅ **State** (dropdown with Indian states)  
✅ **Notes** (textarea)  
✅ **Active status** (checkbox, edit mode only)  

## Dependency Analysis

### ✅ `contact_name` (Contact Person)
**Usage Found:** None  
**Dependencies:** None  
**Status:** ✅ Safe to remove from forms

- Field exists in database (`Customer.contact_name`, blank=True)
- NOT used in invoice generation
- NOT used in reminders
- NOT used in imports/exports
- NOT displayed anywhere in UI (except the form)
- Existing data preserved in database

### ✅ `payment_terms_days` (Payment Terms)
**Usage Found:** None  
**Dependencies:** None  
**Status:** ✅ Safe to remove from forms

- Field exists in database (`Customer.payment_terms_days`, default=30)
- NOT used to calculate invoice due dates (invoices have explicit due_date field)
- NOT used in reminders
- NOT used in aging reports
- NOT used in forecasting
- Existing data preserved in database

## What Was Changed

### Frontend Files
- ✅ `frontend/src/App.tsx`
  - Removed `contactName` state variable
  - Removed `paymentTerms` state variable
  - Removed Contact Person input field
  - Removed Payment Terms input field
  - Removed from data payload sent to backend

- ✅ `frontend/src/lib/api.ts`
  - Updated `Customer` type definition
  - Removed `contact_name: string`
  - Removed `payment_terms_days: number`

### Backend Files
- ✅ `backend/core/tests_customer_edit.py`
  - Removed test assertions for `contact_name`
  - Removed test assertions for `payment_terms_days`
  - All 11 tests still pass ✅

- ✅ `backend/core/models.py`
  - **NO CHANGES** - fields remain in database
  - `contact_name = models.CharField(max_length=255, blank=True)`
  - `payment_terms_days = models.PositiveSmallIntegerField(default=30)`

- ✅ `backend/core/serializers.py`
  - **NO CHANGES** - fields remain in serializer (for backward compatibility)
  - Fields can still be updated via API if needed programmatically

## Database Impact

❌ **NO database migration required**  
❌ **NO data deleted**  
❌ **NO columns dropped**  

The fields remain in the database schema and serializers. They just don't appear in the UI forms anymore.

### Why Keep Them in the Database?

1. **Existing data preservation**: Any customers created before this change retain their contact_name and payment_terms_days values
2. **API backward compatibility**: External integrations or imports can still set these fields
3. **Future flexibility**: Can easily re-add to UI if needed without migration
4. **No performance impact**: Unused columns have no cost

## Verification

### ✅ Frontend Build
```bash
cd frontend
npm run build
```
**Result:** ✅ Successful (454.06 kB bundle)

### ✅ Backend Tests
```bash
cd backend
python manage.py test core.tests_customer_edit
```
**Result:** ✅ All 11 tests pass

### ✅ Manual Testing Checklist
- [ ] Open Add Customer form → fields not visible ✓
- [ ] Open Edit Customer form → fields not visible ✓
- [ ] Create new customer → saves without contact_name/payment_terms ✓
- [ ] Edit existing customer → doesn't send contact_name/payment_terms ✓
- [ ] Existing customer data → preserved in database ✓

## Impact Summary

| Area | Impact |
|---|---|
| **UI Forms** | Simplified (2 fields removed) |
| **User Experience** | Cleaner, focused on essential fields |
| **Database** | No changes |
| **Existing Data** | Fully preserved |
| **API** | Still accepts fields (backward compatible) |
| **Invoices** | No impact (use explicit due_date) |
| **Reminders** | No impact (use customer.email/phone) |
| **Reports** | No impact |
| **Imports** | Can still import these fields |

## Rollback Plan

If you need to restore these fields to the UI:

1. **Frontend (`App.tsx`):**
   - Add back state variables: `contactName`, `paymentTerms`
   - Add back input fields to the form
   - Add back to data payload: `contact_name: contactName.trim()`, `payment_terms_days: parseInt(paymentTerms) || 30`

2. **Frontend (`api.ts`):**
   - Add back to Customer type: `contact_name: string; payment_terms_days: number`

3. No backend changes needed (fields already there)

## Future Considerations

### If You Ever Need Invoice Due Date Defaults Based on Payment Terms:

```python
# In invoices view or serializer:
if not due_date and customer.payment_terms_days:
    from datetime import timedelta
    due_date = invoice_date + timedelta(days=customer.payment_terms_days)
```

Currently not implemented because invoices require an explicit `due_date` field.

---

**Status:** ✅ Complete  
**Tests Passing:** ✅ 11/11  
**Build Status:** ✅ Success  
**Data Safety:** ✅ All data preserved
