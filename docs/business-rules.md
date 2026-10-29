# Financial rules implemented in the initial foundation

- Monetary amounts are integer paise. No floating point value is stored or used for ledger arithmetic.
- Invoice total is calculated by the API: subtotal − discount + tax. Discount cannot exceed subtotal.
- Customer, invoice, payment, and allocation queries are scoped to the active organization membership.
- Only owner, finance manager, and accountant memberships can write customer, invoice, and payment records. Viewer and collections roles are read-only in this foundation.
- Invoices are drafts by default; issued invoices are included in receivables. Voided and draft invoices are excluded.
- Outstanding amount is `max(0, invoice total − valid allocations)`.
- Payment allocations must be positive, must not exceed payment amount or current invoice balance, and must target an issued invoice for the payment's customer in the same organization.
- A payment may be partly unallocated; the payment amount and allocation records remain distinct.
- Aging uses the server's organization runtime date (Asia/Kolkata default); one invoice appears in exactly one bucket.
- Reminder delivery and automatic financial action are not enabled.

Before production, add transaction-safe locking/idempotency for concurrent allocations, a reviewed reversal workflow, organization creation audit events, complete audit coverage, and tenant/security tests.
